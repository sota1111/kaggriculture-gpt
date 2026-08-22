#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluation.economic_oracle import SNAPSHOT, derive_snapshot

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args=parser.parse_args()
    derived=derive_snapshot(); encoded=json.dumps(derived, indent=2, sort_keys=True)+"\n"
    if args.check:
        if not SNAPSHOT.exists() or SNAPSHOT.read_text()!=encoded: raise SystemExit("economic oracle snapshot drift")
        print("economic oracle snapshot: OK")
    else:
        SNAPSHOT.write_text(encoded); print(SNAPSHOT)
if __name__ == "__main__": main()
