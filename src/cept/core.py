"""End-to-end pipeline: load transcript → distill → repo state → packet → model."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import adapters, distiller, events, keyfile, packet, providers, repo_state
from .files import collect_files, to_packet_field

# Headline contract: the calling agent must compress its ask to ~3-4 words.
# Soft cap (4) earns a warning; hard cap (6) truncates. The discipline is the
# point — proprioception starts before the call, not after. See cept#5.
HEADLINE_SOFT_CAP_WORDS = 4
HEADLINE_HARD_CAP_WORDS = 6


def _validate_headline(raw: str) -> tuple[str, str | None]:
    """Return (cleaned, warning). Empty raises ValueError."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError(
            "headline is required — pass 3-4 words describing what you're asking. "
            "If you can't compress the ask to a phrase, you're not clear on what you need."
        )
    words = cleaned.split()
    if len(words) > HEADLINE_HARD_CAP_WORDS:
        cleaned = " ".join(words[:HEADLINE_HARD_CAP_WORDS]) + "…"
        return cleaned, f"headline truncated to {HEADLINE_HARD_CAP_WORDS} words"
    if len(words) > HEADLINE_SOFT_CAP_WORDS:
        return cleaned, f"headline is {len(words)} words; aim for {HEADLINE_SOFT_CAP_WORDS} or fewer"
    return cleaned, None


def run_cept(
    *,
    goal: str,
    headline: str,
    cwd: str | Path | None = None,
    lookback_minutes: int | None = None,
    max_events: int = 250,
    mode: str = "steer",
    transcript: str | Path | None = None,
    transcript_source: str = "auto",
    session_id: str | None = None,
    cept_id: str | None = None,
    include_repo_state: bool = True,
    include_diff: bool = True,
    question: str | None = None,
    files: list[str] | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    emitter: events.Emitter | None = None,
) -> dict[str, Any]:
    cwd = str(cwd or os.getcwd())
    em = emitter or events.Emitter()

    headline, headline_warning = _validate_headline(headline)
    # Fire the headline FIRST so the HUD has it before any other event lands —
    # the popup shows what's being asked while the rest of the pipeline runs.
    em.emit("request.headline", headline, headline=headline)
    if headline_warning:
        em.emit("request.headline.warn", headline_warning, level="warn")

    em.emit("run.start", "cept run started", goal=goal, mode=mode, cwd=cwd, headline=headline)

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
        selected_provider = providers.resolve_provider(
            provider,
            model,
            api_key=api_key,
            require_api_key=not dry_run,
        )

        # ---- load active transcript -------------------------------------
        with em.phase(
            "locating",
            "loading active transcript",
            adapter=transcript_source,
            cept_id=cept_id,
        ):
            loaded = adapters.load_transcript(
                cwd=cwd,
                transcript=transcript,
                source=transcript_source,
                session_id=session_id,
                cept_id=cept_id,
            )
        em.emit(
            "session.found",
            loaded.path.name,
            adapter=loaded.adapter,
            session_id=loaded.session_id,
            discovery=loaded.source,
            verified=(loaded.source == "cept_id"),
        )

        # ---- parse + filter ---------------------------------------------
        with em.phase("parsing", "normalizing transcript events"):
            all_events = loaded.events
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

        # ---- read caller-supplied source files --------------------------
        file_entries = []
        if files:
            with em.phase(
                "reading_files", f"reading {len(files)} source file(s)", count=len(files)
            ):
                file_entries = collect_files(files, cwd=cwd)
            included = sum(1 for e in file_entries if e.content is not None)
            truncated = sum(1 for e in file_entries if e.truncated)
            errored = sum(1 for e in file_entries if e.error)
            em.emit(
                "files.read",
                f"{included}/{len(file_entries)} files included",
                requested=len(files),
                included=included,
                truncated=truncated,
                errored=errored,
            )

        # ---- redact + build packet --------------------------------------
        with em.phase("redacting", "building redacted packet"):
            pkt = packet.build_packet(
                goal=goal,
                headline=headline,
                mode=mode,
                lookback_minutes=lookback_minutes,
                session_path=str(loaded.path),
                trajectory=traj,
                repo=repo,
                question=question,
                files=to_packet_field(file_entries) if file_entries else None,
            )
        em.emit(
            "packet.built",
            "packet ready",
            files_touched=len(traj.files_touched),
            tool_failures=len(traj.tool_failures),
            loops_detected=len(traj.loops_detected),
            files_included=sum(1 for e in file_entries if e.content is not None),
        )

        result: dict[str, Any] = {
            "headline": headline,
            "session": {
                "adapter": loaded.adapter,
                "path": str(loaded.path),
                "session_id": loaded.session_id,
                "discovery": loaded.source,
                "events_in_window": len(recent),
                "total_events": len(all_events),
            },
            "keyfile": {
                "path": str(keyfile_result.path) if keyfile_result.path else None,
                "keys_set": keyfile_result.keys_set,
                "metadata": keyfile_result.metadata,
            },
            "config": {
                "provider": selected_provider.name,
                "model": selected_provider.model,
                "lookback_minutes": lookback_minutes,
            },
            "packet": pkt,
        }

        if dry_run:
            em.emit("run.done", "dry-run complete (no model call)")
            result["guidance"] = None
            return result

        # ---- consult model ---------------------------------------------
        with em.phase(
            "asking_model",
            f"asking {selected_provider.name}/{selected_provider.model}",
            provider=selected_provider.name,
            model=selected_provider.model,
        ):
            guidance = providers.ask(
                pkt,
                provider=selected_provider.name,
                model=selected_provider.model,
                api_key=selected_provider.api_key,
            )
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
