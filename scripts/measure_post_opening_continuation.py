#!/usr/bin/env python3
"""Measure post-opening action-family divergence without opening confirm data."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import tempfile
import zlib
from collections import Counter
from pathlib import Path
from typing import Any


FAMILIES = ("production", "labor-routing", "inventory-feasibility", "market")
FORBIDDEN = {"private", "future", "future_prices", "opponent_private", "replay_bytes"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cells(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return ["".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"] if cell["cell_type"] == "code"]


def _literal(source: str, name: str) -> Any:
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name
                                                for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f"missing literal {name}")


def extract_agent(source: dict[str, Any], notebook: Path, destination: Path) -> Path:
    cells = _cells(notebook)
    encoding = source["agent_encoding"]
    variable = source["agent_variable"]
    cell = next(value for value in cells if variable in value)
    encoded = _literal(cell, variable)
    if isinstance(encoded, list):
        encoded = "".join(encoded)
    if encoding == "base85+zlib":
        payload = zlib.decompress(base64.b85decode(encoded.encode("ascii")))
    elif encoding == "base64":
        payload = base64.b64decode(encoded)
    else:
        raise ValueError(f"unsupported encoding: {encoding}")
    if hashlib.sha256(payload).hexdigest() != source["agent_sha256"]:
        raise ValueError(f"agent hash mismatch: {source['id']}")
    compile(payload, str(destination), "exec")
    destination.write_bytes(payload)
    return destination


def validate_manifest(manifest: dict[str, Any], source_dir: Path | None = None) -> dict[str, bool]:
    screen, confirm = manifest.get("screen", []), manifest.get("confirm", [])
    checks = {
        "schema_supported": manifest.get("schema_version") == 1,
        "engine_pinned": manifest.get("engine") == "kaggle-environments==1.32.4",
        "identity_hash_complete": all(all(row.get(field) for field in
            ("id", "url", "kernel_id", "version", "notebook_sha256", "license"))
            for row in manifest.get("sources", [])),
        "required_references_pinned": {"kaito-v27", "salem-3094", "adaptive"} <=
            {row.get("id") for row in manifest.get("sources", [])},
        "opponent_episode_seed_time_disjoint": all(
            {row.get(field) for row in screen}.isdisjoint({row.get(field) for row in confirm})
            for field in ("opponent", "episode", "seed", "time_index")),
        "same_seed_both_seats": all(row.get("seats") == [0, 1] for row in screen + confirm),
        "confirm_reserved_unopened": manifest.get("confirm_status") == "RESERVED_UNOPENED",
        "public_actions_only": set(manifest.get("telemetry_fields", [])) ==
            {"step", "seat", "public_action", "status", "reward"},
        "private_future_excluded": FORBIDDEN <= set(manifest.get("forbidden_fields", [])),
        "submission_not_performed": manifest.get("kaggle_submission") == "NOT_PERFORMED",
    }
    if source_dir:
        checks["source_hashes_match"] = all(
            digest(source_dir / row["local_filename"]) == row["notebook_sha256"]
            for row in manifest["sources"] if row.get("local_filename"))
    return checks


def orders(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict):
        return []
    values = [action.get("farmer", []), *(action.get("hands", []) or []),
              *(action.get("market", []) or [])]
    return [list(value) for value in values if isinstance(value, list) and value]


def family(order: list[Any]) -> str:
    verb = str(order[0]).upper() if order else "PASS"
    if verb in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "SELL_PRODUCT", "HIRE", "BUY_LAND"}:
        return "market"
    if verb in {"NORTH", "SOUTH", "EAST", "WEST", "MOVE", "PASS"}:
        return "labor-routing"
    if verb in {"PICKUP", "DROP", "PLACE", "FEED", "FERTILIZE"}:
        return "inventory-feasibility"
    return "production"


def first_divergence(champion: Any, reference: Any) -> dict[str, Any] | None:
    left, right = orders(champion), orders(reference)
    for index in range(max(len(left), len(right))):
        champion_order = left[index] if index < len(left) else ["PASS"]
        reference_order = right[index] if index < len(right) else ["PASS"]
        if champion_order != reference_order:
            return {"action_index": index, "family": family(reference_order),
                    "champion_action": champion_order, "reference_action": reference_order}
    return None


def run_screen(champion: Path, agents: dict[str, Path], panel: list[dict[str, Any]], anchor: int) -> list[dict[str, Any]]:
    from kaggle_environments import make
    rows = []
    for identity in panel:
        for champion_seat in identity["seats"]:
            lineup = [str(champion), str(agents[identity["opponent"]])]
            if champion_seat == 1:
                lineup.reverse()
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": identity["seed"]}, debug=False)
            env.run(lineup)
            reference_seat = 1 - champion_seat
            first = None
            family_first: dict[str, dict[str, Any]] = {}
            family_counts = {"champion": Counter(), "reference": Counter()}
            for step, states in enumerate(env.steps[1:]):
                if step < anchor:
                    continue
                champion_action = states[champion_seat].action
                reference_action = states[reference_seat].action
                for side, action in (("champion", champion_action), ("reference", reference_action)):
                    family_counts[side].update(family(order) for order in orders(action))
                event = first_divergence(champion_action, reference_action)
                if event and first is None:
                    first = {"step": step, **event}
                champion_families = Counter(family(order) for order in orders(champion_action))
                reference_families = Counter(family(order) for order in orders(reference_action))
                for name in FAMILIES:
                    if name not in family_first and champion_families[name] != reference_families[name]:
                        family_first[name] = {"step": step, "champion_count": champion_families[name],
                                              "reference_count": reference_families[name]}
            final = env.steps[-1]
            rows.append({"opponent": identity["opponent"], "episode": identity["episode"],
                         "seed": identity["seed"], "time_index": identity["time_index"],
                         "champion_seat": champion_seat, "anchor_step": anchor,
                         "first_post_opening_divergence": first,
                         "first_divergence_by_family": family_first,
                         "family_action_counts": {key: dict(value) for key, value in family_counts.items()},
                         "terminal": {"statuses": [str(state.status) for state in final],
                                      "rewards": [state.reward for state in final]}})
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fired = Counter(row["first_post_opening_divergence"]["family"] for row in rows
                    if row["first_post_opening_divergence"])
    family_firings = Counter(name for row in rows for name in row["first_divergence_by_family"])
    return {"episodes": len(rows), "same_seed_both_seats": all(
                {row["champion_seat"] for row in rows if row["seed"] == seed} == {0, 1}
                for seed in {row["seed"] for row in rows}),
            "first_divergence_family_firings": dict(fired),
            "family_divergence_firings": dict(family_firings),
            "first_steps": [row["first_post_opening_divergence"]["step"] for row in rows
                            if row["first_post_opening_divergence"]],
            "result": "identified" if len(fired) else "inconclusive"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champion", type=Path, default=Path("main.py"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/fixtures/post_opening_continuation.json"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/measurements/SOT-2924/SOT-2925-post-opening-continuation.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    checks = validate_manifest(manifest, args.source_dir)
    report: dict[str, Any] = {"issue": "SOT-2925", "passed": all(checks.values()), "checks": checks,
        "provenance": manifest["sources"], "information_boundary": {
            "committed": manifest["telemetry_fields"], "excluded": manifest["forbidden_fields"]},
        "confirm": {"status": "RESERVED_UNOPENED", "cohort": manifest["confirm"], "outcomes": None},
        "kaggle_submission": "NOT_PERFORMED"}
    if report["passed"] and args.source_dir:
        with tempfile.TemporaryDirectory(prefix="sot2925-agents-") as temporary:
            destination = Path(temporary)
            agents = {row["id"]: extract_agent(row, args.source_dir / row["local_filename"],
                                                destination / f"{row['id']}.py")
                      for row in manifest["sources"] if row.get("screen_executable")}
            rows = run_screen(args.champion.resolve(), agents, manifest["screen"], manifest["anchor_step"])
        report["screen"] = {"rows": rows, "summary": summarize(rows)}
        report["runtime_contract"] = "PASS" if all(
            row["terminal"]["statuses"] == ["DONE", "DONE"] for row in rows) else "FAIL"
        report["passed"] = report["passed"] and report["runtime_contract"] == "PASS" and bool(
            report["screen"]["summary"]["first_steps"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "summary": report.get("screen", {}).get("summary"),
                      "confirm": report["confirm"]["status"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
