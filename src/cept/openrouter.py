"""OpenRouter client — sends the redacted steering packet, returns structured guidance.

OpenRouter exposes an OpenAI-compatible chat-completions endpoint that routes to
many backends, so cept can use Perplexity's grounded Sonar family through one
stable provider surface. Default is ``perplexity/sonar-pro``.

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


BASE_SYSTEM_PROMPT = (
    "You are helping an AI coding agent with proprioception: a grounded sense "
    "of its own recent work, trajectory, uncertainty, and next move. You are "
    "reviewing a redacted work packet from that agent. "
    "Stay evidence-bound: separate what the packet shows from what you infer, "
    "and say when evidence is too thin. Do not assume the agent is looping, "
    "wrong, or safe to continue unless the packet supports it. Prefer concrete "
    "next checks over generic advice. Return only JSON matching the requested schema."
)

MODE_INSTRUCTIONS = {
    "steer": (
        "Look for blind spots, missing verification, stale assumptions, and better next checks. "
        "Recommend one next step, but include uncertainty through confidence and facts_to_verify."
    ),
    "debug": (
        "Rank plausible root causes from the observed evidence. Prefer experiments that would "
        "disconfirm the leading hypothesis quickly."
    ),
    "research": (
        "Identify external facts, docs, release/version issues, and citations relevant to the work. "
        "Prefer primary sources and mark any unsupported claim as something to verify."
    ),
    "architecture": (
        "Compare viable design alternatives and their tradeoffs. Call out missing constraints, "
        "migration risk, and reversibility."
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

    body = build_request_body(packet, model=model)

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


def build_request_body(packet: dict[str, Any], *, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    mode = str(packet.get("meta", {}).get("mode") or "steer")
    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["steer"])
    system = f"{BASE_SYSTEM_PROMPT} Mode: {mode}. {mode_instruction}"

    files_note = (
        "\n\nThe packet includes source files supplied by the calling agent for self-review. "
        "When citing file-specific issues, include path and line range where possible."
        if packet.get("files")
        else ""
    )
    user_payload = (
        "Review this redacted cept packet. Use the packet as evidence, not as a script. "
        "If the packet lacks enough signal, say so in the summary and make the next step a "
        "verification step."
        + files_note
        + "\n\n"
        + f"```json\n{json.dumps(packet, indent=2)}\n```"
    )

    return {
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
