"""End-to-end pipeline: locate → distill → repo state → packet → (optional) OpenRouter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import distiller, events, keyfile, locator, openrouter, packet, repo_state


def run_cept(
    *,
    goal: str,
    cwd: str | Path | None = None,
    lookback_minutes: int | None = None,
    max_events: int = 250,
    mode: str = "steer",
    session_id: str | None = None,
    cept_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    question: str | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    emitter: events.Emitter | None = None,
) -> dict[str, Any]:
    cwd = str(cwd or os.getcwd())
    em = emitter or events.Emitter()

    em.emit("run.start", "cept run started", goal=goal, mode=mode, cwd=cwd)

    try:
        # ---- per-tree credentials and defaults --------------------------
        with em.phase("loading_keyfile", "looking for .ceptkey"):
            keyfile_result = keyfile.load_for(cwd)
        if keyfile_result.path:
            em.emit(
                "keyfile.loaded",
                str(keyfile_result.path),
                keys_set=keyfile_result.keys_set,
                key_name=keyfile_result.metadata.get("key_name"),
                service=keyfile_result.metadata.get("service"),
            )

        if lookback_minutes is None:
            lookback_minutes = _int_env("CEPT_LOOKBACK_MINUTES", 20)
        if model is None:
            model = os.environ.get("CEPT_DEFAULT_MODEL") or openrouter.DEFAULT_MODEL

        # ---- locate active session JSONL --------------------------------
        with em.phase(
            "locating",
            "locating active Claude Code session",
            cept_id=cept_id,
        ):
            location = locator.find_session(cwd=cwd, session_id=session_id, cept_id=cept_id)
        em.emit(
            "session.found",
            location.path.name,
            session_id=location.session_id,
            discovery=location.source,
            verified=(location.source == "cept_id"),
        )

        # ---- parse + filter ---------------------------------------------
        with em.phase("parsing", "parsing JSONL events"):
            all_events = distiller.parse_jsonl(location.path)
        with em.phase("filtering", f"filtering to last {lookback_minutes}m"):
            recent = distiller.filter_recent(all_events, lookback_minutes, max_events)
        em.emit(
            "events.windowed",
            f"{len(recent)} events in window",
            in_window=len(recent),
            total=len(all_events),
        )

        # ---- distill + repo state ---------------------------------------
        with em.phase("distilling", "building trajectory"):
            traj = distiller.distill(recent)
        with em.phase("collecting_repo_state", "git status / branch / diff"):
            repo = (
                repo_state.collect(cwd, include_diff=include_diff)
                if include_repo_state
                else repo_state.RepoState(cwd=cwd)
            )

        # ---- redact + build packet --------------------------------------
        with em.phase("redacting", "building redacted packet"):
            pkt = packet.build_packet(
                goal=goal,
                mode=mode,
                lookback_minutes=lookback_minutes,
                session_path=str(location.path),
                trajectory=traj,
                repo=repo,
                question=question,
            )
        em.emit(
            "packet.built",
            "packet ready",
            files_touched=len(traj.files_touched),
            tool_failures=len(traj.tool_failures),
            loops_detected=len(traj.loops_detected),
        )

        result: dict[str, Any] = {
            "session": {
                "path": str(location.path),
                "session_id": location.session_id,
                "discovery": location.source,
                "events_in_window": len(recent),
                "total_events": len(all_events),
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
            em.emit("run.done", "dry-run complete (no model call)")
            result["guidance"] = None
            return result

        # ---- consult model ---------------------------------------------
        with em.phase("asking_model", f"asking {model}", model=model):
            guidance = openrouter.ask(pkt, api_key=api_key, model=model)
        em.emit(
            "guidance.received",
            "guidance returned",
            hypotheses=len(guidance.get("hypotheses", []) or []),
            decision=guidance.get("decision"),
            confidence=guidance.get("confidence"),
        )
        result["guidance"] = guidance
        em.emit("run.done", "cept run done")
        return result

    except Exception as e:
        em.emit("run.error", str(e), level="error", error_type=type(e).__name__)
        raise
    finally:
        # If we own the emitter, close adapters; if caller passed one, leave it.
        if emitter is None:
            em.close()


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
