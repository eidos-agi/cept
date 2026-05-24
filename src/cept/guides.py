"""CLI access to bundled cept guides."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


class GuideError(RuntimeError):
    pass


def guide_path(name: str) -> Path | None:
    if name != "ceptkey":
        raise GuideError(f"unknown guide {name!r}")

    source_path = Path(__file__).resolve().parents[2] / "docs" / "CEPTKEY.md"
    if source_path.exists():
        return source_path
    return None


def read_guide(name: str) -> str:
    if name != "ceptkey":
        raise GuideError(f"unknown guide {name!r}")

    source_path = guide_path(name)
    if source_path:
        return source_path.read_text(encoding="utf-8")

    try:
        return resources.files("cept").joinpath("guides/CEPTKEY.md").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as e:
        raise GuideError("ceptkey guide is not available in this install") from e
