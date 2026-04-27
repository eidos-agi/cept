from __future__ import annotations

from pathlib import Path

import pytest

from cept import keyfile


def test_find_keyfile_in_cwd(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    project = home / "proj"
    project.mkdir()
    (project / ".ceptkey").write_text("OPENROUTER_API_KEY=x\n")

    found = keyfile.find_keyfile(project, home=home)
    assert found == project / ".ceptkey"


def test_find_keyfile_walks_up(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    root = home / "clientA"
    deep = root / "service" / "src" / "auth"
    deep.mkdir(parents=True)
    (root / ".ceptkey").write_text("OPENROUTER_API_KEY=client-a\n")

    found = keyfile.find_keyfile(deep, home=home)
    assert found == root / ".ceptkey"


def test_find_keyfile_prefers_dotted_name(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (proj / ".ceptkey").write_text("KEY=dotted\n")
    (proj / "ceptkey").write_text("KEY=plain\n")

    found = keyfile.find_keyfile(proj, home=home)
    assert found is not None
    assert found.name == ".ceptkey"


def test_find_keyfile_falls_back_to_plain_name(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (proj / "ceptkey").write_text("KEY=plain\n")

    found = keyfile.find_keyfile(proj, home=home)
    assert found is not None
    assert found.name == "ceptkey"


def test_find_keyfile_stops_at_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = home / "p"
    proj.mkdir(parents=True)
    # File above home — should NOT be found.
    (tmp_path / ".ceptkey").write_text("KEY=outside\n")

    found = keyfile.find_keyfile(proj, home=home)
    assert found is None


def test_find_keyfile_checks_home_itself(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (home / ".ceptkey").write_text("KEY=home\n")

    found = keyfile.find_keyfile(proj, home=home)
    assert found == home / ".ceptkey"


def test_find_keyfile_outside_home_walks_to_root(tmp_path: Path) -> None:
    """If cwd isn't under $HOME, walk to filesystem root instead of stopping early."""
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "elsewhere" / "deep"
    outside.mkdir(parents=True)
    (tmp_path / "elsewhere" / ".ceptkey").write_text("KEY=outside\n")

    found = keyfile.find_keyfile(outside, home=home)
    assert found == tmp_path / "elsewhere" / ".ceptkey"


def test_find_keyfile_returns_none_when_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = home / "p"
    proj.mkdir(parents=True)
    found = keyfile.find_keyfile(proj, home=home)
    assert found is None


def test_parse_keyfile_handles_basic_lines(tmp_path: Path) -> None:
    f = tmp_path / ".ceptkey"
    f.write_text(
        "OPENROUTER_API_KEY=sk-or-abc\n"
        "CEPT_DEFAULT_MODEL=openai/gpt-5:online\n"
        "CEPT_LOOKBACK_MINUTES=10\n"
    )
    parsed = keyfile.parse_keyfile(f)
    assert parsed.values["OPENROUTER_API_KEY"] == "sk-or-abc"
    assert parsed.values["CEPT_DEFAULT_MODEL"] == "openai/gpt-5:online"
    assert parsed.values["CEPT_LOOKBACK_MINUTES"] == "10"
    assert parsed.metadata == {}


def test_parse_keyfile_handles_quotes_comments_export(tmp_path: Path) -> None:
    f = tmp_path / ".ceptkey"
    f.write_text(
        "# top comment\n"
        "\n"
        '  export OPENROUTER_API_KEY="quoted-value"\n'
        "OPENROUTER_TITLE='single quoted'\n"
        "# another comment\n"
        "BAREWORD=no-quotes\n"
    )
    parsed = keyfile.parse_keyfile(f)
    assert parsed.values["OPENROUTER_API_KEY"] == "quoted-value"
    assert parsed.values["OPENROUTER_TITLE"] == "single quoted"
    assert parsed.values["BAREWORD"] == "no-quotes"


def test_parse_keyfile_extracts_metadata(tmp_path: Path) -> None:
    f = tmp_path / ".ceptkey"
    f.write_text(
        "# cept-meta:service=openrouter\n"
        "# cept-meta:key_name=cept-djs-01\n"
        "# cept-meta:created_at=2026-04-27T13:13:00+00:00\n"
        "# cept-meta:created_on=daniels-mbp\n"
        "# cept-meta:created_by=dev@example.com\n"
        '# cept-meta:notes="Eidos AGI shared key"\n'
        "# regular comment, ignored\n"
        "\n"
        "OPENROUTER_API_KEY=sk-or-test\n"
    )
    parsed = keyfile.parse_keyfile(f)
    assert parsed.values == {"OPENROUTER_API_KEY": "sk-or-test"}
    assert parsed.metadata["service"] == "openrouter"
    assert parsed.metadata["key_name"] == "cept-djs-01"
    assert parsed.metadata["created_at"] == "2026-04-27T13:13:00+00:00"
    assert parsed.metadata["created_on"] == "daniels-mbp"
    assert parsed.metadata["created_by"] == "dev@example.com"
    assert parsed.metadata["notes"] == "Eidos AGI shared key"


def test_metadata_is_not_applied_to_env(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = home / "p"
    proj.mkdir(parents=True)
    (proj / ".ceptkey").write_text(
        "# cept-meta:service=openrouter\n"
        "# cept-meta:key_name=test-key\n"
        "OPENROUTER_API_KEY=sk-or-test\n"
    )
    env: dict[str, str] = {}
    result = keyfile.load_for(proj, env=env, home=home)
    assert env == {"OPENROUTER_API_KEY": "sk-or-test"}
    assert "service" not in env
    assert result.metadata == {"service": "openrouter", "key_name": "test-key"}


def test_apply_overrides_existing_env_file_wins(tmp_path: Path) -> None:
    env: dict[str, str] = {"OPENROUTER_API_KEY": "global-key"}
    keys = keyfile.apply({"OPENROUTER_API_KEY": "project-key"}, env=env)
    assert env["OPENROUTER_API_KEY"] == "project-key"
    assert keys == ["OPENROUTER_API_KEY"]


def test_load_for_end_to_end(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "clientA" / "service"
    proj.mkdir(parents=True)
    (home / "clientA" / ".ceptkey").write_text(
        "# cept-meta:service=openrouter\n"
        "# cept-meta:key_name=client-a\n"
        "OPENROUTER_API_KEY=client-a-key\n"
        "CEPT_DEFAULT_MODEL=anthropic/claude-sonnet-4-5:online\n"
    )

    env: dict[str, str] = {"OPENROUTER_API_KEY": "global"}
    result = keyfile.load_for(proj, env=env, home=home)

    assert result.path == home / "clientA" / ".ceptkey"
    assert "OPENROUTER_API_KEY" in result.keys_set
    assert env["OPENROUTER_API_KEY"] == "client-a-key"  # file won
    assert env["CEPT_DEFAULT_MODEL"] == "anthropic/claude-sonnet-4-5:online"
    assert result.metadata["key_name"] == "client-a"


def test_load_for_no_keyfile(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = home / "p"
    proj.mkdir(parents=True)
    env: dict[str, str] = {}
    result = keyfile.load_for(proj, env=env, home=home)
    assert result.path is None
    assert result.keys_set == []
    assert env == {}


@pytest.mark.parametrize("name", [".ceptkey", "ceptkey"])
def test_both_filenames_recognized(tmp_path: Path, name: str) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / "p"
    proj.mkdir()
    (proj / name).write_text("OPENROUTER_API_KEY=k\n")

    found = keyfile.find_keyfile(proj, home=home)
    assert found is not None
    assert found.name == name
