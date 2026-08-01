"""Frozen SOT-2263 champion used by the crop/market promotion gate."""

from pathlib import Path

exec((Path(__file__).resolve().parents[2] / "main.py").read_text().replace('CROP_STRATEGY = "BEST_RETURN"', 'CROP_STRATEGY = "WHEAT_ONLY"').replace('SELL_STRATEGY = "PRICE_AWARE"', 'SELL_STRATEGY = "IMMEDIATE"'))
