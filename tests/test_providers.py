import pytest

from cept import openrouter, providers


def test_auto_provider_uses_openrouter_perplexity_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

    selected = providers.resolve_provider("auto")

    assert selected.name == "openrouter"
    assert selected.model == "perplexity/sonar-pro"
    assert selected.api_key == "or-key"


def test_auto_provider_missing_openrouter_key_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(providers.ProviderError, match="OPENROUTER_API_KEY"):
        providers.resolve_provider("auto")


def test_explicit_openrouter_preserves_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

    selected = providers.resolve_provider("openrouter", model="anthropic/claude-sonnet-4-5:online")

    assert selected.name == "openrouter"
    assert selected.model == "anthropic/claude-sonnet-4-5:online"
    assert selected.api_key == "or-key"


def test_provider_call_tags_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ask(packet, *, api_key=None, model=None):
        return {
            "summary": "ok",
            "is_looping": False,
            "hypotheses": [],
            "recommended_next_step": "continue",
            "decision": "continue",
            "confidence": 0.8,
            "_model": model,
        }

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setattr(openrouter, "ask", fake_ask)

    result = providers.ask({"meta": {"mode": "steer"}}, provider="auto")

    assert result["_provider"] == "openrouter"
    assert result["_model"] == "perplexity/sonar-pro"
