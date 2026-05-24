"""Distill normalized agent transcript events into a steering packet."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Tool calls that are book-keeping or read-only — exclude from "attempts"
# because they don't represent progress on the underlying problem.
_NOISY_TOOLS = {
    "Read",
    "Glob",
    "Grep",
    "LS",
    "TodoWrite",
    "TaskList",
    "TaskGet",
    "TaskOutput",
    "TaskCreate",
    "TaskUpdate",
    "ToolSearch",
}

# Per-string truncation when keeping evidence
_EXCERPT_LIMIT = 280
_STDERR_LIMIT = 500
_MAX_EXCERPTS = 16
_MAX_STDERR_LINES = 12


@dataclass
class Trajectory:
    decisions: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_failures: list[dict[str, Any]] = field(default_factory=list)
    stderr_highlights: list[str] = field(default_factory=list)
    transcript_excerpt: list[str] = field(default_factory=list)
    user_intents: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    loops_detected: list[str] = field(default_factory=list)
    git_branch: str | None = None
    cwd: str | None = None


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def filter_recent(
    events: list[dict[str, Any]],
    lookback_minutes: int,
    max_events: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    cutoff = (now or datetime.now(UTC)) - timedelta(minutes=lookback_minutes)
    kept: list[dict[str, Any]] = []
    for ev in events:
        ts = _event_timestamp(ev)
        if ts is None:
            continue
        if ts >= cutoff:
            kept.append(ev)
    return kept[-max_events:]


def distill(events: Iterable[dict[str, Any]]) -> Trajectory:
    traj = Trajectory()
    events = list(events)

    for ev in events:
        if ev.get("cwd") and not traj.cwd:
            traj.cwd = ev["cwd"]
        if ev.get("gitBranch") and not traj.git_branch:
            traj.git_branch = ev["gitBranch"]

        et = ev.get("type")
        if et == "user":
            _handle_user(ev, traj)
        elif et == "assistant":
            _handle_assistant(ev, traj)
        elif et == "attachment":
            _handle_attachment(ev, traj)

    traj.loops_detected = _detect_loops(traj)
    traj.transcript_excerpt = traj.transcript_excerpt[-_MAX_EXCERPTS:]
    traj.stderr_highlights = _dedupe(traj.stderr_highlights)[:_MAX_STDERR_LINES]
    traj.files_touched = _dedupe(traj.files_touched)
    return traj


def _event_timestamp(ev: dict[str, Any]) -> datetime | None:
    ts = ev.get("timestamp")
    if not ts and isinstance(ev.get("snapshot"), dict):
        ts = ev["snapshot"].get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _handle_user(ev: dict[str, Any], traj: Trajectory) -> None:
    msg = ev.get("message") or {}
    content = msg.get("content")

    # User-role messages may contain only tool_results (the API convention).
    # Route those to the failure tracker and skip the user-intent path.
    if isinstance(content, list):
        only_tool_results = (
            all(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)
            and len(content) > 0
        )
        if only_tool_results:
            for item in content:
                _handle_tool_result(item, traj)
            return

    text = _flatten_text(content)
    if not text:
        return
    text = _trim(text, _EXCERPT_LIMIT)
    if _looks_like_intent(text):
        traj.user_intents.append(text)
    if _looks_like_question(text):
        traj.open_questions.append(text)
    traj.transcript_excerpt.append(f"USER: {text}")


def _handle_assistant(ev: dict[str, Any], traj: Trajectory) -> None:
    msg = ev.get("message") or {}
    content = msg.get("content") or []
    if isinstance(content, str):
        traj.transcript_excerpt.append(f"AI: {_trim(content, _EXCERPT_LIMIT)}")
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype == "text":
            txt = item.get("text", "")
            if txt:
                traj.transcript_excerpt.append(f"AI: {_trim(txt, _EXCERPT_LIMIT)}")
                if _looks_like_decision(txt):
                    traj.decisions.append(_trim(txt, 200))
        elif itype == "tool_use":
            name = item.get("name", "?")
            tool_input = item.get("input", {})
            summary = _summarize_tool_input(name, tool_input)
            traj.tool_calls.append({"name": name, "summary": summary})
            if name not in _NOISY_TOOLS:
                traj.attempts.append(f"{name}: {summary}")
            for path in _extract_paths(tool_input):
                traj.files_touched.append(path)
        elif itype == "tool_result":
            _handle_tool_result(item, traj)


def _handle_tool_result(item: dict[str, Any], traj: Trajectory) -> None:
    if not item.get("is_error"):
        return
    raw = item.get("content")
    text = _flatten_text(raw)
    if not text:
        return
    short = _trim(text, _STDERR_LIMIT)
    traj.stderr_highlights.append(short)
    traj.tool_failures.append({"tool_use_id": item.get("tool_use_id"), "stderr": short})


def _handle_attachment(ev: dict[str, Any], traj: Trajectory) -> None:
    att = ev.get("attachment") or {}
    label = att.get("filename") or att.get("type") or "attachment"
    traj.transcript_excerpt.append(f"ATTACH: {label}")


def _flatten_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                elif "content" in item:
                    parts.append(_flatten_text(item["content"]))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        if "content" in content:
            return _flatten_text(content["content"])
    return str(content)


def _summarize_tool_input(name: str, tool_input: Any) -> str:
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            try:
                tool_input = json.loads(tool_input.replace("'", '"'))
            except Exception:
                return _trim(tool_input, 160)
    if not isinstance(tool_input, dict):
        return _trim(str(tool_input), 160)
    if name == "Bash":
        cmd = tool_input.get("command", "")
        return _trim(cmd, 200)
    for key in ("file_path", "path", "pattern", "url", "query"):
        if key in tool_input:
            return _trim(f"{key}={tool_input[key]}", 200)
    return _trim(json.dumps(tool_input)[:200], 200)


def _extract_paths(tool_input: Any) -> list[str]:
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input.replace("'", '"'))
        except Exception:
            return []
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        v = tool_input.get(key)
        if isinstance(v, str):
            paths.append(v)
    return paths


def _looks_like_intent(text: str) -> bool:
    return bool(
        re.search(r"\b(want|need|let's|please|can you|build|fix|add|remove|refactor)\b", text, re.I)
    )


def _looks_like_question(text: str) -> bool:
    return text.strip().endswith("?") or text.lower().startswith(("why", "how", "what", "should"))


def _looks_like_decision(text: str) -> bool:
    return bool(
        re.search(
            r"\b(I'll|I will|let's|going to|switching to|deciding|chose|picked|approach)\b",
            text,
            re.I,
        )
    )


def _detect_loops(traj: Trajectory) -> list[str]:
    loops: list[str] = []

    bash_cmds = [c["summary"] for c in traj.tool_calls if c["name"] == "Bash"]
    counts: dict[str, int] = {}
    for cmd in bash_cmds:
        key = re.sub(r"\s+", " ", cmd.strip())[:120]
        counts[key] = counts.get(key, 0) + 1
    for key, n in counts.items():
        if n >= 3:
            loops.append(f"Repeated command (x{n}): {key}")

    file_counts: dict[str, int] = {}
    for path in traj.files_touched:
        file_counts[path] = file_counts.get(path, 0) + 1
    for path, n in file_counts.items():
        if n >= 4:
            loops.append(f"Repeatedly editing (x{n}): {path}")

    err_counts: dict[str, int] = {}
    for err in traj.stderr_highlights:
        sig = re.sub(r"\d+", "N", err[:80])
        err_counts[sig] = err_counts.get(sig, 0) + 1
    for sig, n in err_counts.items():
        if n >= 2:
            loops.append(f"Same error class (x{n}): {sig}")

    return loops


def _trim(s: str, limit: int) -> str:
    s = s.strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


def _dedupe(xs: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
