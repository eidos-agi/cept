from __future__ import annotations

from pathlib import Path

import pytest

from cept import keyfile, keyfile_cli


def test_init_writes_metadata_and_body(tmp_path: Path) -> None:
    target = tmp_path / ".ceptkey"
    rc = keyfile_cli.main(
        [
            "init",
            "--service",
            "openrouter",
            "--name",
            "cept-djs-01",
            "--key",
            "sk-or-test-abc",
            "--provider",
            "openrouter",
            "--model",
            "openai/gpt-5:online",
            "--lookback",
            "15",
            "--scope",
            "~/repos-eidos-agi/",
            "--notes",
            "Eidos AGI shared",
            "--path",
            str(target),
        ]
    )
    assert rc == 0
    assert target.exists()
    parsed = keyfile.parse_keyfile(target)
    assert parsed.values["OPENROUTER_API_KEY"] == "sk-or-test-abc"
    assert parsed.values["CEPT_PROVIDER"] == "openrouter"
    assert parsed.values["CEPT_DEFAULT_MODEL"] == "openai/gpt-5:online"
    assert parsed.values["CEPT_LOOKBACK_MINUTES"] == "15"
    # Auto-populated metadata
    assert parsed.metadata["service"] == "openrouter"
    assert parsed.metadata["key_name"] == "cept-djs-01"
    assert "created_at" in parsed.metadata
    assert "created_on" in parsed.metadata
    assert "created_by" in parsed.metadata
    assert "created_os" in parsed.metadata
    assert parsed.metadata["scope"] == "~/repos-eidos-agi/"
    assert parsed.metadata["notes"] == "Eidos AGI shared"


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / ".ceptkey"
    target.write_text("existing\n")
    rc = keyfile_cli.main(["init", "--name", "k", "--key", "v", "--path", str(target)])
    assert rc == 2
    assert target.read_text() == "existing\n"


def test_init_overwrites_with_force(tmp_path: Path) -> None:
    target = tmp_path / ".ceptkey"
    target.write_text("existing\n")
    rc = keyfile_cli.main(["init", "--name", "k", "--key", "v", "--path", str(target), "--force"])
    assert rc == 0
    assert "existing" not in target.read_text()
    assert "OPENROUTER_API_KEY=v" in target.read_text()


def test_show_lists_metadata_without_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (proj / ".ceptkey").write_text(
        "# cept-meta:service=openrouter\n"
        "# cept-meta:key_name=demo\n"
        "OPENROUTER_API_KEY=should-not-appear\n"
    )
    rc = keyfile_cli.main(["show", "--cwd", str(proj), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "should-not-appear" not in out
    assert "OPENROUTER_API_KEY" in out  # name only
    assert "demo" in out  # metadata value


def test_where_prints_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (proj / ".ceptkey").write_text("OPENROUTER_API_KEY=x\n")
    rc = keyfile_cli.main(["where", "--cwd", str(proj)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(proj / ".ceptkey")


def test_guide_prints_ceptkey_guide(capsys: pytest.CaptureFixture[str]) -> None:
    rc = keyfile_cli.main(["guide"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "# ceptkey guide" in out
    assert "CEPT_PROVIDER" in out


def test_guide_path_prints_source_path(capsys: pytest.CaptureFixture[str]) -> None:
    rc = keyfile_cli.main(["guide", "--path"])

    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("docs/CEPTKEY.md") or out == "(bundled guide resource)"
