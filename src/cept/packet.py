"""Build the steering packet — the redacted artifact sent to the model."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .distiller import Trajectory
from .redactor import redact_obj
from .repo_state import RepoState


def build_packet(
    *,
    goal: str,
    headline: str,
    mode: str,
    lookback_minutes: int,
    session_path: str,
    trajectory: Trajectory,
    repo: RepoState,
    question: str | None,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "meta": {
            "captured_at": datetime.now(UTC).isoformat(),
            "lookback_minutes": lookback_minutes,
            "mode": mode,
            "headline": headline,
            "session_path": session_path,
            "cwd": trajectory.cwd or repo.cwd,
            "git_branch": trajectory.git_branch or repo.branch,
        },
        "objective": goal,
        "ask": question or _default_ask(mode),
        "project_state": {
            "is_git_repo": repo.is_git_repo,
            "branch": repo.branch,
            "dirty_files": repo.dirty_files,
            "untracked_count": repo.untracked_count,
            "diff_stat": repo.diff_stat,
        },
        "recent_trajectory": {
            "user_intents": trajectory.user_intents,
            "decisions": trajectory.decisions,
            "attempts": trajectory.attempts,
            "files_touched": trajectory.files_touched,
            "tool_failures": trajectory.tool_failures,
            "loops_detected": trajectory.loops_detected,
            "open_questions": trajectory.open_questions,
        },
        "evidence": {
            "stderr_highlights": trajectory.stderr_highlights,
            "transcript_excerpt": trajectory.transcript_excerpt,
        },
    }
    if files:
        packet["files"] = files
    return redact_obj(packet)


def _default_ask(mode: str) -> str:
    return {
        "steer": "What blind spots, alternative approaches, or external facts should the agent consider next?",
        "debug": "Rank the most likely root causes and propose the single best next step.",
        "research": "Find external facts, docs, or version-specific gotchas relevant to this work.",
        "architecture": "Compare design alternatives. What tradeoffs is the agent missing?",
    }.get(mode, "What should the agent consider next?")


# ---- helpers used by callers / tests ---------------------------------------


def trajectory_dict(traj: Trajectory) -> dict[str, Any]:
    return asdict(traj)


def repo_dict(repo: RepoState) -> dict[str, Any]:
    return asdict(repo)
