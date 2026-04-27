"""End-to-end pipeline: locate → distill → repo state → packet → (optional) OpenRouter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import distiller, keyfile, locator, openrouter, packet, repo_state


def run_cept(
    *,
    goal: str,
    cwd: str | Path | None = None,
    lookback_minutes: int | None = None,
    max_events: int = 250,
    mode: str = "steer",
    session_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    question: str | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    cwd = str(cwd or os.getcwd())

    # Per-tree credentials and defaults (file wins over process env).
    keyfile_result = keyfile.load_for(cwd)

    if lookback_minutes is None:
        lookback_minutes = _int_env("CEPT_LOOKBACK_MINUTES", 20)
    if model is None:
        model = os.environ.get("CEPT_DEFAULT_MODEL") or openrouter.DEFAULT_MODEL

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
        "keyfile": {
            "path": str(keyfile_result.path) if keyfile_result.path else None,
            "keys_set": keyfile_result.keys_set,
            "metadata": keyfile_result.metadata,
        },
        "config": {
            "model": model,
            "lookback_minutes": lookback_minutes,
        },
        "packet": pkt,
    }

    if dry_run:
        result["guidance"] = None
        return result

    guidance = openrouter.ask(pkt, api_key=api_key, model=model)
    result["guidance"] = guidance
    return result


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
