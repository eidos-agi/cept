"""Provider routing for cept model calls.

OpenRouter remains the provider surface for this pass. Grounding comes from the
default Perplexity Sonar model selected through OpenRouter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from . import openrouter

DEFAULT_PROVIDER = "auto"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class SelectedProvider:
    name: str
    model: str
    api_key: str


def resolve_provider(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    require_api_key: bool = True,
) -> SelectedProvider:
    selected = (provider or os.environ.get("CEPT_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if selected == "auto":
        selected = "openrouter"
    if selected != "openrouter":
        raise ProviderError(
            f"unsupported provider {provider!r}; this build supports 'auto' and 'openrouter'. "
            "Use OPENROUTER_API_KEY with a Perplexity model such as perplexity/sonar-pro."
        )

    resolved_api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not resolved_api_key and require_api_key:
        raise ProviderError(
            "OPENROUTER_API_KEY not set. cept uses OpenRouter Perplexity models for grounded "
            "answers in this build; native PERPLEXITY_API_KEY support is not wired."
        )
    return SelectedProvider(
        name="openrouter",
        model=model or os.environ.get("CEPT_DEFAULT_MODEL") or openrouter.DEFAULT_MODEL,
        api_key=resolved_api_key or "",
    )


def ask(
    packet: dict[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    selected = resolve_provider(provider, model, api_key=api_key)
    result = openrouter.ask(packet, api_key=selected.api_key, model=selected.model)
    result.setdefault("_model", selected.model)
    result["_provider"] = selected.name
    return result
