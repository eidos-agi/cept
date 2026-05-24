import json
from pathlib import Path

from cept import cli


def test_self_assess_uses_cept_defaults_with_file_transcript(tmp_path: Path, capsys) -> None:
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-23T12:00:00+00:00",
                "role": "user",
                "text": "should cept use adapters?",
                "cwd": str(tmp_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    code = cli.main(
        [
            "--self-assess",
            "--transcript",
            str(transcript),
            "--cwd",
            str(tmp_path),
            "--dry-run",
            "--quiet",
            "--no-repo-state",
        ]
    )

    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["headline"] == "assess cept design"
    assert out["packet"]["meta"]["mode"] == "architecture"
    assert out["session"]["adapter"] == "file"
    assert any(path.endswith("README.md") for path in out["packet"]["files"])


def test_cli_guide_prints_ceptkey_guide_without_goal(capsys) -> None:
    code = cli.main(["--guide", "ceptkey"])

    assert code == 0
    out = capsys.readouterr().out
    assert "# ceptkey guide" in out
    assert "OPENROUTER_API_KEY" in out


def test_cli_guide_defaults_to_ceptkey(capsys) -> None:
    code = cli.main(["--guide"])

    assert code == 0
    out = capsys.readouterr().out
    assert "# ceptkey guide" in out
    assert "OPENROUTER_API_KEY" in out


def test_cli_guide_path_prints_source_path(capsys) -> None:
    code = cli.main(["--guide", "ceptkey", "--guide-path"])

    assert code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("docs/CEPTKEY.md") or out == "(bundled guide resource)"
