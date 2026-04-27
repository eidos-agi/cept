"""Progress events + pluggable adapters.

Cept emits structured ``Event`` records at phase boundaries (locating, distilling,
asking the model, etc). Adapters consume those events: stdout, file, Unix socket,
spawned subprocess (used by the Swift HUD), macOS notifications, or noop. Multiple
adapters may be attached to one ``Emitter`` and all see every event.

This is the stable public contract — anyone can implement another adapter (in any
language, on the consuming side) by reading JSONL with the schema below:

    {"run_id": "...", "seq": 1, "ts": "...", "phase": "...",
     "level": "info|warn|error", "msg": "...", "data": {...}}

Phase names are stable; ``data`` payload may grow over time.
"""

from __future__ import annotations

import json
import os
import shlex
import socket as socketlib
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, Protocol, runtime_checkable

# ---------------------------------------------------------------- Event ----


@dataclass
class Event:
    run_id: str
    seq: int
    ts: str
    phase: str
    level: str = "info"
    msg: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "seq": self.seq,
            "ts": self.ts,
            "phase": self.phase,
            "level": self.level,
            "msg": self.msg,
            "data": self.data,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), default=str) + "\n"

    def to_text(self) -> str:
        marker = {"info": "·", "warn": "!", "error": "x"}.get(self.level, "·")
        body = self.msg or self.phase
        return f"[cept {marker}] {self.phase:<24} {body}"


# ------------------------------------------------------------- Adapters ----


@runtime_checkable
class Adapter(Protocol):
    def emit(self, event: Event) -> None: ...
    def close(self) -> None: ...


class NoopAdapter:
    def emit(self, event: Event) -> None:  # noqa: ARG002
        del event

    def close(self) -> None:
        pass


class StdoutAdapter:
    """Human-readable text or JSONL to stdout/stderr."""

    def __init__(
        self,
        *,
        jsonl: bool = False,
        stream: IO[str] | None = None,
    ) -> None:
        self.jsonl = jsonl
        self.stream = stream if stream is not None else sys.stdout

    def emit(self, event: Event) -> None:
        try:
            self.stream.write(event.to_jsonl() if self.jsonl else event.to_text() + "\n")
            self.stream.flush()
        except Exception:
            pass

    def close(self) -> None:
        pass


class FileAdapter:
    """Append JSONL to a file. Parent dirs are created."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh: IO[str] | None = self.path.open("a", encoding="utf-8")

    def emit(self, event: Event) -> None:
        if not self.fh:
            return
        try:
            self.fh.write(event.to_jsonl())
            self.fh.flush()
        except Exception:
            pass

    def close(self) -> None:
        if self.fh:
            try:
                self.fh.close()
            except Exception:
                pass
            self.fh = None


class SocketAdapter:
    """JSONL to a Unix domain socket. Silently no-ops if the socket isn't there."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(Path(path).expanduser())
        self.sock: socketlib.socket | None = None
        try:
            s = socketlib.socket(socketlib.AF_UNIX, socketlib.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(self.path)
            s.settimeout(None)
            self.sock = s
        except Exception:
            self.sock = None

    def emit(self, event: Event) -> None:
        if not self.sock:
            return
        try:
            self.sock.sendall(event.to_jsonl().encode("utf-8"))
        except Exception:
            self.sock = None  # next emit no-ops

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class SubprocessAdapter:
    """Spawn a command and write JSONL to its stdin. The HUD adapter."""

    def __init__(self, cmd: list[str]) -> None:
        self.cmd = cmd
        self.proc: subprocess.Popen[bytes] | None = None
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self.proc = None

    def emit(self, event: Event) -> None:
        if not self.proc or not self.proc.stdin:
            return
        try:
            self.proc.stdin.write(event.to_jsonl().encode("utf-8"))
            self.proc.stdin.flush()
        except Exception:
            self.proc = None

    def close(self) -> None:
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass


class NotifyAdapter:
    """macOS notification-center banners via osascript. Silent on non-mac."""

    _NOISY_PHASES = {"locating", "filtering", "redacting", "collecting_repo_state"}

    def __init__(self) -> None:
        self.enabled = sys.platform == "darwin"

    def emit(self, event: Event) -> None:
        if not self.enabled:
            return
        if event.phase in self._NOISY_PHASES and event.level == "info":
            return
        title = "cept"
        subtitle = event.phase
        body = event.msg or event.phase
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f"display notification {json.dumps(body)} "
                    f"with title {json.dumps(title)} "
                    f"subtitle {json.dumps(subtitle)}",
                ],
                capture_output=True,
                timeout=2,
            )
        except Exception:
            pass

    def close(self) -> None:
        pass


# --------------------------------------------------------------- Specs ----


def parse_emit_spec(spec: str) -> Adapter:
    """Parse a single ``--emit`` specifier string into an adapter."""
    s = spec.strip()
    if not s or s in ("noop", "none", "off"):
        return NoopAdapter()
    if s == "stdout":
        return StdoutAdapter(jsonl=False, stream=sys.stdout)
    if s == "stderr":
        return StdoutAdapter(jsonl=False, stream=sys.stderr)
    if s == "notify":
        return NotifyAdapter()
    if s == "hud":
        # Explicit override wins (full command line)
        explicit_cmd = os.environ.get("CEPT_HUD_CMD")
        if explicit_cmd:
            return SubprocessAdapter(shlex.split(explicit_cmd))
        # Otherwise resolve the binary (auto-builds on first use)
        from . import hud_install  # local import to avoid cycle on import-time

        path = hud_install.ensure()
        if not path:
            print(
                "cept: --emit hud requested but cept-hud unavailable; falling back to noop. "
                "Try: cept-hud-install",
                file=sys.stderr,
            )
            return NoopAdapter()
        return SubprocessAdapter([str(path), "--once"])
    if ":" in s:
        kind, _, rest = s.partition(":")
        kind = kind.strip()
        rest = rest.strip()
        if kind == "jsonl":
            if rest in ("-", "stdout"):
                return StdoutAdapter(jsonl=True, stream=sys.stdout)
            if rest == "stderr":
                return StdoutAdapter(jsonl=True, stream=sys.stderr)
            return FileAdapter(rest)
        if kind == "file":
            return FileAdapter(rest)
        if kind == "socket":
            return SocketAdapter(rest)
        if kind == "subprocess":
            return SubprocessAdapter(shlex.split(rest))
    raise ValueError(f"unknown --emit spec: {spec!r}")


def parse_emit_specs(specs: list[str] | str | None) -> list[Adapter]:
    if not specs:
        return []
    if isinstance(specs, str):
        specs = [s for s in specs.split(",") if s.strip()]
    return [parse_emit_spec(s) for s in specs]


# -------------------------------------------------------------- Emitter ----


class Emitter:
    """Fan-out events to a list of adapters, with a `phase` context manager."""

    def __init__(
        self,
        adapters: list[Adapter] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.adapters: list[Adapter] = list(adapters or [])
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.seq = 0

    def add(self, adapter: Adapter) -> None:
        self.adapters.append(adapter)

    def emit(
        self,
        phase: str,
        msg: str = "",
        *,
        level: str = "info",
        **data: Any,
    ) -> None:
        self.seq += 1
        ev = Event(
            run_id=self.run_id,
            seq=self.seq,
            ts=datetime.now(UTC).isoformat(),
            phase=phase,
            level=level,
            msg=msg,
            data=dict(data),
        )
        for ad in self.adapters:
            try:
                ad.emit(ev)
            except Exception:
                pass

    @contextmanager
    def phase(
        self,
        name: str,
        msg: str = "",
        **data: Any,
    ) -> Iterator[None]:
        start = time.monotonic()
        self.emit(name, msg or name, **data)
        try:
            yield
        except Exception as e:
            self.emit(name, f"{name} failed: {e}", level="error", **data)
            raise
        else:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.emit(f"{name}.done", "", duration_ms=elapsed_ms, **data)

    def close(self) -> None:
        for ad in self.adapters:
            try:
                ad.close()
            except Exception:
                pass
        self.adapters = []
