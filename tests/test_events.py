from __future__ import annotations

import io
import json
import socket as socketlib
import threading
from pathlib import Path

import pytest

from cept import events


def test_event_jsonl_round_trips() -> None:
    ev = events.Event(
        run_id="abc",
        seq=3,
        ts="2026-04-27T00:00:00Z",
        phase="locating",
        level="info",
        msg="hi",
        data={"k": 1},
    )
    out = json.loads(ev.to_jsonl())
    assert out == ev.to_dict()


def test_event_text_includes_phase_and_msg() -> None:
    ev = events.Event(run_id="r", seq=1, ts="t", phase="locating", msg="finding session")
    text = ev.to_text()
    assert "locating" in text
    assert "finding session" in text


def test_stdout_adapter_text_format() -> None:
    buf = io.StringIO()
    a = events.StdoutAdapter(jsonl=False, stream=buf)
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="locating", msg="hi"))
    a.close()
    assert "locating" in buf.getvalue()
    assert "hi" in buf.getvalue()


def test_stdout_adapter_jsonl_format() -> None:
    buf = io.StringIO()
    a = events.StdoutAdapter(jsonl=True, stream=buf)
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="x", msg="m"))
    parsed = json.loads(buf.getvalue().strip())
    assert parsed["phase"] == "x"
    assert parsed["msg"] == "m"


def test_file_adapter_appends_jsonl(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    a = events.FileAdapter(log)
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="a", msg="1"))
    a.emit(events.Event(run_id="r", seq=2, ts="t", phase="b", msg="2"))
    a.close()
    lines = log.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "a"
    assert json.loads(lines[1])["phase"] == "b"


def test_socket_adapter_no_op_when_socket_missing() -> None:
    a = events.SocketAdapter("/tmp/cept-no-such-socket.sock")
    # Should not raise even though connect failed.
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="x"))
    a.close()


def test_socket_adapter_writes_when_listener_present() -> None:
    # macOS AF_UNIX paths cap at 104 chars — pytest tmp_path is too deep.
    import os
    import tempfile

    sock_dir = tempfile.mkdtemp(prefix="cept-", dir="/tmp")
    sock_path = Path(sock_dir) / "t.sock"
    received: list[str] = []
    ready = threading.Event()

    def server() -> None:
        srv = socketlib.socket(socketlib.AF_UNIX, socketlib.SOCK_STREAM)
        srv.bind(str(sock_path))
        srv.listen(1)
        ready.set()
        srv.settimeout(3.0)
        try:
            conn, _ = srv.accept()
        except (TimeoutError, OSError):
            srv.close()
            return
        conn.settimeout(3.0)
        buf = b""
        try:
            # Read until client closes (EOF) or read times out.
            while True:
                try:
                    chunk = conn.recv(4096)
                except (TimeoutError, OSError):
                    break
                if not chunk:
                    break
                buf += chunk
        finally:
            conn.close()
            srv.close()
        for line in buf.decode().splitlines():
            if line.strip():
                received.append(line)

    t = threading.Thread(target=server, daemon=True)
    t.start()
    assert ready.wait(3.0)

    a = events.SocketAdapter(sock_path)
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="hello", msg="world"))
    a.close()
    t.join(5.0)

    # Cleanup
    try:
        os.unlink(sock_path)
        os.rmdir(sock_dir)
    except OSError:
        pass

    assert any("hello" in line for line in received)


def test_noop_adapter_silently_drops() -> None:
    a = events.NoopAdapter()
    a.emit(events.Event(run_id="r", seq=1, ts="t", phase="x"))
    a.close()


def test_emitter_phase_emits_start_and_done() -> None:
    captured: list[events.Event] = []

    class Capture:
        def emit(self, ev: events.Event) -> None:
            captured.append(ev)

        def close(self) -> None:
            pass

    em = events.Emitter(adapters=[Capture()])
    with em.phase("locating", "looking…"):
        pass

    assert len(captured) == 2
    assert captured[0].phase == "locating"
    assert captured[1].phase == "locating.done"
    assert "duration_ms" in captured[1].data


def test_emitter_phase_emits_error_on_exception() -> None:
    captured: list[events.Event] = []

    class Capture:
        def emit(self, ev: events.Event) -> None:
            captured.append(ev)

        def close(self) -> None:
            pass

    em = events.Emitter(adapters=[Capture()])
    with pytest.raises(RuntimeError):
        with em.phase("asking_model"):
            raise RuntimeError("boom")

    assert len(captured) == 2
    assert captured[1].phase == "asking_model"
    assert captured[1].level == "error"
    assert "boom" in captured[1].msg


def test_emitter_seq_monotonic() -> None:
    em = events.Emitter()
    em.emit("a")
    em.emit("b")
    em.emit("c")
    assert em.seq == 3


def test_parse_emit_spec_known_strings() -> None:
    assert isinstance(events.parse_emit_spec("noop"), events.NoopAdapter)
    assert isinstance(events.parse_emit_spec("stdout"), events.StdoutAdapter)
    assert isinstance(events.parse_emit_spec("stderr"), events.StdoutAdapter)
    assert isinstance(events.parse_emit_spec("notify"), events.NotifyAdapter)


def test_parse_emit_spec_with_paths(tmp_path: Path) -> None:
    p = tmp_path / "log.jsonl"
    a = events.parse_emit_spec(f"file:{p}")
    assert isinstance(a, events.FileAdapter)
    a.close()


def test_parse_emit_spec_jsonl_paths(tmp_path: Path) -> None:
    a = events.parse_emit_spec("jsonl:-")
    assert isinstance(a, events.StdoutAdapter)
    assert a.jsonl is True

    p = tmp_path / "log.jsonl"
    a2 = events.parse_emit_spec(f"jsonl:{p}")
    assert isinstance(a2, events.FileAdapter)
    a2.close()


def test_parse_emit_spec_unknown_raises() -> None:
    with pytest.raises(ValueError):
        events.parse_emit_spec("schmemit:nope")


def test_parse_emit_specs_comma_split() -> None:
    adapters = events.parse_emit_specs("noop,stderr")
    assert len(adapters) == 2
    assert isinstance(adapters[0], events.NoopAdapter)
    assert isinstance(adapters[1], events.StdoutAdapter)
