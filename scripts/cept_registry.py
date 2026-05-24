#!/usr/bin/env python3
"""Registry/proof surface for Cept plugin storage."""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = PLUGIN_ROOT / "registry"
PROOFS_DIR = REGISTRY_DIR / "cept-proofs"


def load_toml(name: str) -> dict[str, Any]:
    with (REGISTRY_DIR / name).open("rb") as handle:
        return tomllib.load(handle)


def registry() -> dict[str, Any]:
    return {"stores": load_toml("storage.toml").get("stores", [])}


def emit(data: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(data)


def _expand_path(raw: str) -> Path:
    if raw.startswith("~/"):
        return Path.home() / raw[2:]
    path = Path(raw)
    if not path.is_absolute():
        path = PLUGIN_ROOT / path
    return path


def checks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stores = {store["id"]: store for store in registry()["stores"]}

    def add(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    source = PLUGIN_ROOT
    canonical_source = _expand_path(stores["source"]["path"])
    plugin_shim = _expand_path(stores["plugin-shim"]["path"])
    plugin_target = _expand_path(stores["plugin-shim"].get("target", stores["source"]["path"]))

    add("source-exists", source.exists(), str(source))
    add("canonical-source-exists", canonical_source.exists(), str(canonical_source))
    add(
        "plugin-shim",
        plugin_shim.exists() and plugin_shim.resolve() == plugin_target.resolve(),
        f"{plugin_shim} -> {plugin_shim.resolve() if plugin_shim.exists() else '(missing)'}",
    )
    add("ceptkey-guide", (source / "docs" / "CEPTKEY.md").exists(), "docs/CEPTKEY.md")
    add("eidos-playbook", (source / "eidos-plugin" / "cept" / "playbook.md").exists(), "eidos-plugin/cept/playbook.md")
    add("registry", (source / "registry" / "storage.toml").exists(), "registry/storage.toml")

    proc = subprocess.run(
        ["cept-cli", "--help"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    help_text = proc.stdout + proc.stderr
    add("cept-cli", proc.returncode == 0, "cept-cli --help")
    add("guide-flag", "--guide" in help_text, "cept-cli exposes --guide")
    add("self-assess-flag", "--self-assess" in help_text, "cept-cli exposes --self-assess")
    return rows


def cmd_registry(args: argparse.Namespace) -> None:
    emit(registry(), as_json=args.json)


def cmd_stores(args: argparse.Namespace) -> None:
    stores = registry()["stores"]
    if args.json:
        emit(stores, as_json=True)
        return
    for store in stores:
        print(f"{store['id']}: {store['kind']} {store['path']}")


def cmd_doctor(args: argparse.Namespace) -> None:
    rows = checks()
    data = {"ok": all(row["ok"] for row in rows), "checks": rows}
    if args.json:
        emit(data, as_json=True)
        return
    print("Cept registry doctor")
    for row in rows:
        marker = "ok" if row["ok"] else "fail"
        print(f"- {marker}: {row['name']} - {row['detail']}")


def cmd_proof(args: argparse.Namespace) -> None:
    rows = checks()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": all(row["ok"] for row in rows),
        "checks": rows,
    }
    PROOFS_DIR.mkdir(parents=True, exist_ok=True)
    proof_path = PROOFS_DIR / f"{datetime.now(timezone.utc).date().isoformat()}.jsonl"
    with proof_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    record["proof_path"] = str(proof_path)
    emit(record, as_json=args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cept-registry")
    sub = parser.add_subparsers(dest="command", required=True)

    registry_parser = sub.add_parser("registry")
    registry_parser.add_argument("--json", action="store_true")
    registry_parser.set_defaults(func=cmd_registry)

    stores_parser = sub.add_parser("stores")
    stores_parser.add_argument("--json", action="store_true")
    stores_parser.set_defaults(func=cmd_stores)

    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=cmd_doctor)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--json", action="store_true")
    proof_parser.set_defaults(func=cmd_proof)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
