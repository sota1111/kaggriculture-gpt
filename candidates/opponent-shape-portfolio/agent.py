"""Public opponent-shape selector over three structurally independent policies."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "champion": ROOT / "main.py",
    "field_scheduler": ROOT / "candidates/diversified-scheduler/policy.py",
    "contract_farmer": ROOT / "candidates/deepeshumrao-whole-agent/agent.py",
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(f"opponent_shape_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


POLICIES = {name: _load(name, path) for name, path in SOURCES.items()}
SELECTIONS = {}


def public_shape(obs):
    """Return a bounded selector feature vector from public farms only."""
    player = int(obs.get("player", 0))
    farms = obs.get("farms", ())
    rivals = [farm for index, farm in enumerate(farms) if index != player]
    plants = livestock = usable = 0
    for farm in rivals:
        for row in farm.get("tiles", ()):
            for tile in row:
                usable += tile != "LOCKED"
                plants += isinstance(tile, dict) and tile.get("kind") == "PLANT"
                livestock += isinstance(tile, dict) and tile.get("kind") == "ANIMAL"
    return {"plant_share": plants / max(1, usable), "livestock": livestock,
            "usable_tiles": usable}


def select_foundation(obs):
    shape = public_shape(obs)
    if shape["livestock"] >= 2:
        return "champion"
    if shape["plant_share"] >= 0.18:
        return "field_scheduler"
    return "contract_farmer"


def agent(obs):
    seat = int(obs.get("player", 0))
    step = int(obs.get("step", 0))
    day = int(obs.get("day", step // 24))
    key = seat
    if step == 0:
        SELECTIONS.pop(key, None)
    # Observe through day 3, then latch. Only current public observations enter.
    if day >= 3 and key not in SELECTIONS:
        SELECTIONS[key] = select_foundation(obs)
    selected = SELECTIONS.get(key, "champion")
    return POLICIES[selected](obs)
