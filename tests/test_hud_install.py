from __future__ import annotations

from pathlib import Path

import pytest

from cept import hud_install


def test_find_source_dir_returns_real_path() -> None:
    """The cept repo ships hud/ next to src/ — the walker should find it."""
    src = hud_install.find_source_dir()
    assert src is not None
    assert (src / "Package.swift").is_file()


def test_find_source_dir_prefers_bundled_location(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Under a uvx/PyPI install the wheel ships hud/ as cept/_hud_source/.
    The resolver should pick that over walking up to a sibling source tree."""
    fake_pkg = tmp_path / "site-packages" / "cept"
    fake_pkg.mkdir(parents=True)
    (fake_pkg / "hud_install.py").write_text("# stub")
    bundled = fake_pkg / "_hud_source"
    bundled.mkdir()
    (bundled / "Package.swift").write_text("// stub")

    # Point the resolver at the fake package by patching __file__ via a
    # module-level attribute on a copy of the function logic.
    monkeypatch.setattr(hud_install, "__file__", str(fake_pkg / "hud_install.py"))
    src = hud_install.find_source_dir()
    assert src == bundled


def test_cache_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert hud_install.cache_dir() == tmp_path / "cept"


def test_ensure_explicit_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "my-hud"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)

    monkeypatch.setenv("CEPT_HUD_BIN", str(fake))
    # Ensure $PATH lookup is bypassed
    monkeypatch.setattr(hud_install.shutil, "which", lambda _: None)

    resolved = hud_install.ensure(log=False)
    assert resolved == fake


def test_ensure_falls_back_to_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CEPT_HUD_BIN", raising=False)
    fake = tmp_path / "cept-hud"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)

    monkeypatch.setattr(
        hud_install.shutil, "which", lambda name: str(fake) if name == "cept-hud" else None
    )
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "no-cache-here"))

    resolved = hud_install.ensure(log=False)
    assert resolved == fake


def test_ensure_uses_cache_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CEPT_HUD_BIN", raising=False)
    monkeypatch.setattr(hud_install.shutil, "which", lambda _: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    cache = tmp_path / "cept" / "cept-hud"
    cache.parent.mkdir(parents=True)
    cache.write_text("#!/bin/sh\nexit 0\n")
    cache.chmod(0o755)

    resolved = hud_install.ensure(log=False)
    assert resolved == cache


def test_ensure_returns_none_when_no_swift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No env var, no PATH binary, no cache, no swift compiler → None."""
    monkeypatch.delenv("CEPT_HUD_BIN", raising=False)
    monkeypatch.setattr(hud_install.shutil, "which", lambda _: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    resolved = hud_install.ensure(log=False)
    assert resolved is None
