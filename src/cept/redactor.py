"""Redact secrets and sensitive paths before anything leaves the machine."""

from __future__ import annotations

import os
import re
from typing import Any

_HOME = os.path.expanduser("~")

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Provider-prefixed API keys
    (re.compile(r"\bsk-(?:live|test|proj|ant|or)-[A-Za-z0-9_\-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bpplx-[A-Za-z0-9]{32,}\b"), "[REDACTED_PPLX_KEY]"),
    (re.compile(r"\bxoxb-[A-Za-z0-9\-]{20,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GH_TOKEN]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY_ID]"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY_ID]"),
    # Bearer tokens / JWT-shaped strings
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.I), "Bearer [REDACTED_TOKEN]"),
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}\b"),
        "[REDACTED_JWT]",
    ),
    # PEM blocks
    (
        re.compile(
            r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----",
            re.S,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # KEY=value style env assignments (any *_KEY, *_TOKEN, *_SECRET, *_PASSWORD)
    (
        re.compile(
            r"\b([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASS|PWD))\s*=\s*([^\s'\"]{6,})"
        ),
        r"\1=[REDACTED]",
    ),
    # Basic-auth style URLs
    (re.compile(r"://([^:/\s]+):([^@/\s]+)@"), r"://\1:[REDACTED]@"),
    # Long hex strings (likely hashes/keys, leave short ones alone)
    (re.compile(r"\b[a-f0-9]{40,}\b"), "[REDACTED_HEX]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, replacement in _PATTERNS:
        out = pat.sub(replacement, out)
    if _HOME and _HOME != "/":
        out = out.replace(_HOME, "~")
    return out


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    return obj
