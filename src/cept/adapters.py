"""Transcript adapters for agent-specific session sources.

Adapters own discovery and normalization. Downstream cept code receives the
same event shape regardless of whether the source was Claude Code JSONL or a
generic agent transcript file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import distiller, locator


class TranscriptValidationError(ValueError):
    pass


@dataclass
class LoadedTranscript:
    adapter: str
    path: Path
    session_id: str
    source: str
    events: list[dict[str, Any]]


class TranscriptAdapter(Protocol):
    name: str

    def load(
        self,
        *,
        cwd: str | Path,
        session_id: str | None,
        cept_id: str | None,
    ) -> LoadedTranscript:
        ...


class ClaudeCodeTranscriptAdapter:
    name = "claude-code"

    def load(
        self,
        *,
        cwd: str | Path,
        session_id: str | None,
        cept_id: str | None,
    ) -> LoadedTranscript:
        location = locator.find_session(cwd=cwd, session_id=session_id, cept_id=cept_id)
        return LoadedTranscript(
            adapter=self.name,
            path=location.path,
            session_id=location.session_id,
            source=location.source,
            events=distiller.parse_jsonl(location.path),
        )


class FileTranscriptAdapter:
    name = "file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(
        self,
        *,
        cwd: str | Path,
        session_id: str | None,
        cept_id: str | None,
    ) -> LoadedTranscript:
        if cept_id:
            raise FileNotFoundError("cept_id session verification is only supported by claude-code")
        path = self.path.expanduser().resolve()
        events = [_normalize_event(row, cwd=cwd, path=path, line=line) for line, row in _read_jsonl(path)]
        return LoadedTranscript(
            adapter=self.name,
            path=path,
            session_id=session_id or path.stem,
            source="explicit-file",
            events=events,
        )


def load_transcript(
    *,
    cwd: str | Path,
    transcript: str | Path | None = None,
    source: str = "auto",
    session_id: str | None = None,
    cept_id: str | None = None,
) -> LoadedTranscript:
    """Load a transcript from the selected adapter."""
    if transcript:
        if source not in {"auto", "file"}:
            raise ValueError("--transcript can only be used with source=auto or source=file")
        return FileTranscriptAdapter(transcript).load(cwd=cwd, session_id=session_id, cept_id=cept_id)
    if source in {"auto", "claude-code"}:
        return ClaudeCodeTranscriptAdapter().load(cwd=cwd, session_id=session_id, cept_id=cept_id)
    if source == "file":
        raise ValueError("source=file requires --transcript PATH")
    raise ValueError(f"unknown transcript source: {source}")


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    events: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as e:
                raise TranscriptValidationError(f"{path}: line {line_no}: invalid JSON: {e}") from e
            if not isinstance(row, dict):
                raise TranscriptValidationError(f"{path}: line {line_no}: row must be a JSON object")
            events.append((line_no, row))
    return events


def _normalize_event(
    row: dict[str, Any],
    *,
    cwd: str | Path,
    path: Path,
    line: int,
) -> dict[str, Any]:
    if _looks_like_cept_event(row):
        return row

    timestamp = row.get("timestamp") or row.get("ts")
    base: dict[str, Any] = {}
    if timestamp:
        base["timestamp"] = timestamp
    base["cwd"] = row.get("cwd") or str(Path(cwd).resolve())
    if row.get("git_branch"):
        base["gitBranch"] = row["git_branch"]

    role = row.get("role")
    event_type = row.get("type")
    if role is not None and role not in {"user", "assistant"}:
        _invalid(path, line, "role must be 'user' or 'assistant'")
    if role in {"user", "assistant"} and (row.get("text") or row.get("content")):
        content = row.get("text") or row.get("content")
        if role == "assistant":
            content = [{"type": "text", "text": str(content)}]
        return {**base, "type": role, "message": {"content": content}}
    if role in {"user", "assistant"}:
        _invalid(path, line, "role rows require text or content")

    if event_type in {"tool_call", "tool_use", "command"}:
        name = _normalize_tool_name(row.get("tool") or row.get("name") or event_type)
        tool_input = row.get("input")
        if tool_input is None and row.get("command"):
            tool_input = {"command": row["command"]}
        if tool_input is None:
            _invalid(path, line, "tool_call rows require input or command")
        return {
            **base,
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": row.get("id") or row.get("tool_use_id"),
                        "name": name,
                        "input": tool_input or {},
                    }
                ]
            },
        }

    if event_type in {"tool_result", "command_result"}:
        if not any(key in row for key in ("content", "stderr", "text")):
            _invalid(path, line, "tool_result rows require content, stderr, or text")
        return {
            **base,
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": row.get("tool_use_id") or row.get("id"),
                        "is_error": bool(row.get("is_error") or row.get("error")),
                        "content": row.get("content") or row.get("stderr") or row.get("text") or "",
                    }
                ]
            },
        }

    _invalid(
        path,
        line,
        "row must be a role message, tool_call, tool_result, or native cept event",
    )


def _looks_like_cept_event(row: dict[str, Any]) -> bool:
    return row.get("type") in {"user", "assistant", "attachment"} and isinstance(
        row.get("message") or row.get("attachment"), dict
    )


def _normalize_tool_name(raw: Any) -> str:
    name = str(raw or "").strip()
    if name.lower() in {"shell", "bash", "exec", "exec_command", "command"}:
        return "Bash"
    return name or "Tool"


def _invalid(path: Path, line: int, message: str) -> None:
    raise TranscriptValidationError(f"{path}: line {line}: {message}")
