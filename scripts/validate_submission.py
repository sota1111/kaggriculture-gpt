"""Validate a Kaggriculture main.py without requiring the game package."""

import importlib.util
import runpy
import sys
from pathlib import Path


path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("submission", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
assert callable(module.agent)

namespace = runpy.run_path(str(path))
last_callable_name = [name for name, value in namespace.items() if callable(value)][-1]
assert last_callable_name == "agent", f"runtime entrypoint is {last_callable_name}, not agent"

obs = {
    "player": 0,
    "day": 0,
    "farms": [
        {"money": 100, "farmer": [0, 0], "hands": [], "tiles": [[None]]}
    ],
    "private": {"shed": {}, "seeds": {"WHEAT": 1}, "inventories": [[]]},
}
result = module.agent(obs)
assert set(result) == {"farmer", "hands", "market"}
assert all(isinstance(result[key], list) for key in result)
print("Kaggriculture submission contract: PASS")
