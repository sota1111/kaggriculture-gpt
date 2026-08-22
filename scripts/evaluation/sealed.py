"""Clean-room current-engine sealed evaluation protocol.

The protocol is inspired by the public *Breaking the Tie* notebook's evaluation
design only.  No notebook code or replay/action bytes are included here.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class EnginePin:
    package: str
    version: str
    source_commit: str
    source_sha256: str
    pricing_semantics: str
    action_semantics: str


@dataclass(frozen=True)
class MatchResult:
    block: str
    candidate: str
    opponent: str
    seed: int
    seat: int
    candidate_reward: float
    opponent_reward: float
    status: str = "DONE"
    errors: tuple[str, ...] = ()

    @property
    def margin(self) -> float:
        return self.candidate_reward - self.opponent_reward


@dataclass(frozen=True)
class SealedProtocol:
    engine: EnginePin
    screen_seeds: tuple[int, ...]
    confirm_seeds: tuple[int, ...]
    final_seeds: tuple[int, ...]
    opponents: tuple[str, ...]
    bootstrap_samples: int = 2000
    bootstrap_seed: int = 3007

    def fingerprint(self) -> str:
        return canonical_sha256(asdict(self))


OFFICIAL_ENGINE = EnginePin(
    "kaggle-environments", "1.32.7",
    "28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c",
    "61f1d031afceb5ea3324918723941e0ea2dcc89c8190a64d6837d9fb8a7e53c0",
    "shared-market-lockstep-precommit-unit-quotes-v1",
    "farmer-hands-market-orders-kaggriculture-v1",
)


def validate_engine(pin: EnginePin, expected: EnginePin) -> dict[str, object]:
    """Verify runtime plus source/price/action identity; mismatches fail closed."""
    try:
        actual_version = importlib.metadata.version(pin.package)
    except importlib.metadata.PackageNotFoundError:
        actual_version = None
    checks = {
        "runtime_version": actual_version == pin.version,
        "source_commit": pin.source_commit == expected.source_commit,
        "source_sha256": pin.source_sha256 == expected.source_sha256,
        "pricing_semantics": pin.pricing_semantics == expected.pricing_semantics,
        "action_semantics": pin.action_semantics == expected.action_semantics,
    }
    return {"passed": all(checks.values()), "actual_version": actual_version,
            "checks": checks}


def validate_protocol(protocol: SealedProtocol) -> dict[str, object]:
    blocks = {"screen": set(protocol.screen_seeds),
              "confirm": set(protocol.confirm_seeds),
              "final": set(protocol.final_seeds)}
    checks = {
        "nonempty_blocks": all(blocks.values()),
        "seed_blocks_disjoint": not (blocks["screen"] & blocks["confirm"] or
                                     blocks["screen"] & blocks["final"] or
                                     blocks["confirm"] & blocks["final"]),
        "multiple_opponents": len(set(protocol.opponents)) >= 2,
        "bootstrap_configured": protocol.bootstrap_samples >= 100,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "seeds": {key: sorted(value) for key, value in blocks.items()}}


def _summary(rows: list[MatchResult], samples: int, bootstrap_seed: int) -> dict[str, object]:
    if not rows:
        raise ValueError("empty match block")
    if any(r.status != "DONE" or r.errors for r in rows):
        return {"technical_failure": True, "promotion_eligible": False}
    pairs: dict[tuple[str, int], list[MatchResult]] = defaultdict(list)
    for row in rows:
        pairs[(row.opponent, row.seed)].append(row)
    if any({r.seat for r in pair} != {0, 1} for pair in pairs.values()):
        return {"technical_failure": True, "promotion_eligible": False,
                "reason": "incomplete both-seat pair"}
    pair_margins = {key: sum(r.margin for r in pair) / len(pair) for key, pair in pairs.items()}
    values = list(pair_margins.values())
    rng = random.Random(bootstrap_seed)
    boot = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples))
    by_opponent = defaultdict(list)
    for (opponent, _), margin in pair_margins.items():
        by_opponent[opponent].append(margin)
    opponent_means = {key: sum(value) / len(value) for key, value in by_opponent.items()}
    return {"technical_failure": False, "promotion_eligible": True,
            "seat_pairs": len(values), "mean_margin": sum(values) / len(values),
            "bootstrap_95": [boot[int(.025 * (len(boot)-1))], boot[int(.975 * (len(boot)-1))]],
            "opponent_mean_margins": opponent_means,
            "worst_opponent_margin": min(opponent_means.values())}


def evaluate_sealed(protocol: SealedProtocol, candidates: Iterable[str],
                    run_match: Callable[[str, str, int, int, str], MatchResult]) -> dict[str, object]:
    """Evaluate without opening final until a candidate passes screen+confirm.

    Candidate selection uses screen/confirm only.  Final is run exactly once for
    the selected candidate and can only veto promotion.
    """
    validation = validate_protocol(protocol)
    if not validation["passed"]:
        return {"passed": False, "reason": "invalid protocol", "validation": validation}
    reports = {}
    eligible = []
    def safe_run(candidate: str, opponent: str, seed: int, seat: int, block: str) -> MatchResult:
        try:
            return run_match(candidate, opponent, seed, seat, block)
        except Exception as error:  # evaluator failures are evidence, never pipeline crashes
            return MatchResult(block, candidate, opponent, seed, seat, 0, 0, "ERROR",
                               (f"{type(error).__name__}: {error}",))
    for candidate in candidates:
        reports[candidate] = {}
        for block, seeds in (("screen", protocol.screen_seeds),
                             ("confirm", protocol.confirm_seeds)):
            rows = [safe_run(candidate, opponent, seed, seat, block)
                    for opponent in protocol.opponents for seed in seeds for seat in (0, 1)]
            reports[candidate][block] = _summary(rows, protocol.bootstrap_samples,
                                                  protocol.bootstrap_seed)
            if not reports[candidate][block]["promotion_eligible"]:
                break
        if (set(reports[candidate]) == {"screen", "confirm"} and
                reports[candidate]["screen"]["mean_margin"] >= 0 and
                reports[candidate]["confirm"]["mean_margin"] >= 0):
            eligible.append(candidate)
    if not eligible:
        return {"passed": True, "decision": "no-promotion", "candidates": reports,
                "final_opened": False}
    selected = max(eligible, key=lambda c: (reports[c]["confirm"]["mean_margin"],
                                            reports[c]["screen"]["mean_margin"], c))
    final_rows = [safe_run(selected, opponent, seed, seat, "final")
                  for opponent in protocol.opponents for seed in protocol.final_seeds for seat in (0, 1)]
    final = _summary(final_rows, protocol.bootstrap_samples, protocol.bootstrap_seed)
    reports[selected]["final"] = final
    confirm_worst = reports[selected]["confirm"]["worst_opponent_margin"]
    promoted = (final["promotion_eligible"] and final["mean_margin"] >= 0 and
                final["worst_opponent_margin"] >= confirm_worst)
    return {"passed": True, "decision": "promoted" if promoted else "rejected-final",
            "selected_before_final": selected, "final_opened": True,
            "final_used_for_selection": False, "worst_opponent_guard": promoted,
            "candidates": reports}
