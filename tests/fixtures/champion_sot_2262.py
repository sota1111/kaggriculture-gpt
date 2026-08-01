"""Frozen SOT-2262 single-tile champion used by the promotion gate."""


def agent(obs):
    me = obs["farms"][int(obs["player"])]
    private = obs["private"]
    x, y = me["farmer"]
    tile = me["tiles"][y][x]
    market = []
    stored = int(private["shed"].get("WHEAT", 0))
    if stored > 0:
        market.append(["SELL", "WHEAT", stored])
    seeds = int(private["seeds"].get("WHEAT", 0))
    if seeds == 0 and int(me["money"]) >= 10:
        market.append(["BUY_SEED", "WHEAT", 1])
    action = ["PASS"]
    if tile is None and seeds > 0:
        action = ["PLANT", "WHEAT"]
    elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
        if int(obs["day"]) - int(tile["planted_day"]) >= 2:
            action = ["HARVEST"]
        elif not tile.get("watered_today", False):
            action = ["WATER"]
    return {"farmer": action, "hands": [["PASS"] for _ in me.get("hands", [])], "market": market}
