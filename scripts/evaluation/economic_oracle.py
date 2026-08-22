"""Fail-closed, engine-derived Kaggriculture economic oracle.

Only public observations and the installed official engine are inputs.  Replay
bytes, credentials, and opponent private state are deliberately unsupported.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ENGINE_VERSION = "1.32.7"
ENGINE_SHA256 = "bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e"
AGENTS_SHA256 = "e1a80501a7b02a212eaac9370ada4129a64e0ee6cb3cbc790f3d77d22863fe22"
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
SNAPSHOT = Path(__file__).with_name("economic_oracle_snapshot.json")


class EngineDriftError(RuntimeError):
    """Raised before producing evidence when the official engine has drifted."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_engine() -> Any:
    if importlib.metadata.version("kaggle-environments") != ENGINE_VERSION:
        raise EngineDriftError("kaggle-environments version mismatch")
    module = importlib.import_module("kaggle_environments.envs.kaggriculture.kaggriculture")
    if _sha256(Path(module.__file__)) != ENGINE_SHA256:
        raise EngineDriftError("kaggriculture.py hash mismatch")
    return module


def _crop_yield(crop: dict[str, Any], fertilized: bool = False) -> int:
    if crop["ongoing"]:
        return min(crop["max_yield"], crop["max_yield"] * (2 if fertilized else 1))
    window = crop["max_yield_day"] - ((crop["max_yield_day"] + 1) // 2) + 1
    return min(crop["max_yield"], 1 + window * (2 if fertilized else 1))


def derive_snapshot() -> dict[str, Any]:
    e = load_engine()
    crops = {}
    for name, crop in e.CROPS.items():
        base = e.MARKET_PARAMS[name]["base"]
        days = crop["first_yield_day"] if crop["ongoing"] else crop["max_yield_day"]
        normal, fertilized = _crop_yield(crop), _crop_yield(crop, True)
        crops[name] = {
            **crop, "base_price": base, "cycle_days": days,
            "base_yield": normal, "fertilized_yield": fertilized,
            "base_profit": normal * base - crop["seed"],
            "base_profit_per_tile_day": (normal * base - crop["seed"]) / days,
            "fertilizer_increment_value": (fertilized - normal) * base,
        }
    animals = {}
    wheat = e.MARKET_PARAMS["WHEAT"]["base"]
    for name, animal in e.ANIMALS.items():
        product_price = e.MARKET_PARAMS[animal["product"]]["base"]
        first = animal["first_yield_day"]
        net_first = product_price - first * wheat
        animals[name] = {
            **animal, "product_base_price": product_price,
            "feed_cost_to_first_yield": first * wheat,
            "first_yield_net": net_first,
            "payback_productions_without_care": max(1, math.ceil((animal["cost"] + first * wheat) / product_price)),
            "care_bonus_value_per_fed_day": product_price,
        }
    market = {}
    for item, params in e.MARKET_PARAMS.items():
        market[item] = {**params,
            "price_at_i0_minus_t": e.market_price(item, params["I0"] - params["T"]),
            "price_at_i0": e.market_price(item, params["I0"]),
            "price_at_i0_plus_t": e.market_price(item, params["I0"] + params["T"]),
        }
    return {
        "schema_version": 1,
        "engine": {"package": "kaggle-environments", "version": ENGINE_VERSION,
                   "source_commit": "28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c",
                   "engine_sha256": ENGINE_SHA256, "agents_sha256": AGENTS_SHA256,
                   "license": "Apache-2.0", "license_sha256": LICENSE_SHA256},
        "sources": [{"url": "https://www.kaggle.com/code/georgymamarin/kaggriculture-visualized-what-every-crop-pays",
                     "kernel_id": 129206683, "version": "pulled-2026-08-22",
                     "notebook_sha256": "4c22f50f2e2ee28f92713d304a927d060b26ca73bba3904a35f6870f999b0446",
                     "license": "UNSPECIFIED", "use": "provenance-and-design-only-no-code-copied"}],
        "crops": crops, "animals": animals, "market": market,
        "land": {"order": list(e.LAND_ORDER), "prices": list(e.LAND_PRICES)},
        "labor": {"daily_hire_costs_first_10": [e._hire_cost(i) for i in range(10)], "resets_daily": True},
        "town": {"shops": e.SHOPS, "center_products": e.TOWN_CENTER_PRODUCTS,
                 "default_center_interval": 24, "default_shop_interval": 4,
                 "max_shop_instances": e.MAX_SHOP_INSTANCES},
        "shed": {"default_capacity": 100, "overflow": "discarded-end-of-day"},
        "execution": {"default_episode_steps": 720, "last_action_step": 718,
                      "done_condition": "previous_step >= episodeSteps - 2"},
        "privacy": {"allowed": ["public observation", "own private observation", "engine constants/functions"],
                    "forbidden": ["external replay bytes", "credentials", "opponent private state"]},
    }


def validate_snapshot(path: Path = SNAPSHOT) -> dict[str, Any]:
    expected = json.loads(path.read_text())
    actual = derive_snapshot()
    if actual != expected:
        raise EngineDriftError("economic oracle snapshot mismatch")
    return actual


@dataclass(frozen=True)
class GapRecord:
    entity: str
    opponent: str
    lineage: str
    seed: int
    seat: int
    time: int
    planned_value: float
    realized_value: float
    action_family: str

    @property
    def gap(self) -> float:
        return self.realized_value - self.planned_value


def action_family(action: Any) -> str:
    ops = []
    if isinstance(action, dict):
        ops += [action.get("farmer", ["PASS"])] + list(action.get("hands", []) or [])
        ops += list(action.get("market", []) or [])
    names = {row[0] for row in ops if isinstance(row, list) and row}
    if names & {"SELL", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "BUY_LAND", "HIRE"}: return "market-capital"
    if names & {"PLANT", "WATER", "FERTILIZE", "HARVEST"}: return "crop"
    if names & {"FEED", "CARE", "COLLECT_FERTILIZER", "BUILD_COOP", "BUILD_PASTURE", "PLACE"}: return "animal"
    if names & {"NORTH", "SOUTH", "EAST", "WEST"}: return "labor-movement"
    return "idle"
