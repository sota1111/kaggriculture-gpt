#!/usr/bin/env python3
"""Re-anchor the tomato fork on hash-pinned public agents without consuming confirm."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tarfile
import tempfile
import zlib
from pathlib import Path
from typing import Any


FORBIDDEN_FEATURES = {"private_state", "episode_identity", "future_outcome"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sources = {row.get("id"): row for row in manifest.get("sources", [])}
    windows = manifest.get("panels", {})
    rows = {name: windows.get(name, []) for name in ("screen", "confirm")}
    dimensions = ("opponent", "source_hash", "seed", "time_utc", "episode")
    disjoint = {}
    for field in dimensions:
        screen = {row.get(field) for row in rows["screen"]}
        confirm = {row.get(field) for row in rows["confirm"]}
        disjoint[field] = None not in screen | confirm and screen.isdisjoint(confirm)
    seat_complete = all(row.get("seats") == [0, 1] for panel in rows.values() for row in panel)
    source_linked = all(
        row.get("opponent") in sources
        and row.get("source_hash") == sources[row["opponent"]].get("agent_sha256")
        for panel in rows.values() for row in panel
    )
    feature_policy = manifest.get("feature_policy", {})
    feature_keys = set(feature_policy.get("allowed", []))
    forbidden_declared = set(feature_policy.get("forbidden", []))
    row_leakage = any(
        key in FORBIDDEN_FEATURES
        for panel in rows.values() for row in panel for key in row
    )
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_exact": manifest.get("engine", {}).get("version") == "1.32.7",
        "acquisition_time_fixed": bool(manifest.get("acquired_at_utc")),
        "source_url_notebook_and_agent_hash_fixed": len(sources) == 3 and all(
            row.get("url") and row.get("notebook_sha256") and row.get("agent_sha256")
            for row in sources.values()
        ),
        "opponent_disjoint": disjoint["opponent"],
        "source_hash_disjoint": disjoint["source_hash"],
        "seed_disjoint": disjoint["seed"],
        "time_disjoint": disjoint["time_utc"],
        "episode_identity_disjoint": disjoint["episode"],
        "both_seats_declared": seat_complete,
        "panel_sources_match_pins": source_linked,
        "public_features_only": feature_keys == {"public_observation"},
        "forbidden_features_fail_closed": FORBIDDEN_FEATURES <= forbidden_declared and not row_leakage,
        "confirm_reserved": manifest.get("confirm_policy") == "reserved-for-SOT-2877",
        "no_submission": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    return {"passed": all(checks.values()), "checks": checks}


def _literal(source: str, symbol: str) -> Any:
    for cell in json.loads(source)["cells"]:
        code = "".join(cell.get("source", []))
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == symbol for target in node.targets):
                return ast.literal_eval(node.value)
    raise ValueError(f"payload symbol not found: {symbol}")


def materialize_agent(notebook: Path, source: dict[str, Any], destination: Path) -> Path:
    raw = notebook.read_bytes()
    if _sha(raw) != source["notebook_sha256"]:
        raise ValueError(f"notebook hash mismatch: {source['id']}")
    payload = _literal(raw.decode(), source["payload_symbol"])
    if isinstance(payload, list):
        payload = "".join(payload)
    agent = zlib.decompress(base64.b85decode(payload.encode("ascii")))
    if _sha(agent) != source["agent_sha256"]:
        raise ValueError(f"agent hash mismatch: {source['id']}")
    path = destination / f"{source['id']}.py"
    path.write_bytes(agent)
    compile(agent, str(path), "exec")
    return path


def acquire_sources(manifest: dict[str, Any], destination: Path, source_dir: Path | None) -> dict[str, Path]:
    paths = {}
    for source in manifest["sources"]:
        if source_dir:
            matches = list(source_dir.rglob(source["notebook_file"]))
            if len(matches) != 1:
                raise ValueError(f"expected one pinned notebook for {source['id']}, found {len(matches)}")
            notebook = matches[0]
        else:
            pulled = destination / f"notebook-{source['id']}"
            pulled.mkdir()
            subprocess.run(
                ["kaggle", "kernels", "pull", source["kaggle_ref"], "-p", str(pulled)],
                check=True, capture_output=True, text=True,
            )
            notebook = pulled / source["notebook_file"]
        paths[source["id"]] = materialize_agent(notebook, source, destination)
    return paths


def run_screen(champion: Path, agents: dict[str, Path], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    from kaggle_environments import make

    rows = []
    for identity in manifest["panels"]["screen"]:
        for seat in identity["seats"]:
            lineup = [str(champion), str(agents[identity["opponent"]])]
            if seat == 1:
                lineup.reverse()
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
            env.run(lineup)
            final = env.steps[-1]
            candidate = final[seat]
            opponent = final[1 - seat]
            rewards = [state.reward for state in final]
            candidate_reward = rewards[seat]
            opponent_reward = rewards[1 - seat]
            farm = candidate.observation.get("farms", [])[seat]
            rows.append({
                "identity": identity["episode"], "opponent": identity["opponent"],
                "source_hash": identity["source_hash"], "seed": identity["seed"],
                "seat": seat, "time_utc": identity["time_utc"],
                "rank": 1 if candidate_reward >= opponent_reward else 2,
                "margin": candidate_reward - opponent_reward,
                "terminal_cash": farm.get("money"),
                "rewards": {"candidate": candidate_reward, "opponent": opponent_reward},
                "statuses": [state.status for state in final],
                "invalid_actions": sum(state.status != "DONE" for state in final),
                "contract_violations": sum(state.status != "DONE" for state in final),
            })
    return rows


def measure(champion: Path, manifest: dict[str, Any], source_dir: Path | None = None) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    base = {
        "issue": "SOT-2875", "engine": manifest.get("engine"),
        "validation": validation, "confirm": {"consumed": False, "reason": "reserved for SOT-2877"},
        "kaggle_submission": "NOT_PERFORMED",
    }
    if not validation["passed"]:
        return {**base, "passed": False, "screen": {"skipped": True}}
    actual_engine = importlib.metadata.version("kaggle-environments")
    if actual_engine != manifest["engine"]["version"]:
        return {**base, "passed": False, "actual_engine": actual_engine, "screen": {"skipped": True}}
    with tempfile.TemporaryDirectory(prefix="sot2875-public-panel-") as tmp:
        temp = Path(tmp)
        agents = acquire_sources(manifest, temp, source_dir)
        first = run_screen(champion.resolve(), agents, manifest)
        second = run_screen(champion.resolve(), agents, manifest)
        archive = temp / "submission.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(champion.resolve(), arcname="main.py")
        with tarfile.open(archive, "r:gz") as bundle:
            names = bundle.getnames()
            archived = bundle.extractfile("main.py").read() if names == ["main.py"] else b""
        archive_compatible = names == ["main.py"] and archived == champion.resolve().read_bytes()
    validator = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("validate_submission.py")), str(champion.resolve())],
        capture_output=True, text=True, check=False,
    )
    deterministic = first == second
    contract = validator.returncode == 0 and all(
        row["invalid_actions"] == row["contract_violations"] == 0 for row in first)
    both_seat = all({row["seat"] for row in first if row["opponent"] == opponent} == {0, 1}
                    for opponent in {row["opponent"] for row in first})
    return {
        **base, "passed": deterministic and contract and archive_compatible and both_seat,
        "actual_engine": actual_engine,
        "source_pins": manifest["sources"],
        "screen": {"rows": first, "deterministic_reproduction": deterministic,
                   "same_seed_both_seat": both_seat, "contract_pass": contract},
        "submission_contract": "PASS" if contract else "FAIL",
        "archive_compatibility": "PASS" if archive_compatible else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/tomato_public_sealed_panel.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2874/SOT-2875-tomato-public-sealed-panel.json"))
    args = parser.parse_args()
    report = measure(args.champion, json.loads(args.manifest.read_text()), args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "engine": report.get("actual_engine"),
                      "confirm_consumed": report["confirm"]["consumed"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
