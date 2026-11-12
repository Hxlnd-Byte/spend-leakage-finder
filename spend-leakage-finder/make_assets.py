#!/usr/bin/env python3
"""Makes the two charts used in the README and the posts (assets/).
Neither depends on the AI: one shows what was planted, one shows the modelled value."""
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import ROOT, TRUTH_DIR, read_json

COLORS = {"DUPLICATE": "#E4572E", "RATE_OVER": "#17BEBB", "POST_EXPIRY": "#FFC914", "QTY_OVER": "#76B041",
          "SURCHARGE": "#7B5EA7", "MATH_ERROR": "#2E86AB"}
(ROOT / "assets").mkdir(exist_ok=True)
s = read_json(TRUTH_DIR / "dataset_summary.json")
items = sorted(s["by_type"].items(), key=lambda kv: -kv[1]["usd"])
fig, ax = plt.subplots(figsize=(9, 4.4))
ax.barh([k.replace("_", " ").title() for k, _ in items], [v["usd"] for _, v in items], color=[COLORS[k] for k, _ in items])
for i, (k, v) in enumerate(items):
    ax.text(v["usd"] + 1500, i, f"${v['usd']:,.0f}  ({v['invoices']} invoices)", va="center", fontsize=9)
ax.invert_yaxis()
ax.set_xlim(0, max(v["usd"] for _, v in items) * 1.38)
ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
ax.set_title(f"Mistakes planted in the test data: ${s['planted_leakage_ex_vat']:,.0f} across {s['flagged_invoices']} of {s['invoices']} invoices", loc="left", fontweight="bold", fontsize=11)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.tight_layout()
fig.savefig(ROOT / "assets" / "chart_planted_leakage.png", dpi=170)
src = ROOT / "output" / "chart_value_cases.png"
if src.exists():
    shutil.copy(src, ROOT / "assets" / "chart_value_cases.png")
print("assets written")
