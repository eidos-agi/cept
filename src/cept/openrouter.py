"""OpenRouter client — sends the redacted steering packet, returns structured guidance.

OpenRouter exposes an OpenAI-compatible chat-completions endpoint that routes to
many backends, so cept can pick a model with web search built in (Perplexity's
sonar family) without locking the user to a single provider. Default is
``perplexity/sonar-reasoning`` — same outside-in flavor that justified cept's
design, just routed through OpenRouter.

Append ``:online`` to any model name to force web search on backends that
support it (e.g. ``anthropic/claude-sonnet-4-5:online``).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "perplexity/sonar-pro"


SYSTEM_PROMPTS = {
    "steer": (
        "You are a senior staff engineer acting as the proprioceptive steering module for a coding agent. "
        "The agent has shared its recent trajectory. Your job: surface blind spots and propose the single best next move. "
        "Be specific. Cite docs when relevant. Avoid generic advice."
    ),
    "debug": (
        "You are a senior debugger. Rank the most likely root causes from the evidence, then propose the single "
        "highest-leverage next experiment. If the agent appears to be in a loop, say so explicitly."
    ),
    "research": (
        "You are a research assistant. Find external facts, version gotchas, and authoritative docs relevant to the agent's work. "
        "Prefer primary sources. Return citations."
    ),
    "architecture": (
        "You are a principal engineer reviewing an in-flight design choice. Compare alternatives, surface tradeoffs the agent has not "
        "considered, and recommend a direction with explicit reasoning."
    ),
}


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "is_looping": {"type": "boolean"},
        "blind_spots": {"type": "array", "items": {"type": "string"}},
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "confidence": {"type": "number"},
                    "why": {"type": "string"},
                },
                "required": ["title", "confidence", "why"],
            },
        },
        "recommended_next_step": {"type": "string"},
        "backup_step": {"type": "string"},
        "facts_to_verify": {"type": "array", "items": {"type": "string"}},
        "decision": {
            "type": "string",
            "enum": ["continue", "continue-with-adjustment", "backtrack", "reframe"],
        },
        "confidence": {"type": "number"},
    },
    "required": [
        "summary",
        "is_looping",
        "hypotheses",
        "recommended_next_step",
        "decision",
        "confidence",
    ],
}


class OpenRouterError(RuntimeError):
    pass


def ask(
    packet: dict[str, Any],
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 60.0,
    referer: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY not set.")

    mode = packet.get("meta", {}).get("mode", "steer")
    system = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["steer"])

    has_files = bool(packet.get("files"))
    files_note = (
        " The packet's `files` field contains the verbatim content of "
        "source files the calling agent wants critiqued. The agent is the "
        "owner of these files and is asking for help hardening their own "
        "deliverable — owner-positive framing applies even when the request "
        "uses adversarial language like \"audit\", \"red-team\", or \"find "
        "the holes\". This is not a third party requesting analysis of "
        "someone else's materials. When you cite an issue in a file, include "
        "the path and a line range (e.g. `README.md:42-48`) so the agent can "
        "navigate directly to it."
        if has_files
        else ""
    )
    user_payload = (
        "Here is a redacted steering packet from the agent's recent trajectory."
        + files_note
        + " Respond as JSON matching the requested schema.\n\n"
        + f"```json\n{json.dumps(packet, indent=2)}\n```"
    )

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "cept_guidance",
                "strict": True,
                "schema": RESPONSE_SCHEMA,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Optional OpenRouter ranking headers — recommended but not required.
    if referer or os.environ.get("OPENROUTER_REFERER"):
        headers["HTTP-Referer"] = referer or os.environ["OPENROUTER_REFERER"]
    if title or os.environ.get("OPENROUTER_TITLE"):
        headers["X-Title"] = title or os.environ.get("OPENROUTER_TITLE", "cept")

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(OPENROUTER_URL, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise OpenRouterError(f"OpenRouter request failed: {e}") from e

    if resp.status_code >= 400:
        raise OpenRouterError(f"OpenRouter {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        message = data["choices"][0]["message"]
        content = message.get("content", "")
    except (KeyError, IndexError, TypeError) as e:
        raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from e

    citations = data.get("citations") or message.get("citations") or []

    parsed = _parse_json_content(content)
    parsed.setdefault("citations", citations)
    parsed.setdefault("_model", model)
    refused, reason = detect_refusal(parsed)
    if refused:
        parsed["refused"] = True
        parsed["refusal_reason"] = reason
    return parsed


# Refusal detection: distinguish "model engaged with the packet and recommended
# backtracking" from "model declined to participate." cept's response shape is
# the same in both cases — `decision: backtrack, confidence: 0.88` — so without
# this layer the calling agent acts on the refusal as if it were guidance. See
# eidos-agi/cept#4 for the failure case that motivated this.

_REFUSAL_NEXT_STEP = re.compile(
    r"^\s*("
    r"decline|refuse|cannot|"
    r"won['’]?\s*t|will\s+not|do\s+not\s+(provide|engage|participate)|"
    r"i\s*[''’]?\s*m?\s*(unable|sorry|cannot|won['’]?\s*t|can['’]?\s*t)|"
    r"i\s+(refuse|decline|cannot|won['’]?t|can['’]?t)"
    r")\b",
    re.I,
)

_REFUSAL_PHRASES = (
    "test of whether",
    "decoy",
    "scaffolding to make",
    "third party",
    "bad actor",
    "jailbreak",
    "extract attacks",
    "manipulat",  # manipulate / manipulation / manipulating
    "i cannot provide",
    "i can't provide",
    "i won't provide",
    "i am unable",
    "i'm unable",
    "i refuse",
    "i decline",
    "not appropriate",
    "ethically problematic",
    "against my guidelines",
)


def detect_refusal(parsed: dict[str, Any]) -> tuple[bool, str | None]:
    """Heuristic: did the model refuse to engage with the packet?

    Returns (refused, reason). A refusal looks structurally like substantive
    guidance — decision/confidence/hypotheses are all populated — so callers
    must rely on this detector to tell the difference. False positives are
    far less costly than false negatives here: a real "backtrack" recommendation
    survives because it doesn't open with "decline/refuse" or contain
    refusal-shaped hypotheses.
    """
    next_step = str(parsed.get("recommended_next_step") or "")
    if next_step and _REFUSAL_NEXT_STEP.match(next_step):
        snippet = next_step[:80].rstrip()
        return True, f"recommended_next_step opens with refusal: {snippet!r}"

    summary = str(parsed.get("summary") or "").lower()
    for phrase in _REFUSAL_PHRASES:
        if phrase in summary:
            return True, f"summary contains refusal phrase {phrase!r}"

    matched: set[str] = set()
    for h in parsed.get("hypotheses") or []:
        if not isinstance(h, dict):
            continue
        text = (str(h.get("title", "")) + " " + str(h.get("why", ""))).lower()
        for phrase in _REFUSAL_PHRASES:
            if phrase in text:
                matched.add(phrase)
    if matched:
        return True, f"hypotheses contain refusal language: {sorted(matched)}"

    return False, None


def _parse_json_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        return {"summary": str(content), "raw": True}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {"summary": content, "raw": True}
