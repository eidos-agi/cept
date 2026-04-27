"""End-to-end pipeline: locate → distill → repo state → packet → (optional) OpenRouter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import distiller, locator, openrouter, packet, repo_state


def run_cept(
    *,
    goal: str,
    cwd: str | Path | None = None,
    lookback_minutes: int = 20,
    max_events: int = 250,
    mode: str = "steer",
    session_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    question: str | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
    model: str = openrouter.DEFAULT_MODEL,
) -> dict[str, Any]:
    cwd = str(cwd or os.getcwd())

    location = locator.find_session(cwd=cwd, session_id=session_id)
    events = distiller.parse_jsonl(location.path)
    recent = distiller.filter_recent(events, lookback_minutes, max_events)
    traj = distiller.distill(recent)

    repo = (
        repo_state.collect(cwd, include_diff=include_diff)
        if include_repo_state
        else repo_state.RepoState(cwd=cwd)
    )

    pkt = packet.build_packet(
        goal=goal,
        mode=mode,
        lookback_minutes=lookback_minutes,
        session_path=str(location.path),
        trajectory=traj,
        repo=repo,
        question=question,
    )

    result: dict[str, Any] = {
        "session": {
            "path": str(location.path),
            "session_id": location.session_id,
            "discovery": location.source,
            "events_in_window": len(recent),
            "total_events": len(events),
        },
        "packet": pkt,
    }

    if dry_run:
        result["guidance"] = None
        return result

    guidance = openrouter.ask(pkt, api_key=api_key, model=model)
    result["guidance"] = guidance
    return result
