#!/usr/bin/env python3
"""Step 5 - turn the test into a cost-benefit story a CFO can argue with.

Reads assumptions.toml (every number is labelled benchmark or assumption) and works out
low / base / high cases. Savings are MODELLED, not measured. The only measured number is the
share of planted mistakes the tool caught, and you can plug that in with --use-measured.

Cash recovered (hard savings) and avoided renewals (soft savings) are kept apart on purpose.

Run:  python 05_value_model.py
      python 05_value_model.py --use-measured     (uses your own test run's dollar catch rate)
Outputs: output/value_model.json, output/value_model.md, output/chart_value_cases.png
"""
from __future__ import annotations

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import OUT, load_assumptions, money, read_json, write_json


def case(a, which, detect_override=None, act_now_value=0.0):
    co, lk, de, rc, wk, rn = a["company"], a["leakage_rate"], a["detection"], a["recovery"], a["work"], a["renewals"]
    readable = co["annual_supplier_spend_usd"] * co["share_readable"]
    leakage = readable * lk[which]
    detect = detect_override if detect_override is not None else de[which]
    found = leakage * detect
    recovered = found * rc[which]
    n_true = found / wk["avg_finding_usd"]
    flags = n_true * (1 + wk["false_alarms_per_true_finding"])
    review_cost = flags * wk["review_minutes_per_flag"] / 60 * wk["analyst_cost_usd_per_hour"]
    setup = wk["setup_hours"] * wk["setup_cost_usd_per_hour"] + wk["hardware_and_software_cost_usd"]
    upkeep = wk["annual_upkeep_hours"] * wk["setup_cost_usd_per_hour"]
    year1_cost = setup + upkeep + review_cost
    ongoing_cost = upkeep + review_cost
    soft = act_now_value * rn["share_renegotiated"] * rn[f"saving_{which}"]
    return dict(readable_spend=readable, leakage=leakage, found=found, recovered=recovered, flags_to_review=flags,
                review_cost=review_cost, setup_cost=setup, upkeep_cost=upkeep, year1_cost=year1_cost,
                year1_net=recovered - year1_cost, ongoing_net=recovered - ongoing_cost,
                payback_months=(setup / max(recovered - ongoing_cost, 1e-9) * 12) if recovered > ongoing_cost else None,
                return_per_dollar=recovered / year1_cost if year1_cost else None, soft_renewal_saving=soft)


def break_even_rate(a, detect, recover):
    """Leakage rate (share of readable spend) at which recovered cash just covers year-1 cost."""
    co, wk = a["company"], a["work"]
    readable = co["annual_supplier_spend_usd"] * co["share_readable"]
    setup = wk["setup_hours"] * wk["setup_cost_usd_per_hour"] + wk["hardware_and_software_cost_usd"]
    upkeep = wk["annual_upkeep_hours"] * wk["setup_cost_usd_per_hour"]
    per_dollar_review = (1 + wk["false_alarms_per_true_finding"]) / wk["avg_finding_usd"] * wk["review_minutes_per_flag"] / 60 * wk["analyst_cost_usd_per_hour"]
    # recovered = readable * r * detect * recover ; cost = setup + upkeep + review_per_dollar * readable * r * detect
    denom = readable * detect * (recover - per_dollar_review)
    return (setup + upkeep) / denom if denom > 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-measured", action="store_true")
    args = ap.parse_args()
    a = load_assumptions()
    ren = read_json(OUT.parent / "data" / "truth" / "dataset_summary.json")
    act_now = ren["renewal_annual_value_act_now"]
    override = None
    note = "Detection rates are assumptions (see assumptions.toml)."
    if args.use_measured:
        rs = read_json(OUT / "results_summary.json")
        if rs["is_mock"]:
            raise SystemExit("The last test run used a MOCK reader, so it cannot be used as a measured catch rate. Run the real extractor first.")
        override = rs["finding"]["dollar_recall_pct"] / 100.0
        note = f"Detection uses the MEASURED dollar catch rate from your test run: {override:.0%} for all three cases (a test set with obvious planted errors, so real life may be lower)."

    res = {w: case(a, w, override, act_now) for w in ("low", "base", "high")}
    be = break_even_rate(a, override or a["detection"]["base"], a["recovery"]["base"])
    out = dict(note=note, company=a["company"], cases=res, break_even_leakage_rate=be)
    write_json(OUT / "value_model.json", out)

    co = a["company"]
    L = [f"# Value model: {co['name']}\n",
         f"{co['employees']:,} employees, about {money(co['annual_supplier_spend_usd'])} a year paid to suppliers, "
         f"{co['share_readable']:.0%} of it backed by a contract and invoices the tool can read ({money(res['base']['readable_spend'])}).\n",
         f"_{note}_\n", "| | Low | Base | High |", "|---|---:|---:|---:|"]
    rows = [("Share of spend lost to leakage", lambda w: f"{a['leakage_rate'][w]:.2%}"),
            ("Leakage in the readable spend", lambda w: money(res[w]["leakage"])),
            ("Found by the tool", lambda w: money(res[w]["found"])),
            ("Cash recovered or credited (hard saving)", lambda w: money(res[w]["recovered"])),
            ("Setup cost (one-off)", lambda w: money(res[w]["setup_cost"])),
            ("Yearly upkeep and review", lambda w: money(res[w]["upkeep_cost"] + res[w]["review_cost"])),
            ("Net benefit, year 1", lambda w: money(res[w]["year1_net"])),
            ("Net benefit, later years", lambda w: money(res[w]["ongoing_net"])),
            ("Cash back per dollar spent, year 1", lambda w: f"{res[w]['return_per_dollar']:.1f}x"),
            ("Avoided renewal cost (soft saving, kept separate)", lambda w: money(res[w]["soft_renewal_saving"]))]
    for name, fn in rows:
        L.append(f"| {name} | {fn('low')} | {fn('base')} | {fn('high')} |")
    L += ["", f"**Break-even:** at base detection and recovery, the tool pays for its year-1 cost if leakage is at least **{be:.2%}** of readable spend." if be else "",
          "", "Honest limits: the test set is built with a deliberately high error rate; savings here are modelled, not measured; "
          "a supplier may refuse a refund; and your own leakage rate may sit below the low case if your controls are strong."]
    (OUT / "value_model.md").write_text("\n".join(L), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    names = ["Low", "Base", "High"]
    rec = [res[w]["recovered"] for w in ("low", "base", "high")]
    cost = [res[w]["year1_cost"] for w in ("low", "base", "high")]
    x = range(3)
    ax.bar([i - 0.2 for i in x], rec, 0.38, color="#76B041", label="Cash recovered")
    ax.bar([i + 0.2 for i in x], cost, 0.38, color="#E4572E", label="Year-1 cost (time, upkeep, review)")
    for i in x:
        ax.text(i - 0.2, rec[i], money(rec[i]), ha="center", va="bottom", fontsize=9)
        ax.text(i + 0.2, cost[i], money(cost[i]), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names)
    ax.yaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
    ax.set_title("Modelled year-1 return for a 1,200-person company", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "chart_value_cases.png", dpi=170)
    plt.close(fig)
    print("\n".join(L))


if __name__ == "__main__":
    main()
