#!/usr/bin/env python3
"""Reproduce the compact production table from SOT-2824 screen rows only."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED_DATASET_SHA256 = "c2807cd6f38f5a69201939f973114310e89a64dd000e34fce9bf372ba068348f"


def distill(path: Path) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_DATASET_SHA256:
        raise ValueError(f"teacher dataset hash mismatch: {digest}")
    rows = [json.loads(line) for line in raw.splitlines()]
    screen = [row for row in rows if row["identity"]["window"] == "screen"]
    if not screen:
        raise ValueError("screen split is empty")

    peak_hands: dict[int, list[int]] = defaultdict(list)
    per_episode_land: dict[int, dict[int, tuple[int, int]]] = defaultdict(dict)
    for row in screen:
        features = row["features"]
        seat = row["identity"]["winner_seat"]
        farm = features["farms"][seat]
        unlocked = len(farm.get("unlocked_quadrants", ()))
        peak_hands[unlocked].append(len(farm.get("hands", ())))
        episode = row["identity"]["episode_id"]
        previous = per_episode_land[episode].get(unlocked)
        point = (int(features["day"]), int(features["hour"]))
        if previous is None or point < previous:
            per_episode_land[episode][unlocked] = point

    hand_targets = tuple(max(values) for _, values in sorted(peak_hands.items()))
    milestones = []
    for land_count in sorted(peak_hands):
        if land_count <= 1:
            continue
        points = [values[land_count] for values in per_episode_land.values()
                  if land_count in values]
        day = round(statistics.median(point[0] for point in points))
        hour = Counter(point[1] for point in points if point[0] == day).most_common(1)[0][0]
        milestones.append((day, hour, land_count))
    return {
        "dataset_sha256": digest,
        "fit_split": "screen",
        "confirm_rows_used_for_tuning": 0,
        "screen_rows": len(screen),
        "constants": {
            "hands_per_unlocked_quadrant": hand_targets,
            "land_milestones": tuple(milestones),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = distill(args.dataset)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
