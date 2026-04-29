"""Read source files into the steering packet.

cept's trajectory tells the model *what the agent did*. Without the file
contents, the model can't critique *what's in the files* — and most production
failures are content-shape, not workflow-shape. This module pulls a
caller-supplied list of paths into the packet under ``files``, with size caps
and basic safety so the upload stays bounded and the model can quote specific
lines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Per-file byte cap before truncation. 50 KB is enough for a long README or a
# medium source file; bigger files get the head, with a marker showing the cut.
_PER_FILE_CAP = 50 * 1024
# Total bytes across all included files. Stops the packet from blowing up if
# the caller passes a giant list.
_TOTAL_CAP = 256 * 1024
# Marker appended where a file was cut off by either cap.
_TRUNCATED_MARKER = "\n…[truncated by cept; full file is larger]\n"
# Hard cap on number of files in one call — refuses extras with a note.
_MAX_FILES = 24


@dataclass
class FileEntry:
    """One file's content + metadata, ready to drop into the packet."""

    path: str  # the path the caller passed (kept verbatim for citation)
    resolved: str  # absolute path actually read
    bytes_total: int
    bytes_included: int
    truncated: bool
    line_count: int
    content: str | None
    error: str | None = None


def collect_files(
    paths: list[str] | None,
    *,
    cwd: str | os.PathLike[str],
    per_file_cap: int = _PER_FILE_CAP,
    total_cap: int = _TOTAL_CAP,
    max_files: int = _MAX_FILES,
) -> list[FileEntry]:
    """Read each path; return a FileEntry per attempt.

    Errors (missing, binary, permission) become entries with ``content=None``
    and ``error`` set, rather than raising — the agent should still see the
    rest of the packet, and the model benefits from knowing the file was
    requested but unreadable.
    """
    if not paths:
        return []

    cwd_path = Path(cwd)
    out: list[FileEntry] = []
    bytes_used = 0
    seen: set[str] = set()

    for raw in paths[:max_files]:
        if not isinstance(raw, str) or not raw.strip():
            continue
        original = raw.strip()
        # Resolve relative paths against cwd so the caller can pass either.
        resolved = (
            Path(original) if Path(original).is_absolute() else (cwd_path / original)
        ).expanduser()

        # Dedupe by resolved absolute path; keep the *first* spelling the
        # caller used (that's what they'll cite).
        try:
            key = str(resolved.resolve())
        except OSError:
            key = str(resolved)
        if key in seen:
            continue
        seen.add(key)

        entry = _read_one(
            original=original,
            resolved=resolved,
            per_file_cap=per_file_cap,
            remaining=max(0, total_cap - bytes_used),
        )
        out.append(entry)
        bytes_used += entry.bytes_included

        if bytes_used >= total_cap:
            # Tell the model the rest were skipped, rather than silently dropping.
            for skipped in paths[len(out) : max_files]:
                if isinstance(skipped, str) and skipped.strip():
                    out.append(
                        FileEntry(
                            path=skipped.strip(),
                            resolved=str(skipped.strip()),
                            bytes_total=0,
                            bytes_included=0,
                            truncated=False,
                            line_count=0,
                            content=None,
                            error=f"skipped: total cept files cap ({total_cap} bytes) reached",
                        )
                    )
            break

    if paths and len(paths) > max_files:
        # Same idea for callers who passed too many paths.
        for skipped in paths[max_files:]:
            if isinstance(skipped, str) and skipped.strip():
                out.append(
                    FileEntry(
                        path=skipped.strip(),
                        resolved=str(skipped.strip()),
                        bytes_total=0,
                        bytes_included=0,
                        truncated=False,
                        line_count=0,
                        content=None,
                        error=f"skipped: max_files ({max_files}) exceeded",
                    )
                )

    return out


def _read_one(
    *,
    original: str,
    resolved: Path,
    per_file_cap: int,
    remaining: int,
) -> FileEntry:
    cap = min(per_file_cap, remaining) if remaining > 0 else 0

    if not resolved.exists():
        return FileEntry(
            path=original,
            resolved=str(resolved),
            bytes_total=0,
            bytes_included=0,
            truncated=False,
            line_count=0,
            content=None,
            error="file not found",
        )
    if not resolved.is_file():
        return FileEntry(
            path=original,
            resolved=str(resolved),
            bytes_total=0,
            bytes_included=0,
            truncated=False,
            line_count=0,
            content=None,
            error="not a regular file",
        )
    if cap == 0:
        return FileEntry(
            path=original,
            resolved=str(resolved),
            bytes_total=resolved.stat().st_size,
            bytes_included=0,
            truncated=False,
            line_count=0,
            content=None,
            error="skipped: total cept files cap reached",
        )

    try:
        size = resolved.stat().st_size
        with resolved.open("rb") as fh:
            raw = fh.read(cap + 1)  # one extra byte tells us if the cap fired
    except OSError as e:
        return FileEntry(
            path=original,
            resolved=str(resolved),
            bytes_total=0,
            bytes_included=0,
            truncated=False,
            line_count=0,
            content=None,
            error=f"read error: {e}",
        )

    if b"\x00" in raw[: min(len(raw), 8000)]:
        return FileEntry(
            path=original,
            resolved=str(resolved),
            bytes_total=size,
            bytes_included=0,
            truncated=False,
            line_count=0,
            content=None,
            error="binary file (NUL byte detected); skipped",
        )

    truncated = len(raw) > cap
    if truncated:
        raw = raw[:cap]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    if truncated:
        text = text + _TRUNCATED_MARKER

    return FileEntry(
        path=original,
        resolved=str(resolved),
        bytes_total=size,
        bytes_included=len(raw),
        truncated=truncated,
        line_count=text.count("\n") + (0 if text.endswith("\n") else 1),
        content=text,
    )


def to_packet_field(entries: list[FileEntry]) -> dict[str, Any]:
    """Shape the entries for inclusion in the packet sent to the model.

    Keyed by the path the caller passed (verbatim) so the model's citations
    line up with what the calling agent will see in its own context.
    """
    out: dict[str, Any] = {}
    for e in entries:
        out[e.path] = {
            "resolved_path": e.resolved,
            "bytes_total": e.bytes_total,
            "bytes_included": e.bytes_included,
            "truncated": e.truncated,
            "line_count": e.line_count,
            "content": e.content,
            "error": e.error,
        }
    return out
