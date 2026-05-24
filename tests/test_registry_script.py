from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_registry_script_reports_storage_model() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cept_registry.py"), "registry", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    store_ids = {store["id"] for store in payload["stores"]}
    assert {"source", "plugin-shim", "event-log", "proofs", "keyfiles"} <= store_ids


def test_registry_doctor_is_machine_readable() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cept_registry.py"), "doctor", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert "ok" in payload
    assert {check["name"] for check in payload["checks"]} >= {
        "source-exists",
        "ceptkey-guide",
        "registry",
        "cept-cli",
    }
