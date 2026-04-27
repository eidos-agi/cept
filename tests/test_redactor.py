from __future__ import annotations

import os

from cept import redactor


def test_redacts_api_keys() -> None:
    s = "key=sk-live-abcd1234567890efghij call=pplx-" + "a" * 40
    out = redactor.redact_text(s)
    assert "sk-live-" not in out
    assert "pplx-" not in out
    assert "[REDACTED_API_KEY]" in out
    assert "[REDACTED_PPLX_KEY]" in out


def test_redacts_bearer_and_jwt() -> None:
    s = "Authorization: Bearer eyJhbGci.eyJzdWIi.signature"
    out = redactor.redact_text(s)
    assert "[REDACTED_JWT]" in out or "Bearer [REDACTED_TOKEN]" in out
    assert "eyJhbGci.eyJzdWIi.signature" not in out


def test_redacts_email() -> None:
    out = redactor.redact_text("contact alice@example.com today")
    assert "alice@example.com" not in out
    assert "[REDACTED_EMAIL]" in out


def test_redacts_env_assignments() -> None:
    out = redactor.redact_text("DATABASE_PASSWORD=hunter2hunter2 OPENAI_API_KEY=abcdefghij")
    assert "hunter2hunter2" not in out
    assert "abcdefghij" not in out
    assert "DATABASE_PASSWORD=[REDACTED]" in out
    assert "OPENAI_API_KEY=[REDACTED]" in out


def test_redacts_basic_auth_url() -> None:
    out = redactor.redact_text("https://user:supersecret@host.com/path")
    assert "supersecret" not in out
    assert "[REDACTED]" in out


def test_replaces_home_path() -> None:
    home = os.path.expanduser("~")
    if home == "/":
        return
    out = redactor.redact_text(f"opening {home}/secrets/.env")
    assert home not in out
    assert "~/secrets" in out


def test_redact_obj_recurses() -> None:
    obj = {
        "a": "Bearer eyJhbGci.payload.sig",
        "b": ["ghp_" + "a" * 30, {"c": "alice@example.com"}],
    }
    out = redactor.redact_obj(obj)
    assert "Bearer" in out["a"] and "[REDACTED" in out["a"]
    assert "[REDACTED_GH_TOKEN]" in out["b"][0]
    assert out["b"][1]["c"] == "[REDACTED_EMAIL]"
