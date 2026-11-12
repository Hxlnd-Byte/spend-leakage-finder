#!/usr/bin/env python3
"""Run the whole pipeline in order.

  python run_all.py                       real run with your local Ollama model
  python run_all.py --extractor mock      plumbing test, no AI needed (NOT a result)
  python run_all.py --limit 5             try only the first 5 documents of each kind
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--extractor", default="ollama", choices=["ollama", "mock", "noisy_mock"])
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--regenerate", action="store_true", help="rebuild the made-up documents first")
a = ap.parse_args()

steps = []
if a.regenerate or not (ROOT / "data" / "truth" / "answer_key.csv").exists():
    steps.append(["01_generate_data.py"])
ex = ["02_extract.py", "--extractor", a.extractor] + (["--limit", str(a.limit)] if a.limit else [])
steps += [ex, ["03_reconcile.py"], ["04_score_and_report.py"], ["05_value_model.py"]]
for s in steps:
    print(f"\n=== python {' '.join(s)} ===", flush=True)
    r = subprocess.run([sys.executable, *s], cwd=ROOT)
    if r.returncode:
        sys.exit(r.returncode)
print("\nDone. Open output/report.md and output/value_model.md")
