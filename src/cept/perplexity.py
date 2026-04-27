"""Perplexity client — sends the redacted steering packet, returns structured guidance."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


PPLX_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar-reasoning"


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


class PerplexityError(RuntimeError):
    pass


def ask(
    packet: dict[str, Any],
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 60.0,
) -> dict[str, Any]:
    api_key = api_key or os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise PerplexityError("PERPLEXITY_API_KEY not set.")

    mode = packet.get("meta", {}).get("mode", "steer")
    system = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["steer"])

    user_payload = (
        "Here is a redacted steering packet from the agent's recent trajectory. "
        "Respond as JSON matching the requested schema.\n\n"
        f"```json\n{json.dumps(packet, indent=2)}\n```"
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_payload},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": RESPONSE_SCHEMA},
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(PPLX_URL, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise PerplexityError(f"Perplexity request failed: {e}") from e

    if resp.status_code >= 400:
        raise PerplexityError(f"Perplexity {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise PerplexityError(f"Unexpected Perplexity response shape: {data}") from e

    citations = data.get("citations") or []

    parsed = _parse_json_content(content)
    parsed.setdefault("citations", citations)
    return parsed


def _parse_json_content(content: str) -> dict[str, Any]:
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
