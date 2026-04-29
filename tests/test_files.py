from __future__ import annotations

from pathlib import Path

from cept import files


def test_collect_files_reads_relative_and_absolute(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    a.write_text("hello world\nline two\n")
    b = tmp_path / "sub" / "b.txt"
    b.parent.mkdir()
    b.write_text("nested\n")

    entries = files.collect_files(["a.md", str(b)], cwd=tmp_path)
    by_path = {e.path: e for e in entries}

    assert by_path["a.md"].content == "hello world\nline two\n"
    assert by_path["a.md"].error is None
    assert by_path["a.md"].line_count == 2
    assert by_path[str(b)].content == "nested\n"


def test_collect_files_truncates_at_per_file_cap(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("A" * 200_000)

    entries = files.collect_files(["big.txt"], cwd=tmp_path, per_file_cap=1024)
    e = entries[0]
    assert e.truncated is True
    assert e.bytes_total == 200_000
    assert e.bytes_included == 1024
    assert "[truncated by cept" in (e.content or "")


def test_collect_files_handles_missing(tmp_path: Path) -> None:
    entries = files.collect_files(["nope.md"], cwd=tmp_path)
    assert entries[0].error == "file not found"
    assert entries[0].content is None


def test_collect_files_skips_binary(tmp_path: Path) -> None:
    bin_path = tmp_path / "blob.bin"
    bin_path.write_bytes(b"\x00\x01\x02hello")
    entries = files.collect_files(["blob.bin"], cwd=tmp_path)
    assert entries[0].content is None
    assert "binary file" in (entries[0].error or "")


def test_collect_files_dedupes_same_resolved_path(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    a.write_text("x\n")
    entries = files.collect_files(["a.md", str(a)], cwd=tmp_path)
    assert len(entries) == 1
    # First spelling wins.
    assert entries[0].path == "a.md"


def test_collect_files_enforces_total_cap(tmp_path: Path) -> None:
    for i in range(4):
        (tmp_path / f"f{i}.txt").write_text("x" * 1000)
    entries = files.collect_files(
        [f"f{i}.txt" for i in range(4)],
        cwd=tmp_path,
        per_file_cap=1000,
        total_cap=1500,
    )
    included = [e for e in entries if e.content is not None]
    skipped = [e for e in entries if e.error and "cap" in e.error]
    assert len(included) >= 1
    assert len(skipped) >= 1


def test_collect_files_max_files_skips_extras(tmp_path: Path) -> None:
    paths = []
    for i in range(5):
        p = tmp_path / f"f{i}.txt"
        p.write_text("x")
        paths.append(p.name)

    entries = files.collect_files(paths, cwd=tmp_path, max_files=2)
    included = [e for e in entries if e.content is not None]
    skipped = [e for e in entries if e.error and "max_files" in (e.error or "")]
    assert len(included) == 2
    assert len(skipped) == 3


def test_collect_files_empty_input_returns_empty() -> None:
    assert files.collect_files(None, cwd=".") == []
    assert files.collect_files([], cwd=".") == []


def test_to_packet_field_keys_by_caller_path(tmp_path: Path) -> None:
    a = tmp_path / "a.md"
    a.write_text("hi\n")
    entries = files.collect_files(["a.md"], cwd=tmp_path)
    field = files.to_packet_field(entries)
    assert "a.md" in field
    assert field["a.md"]["content"] == "hi\n"
    assert field["a.md"]["truncated"] is False
