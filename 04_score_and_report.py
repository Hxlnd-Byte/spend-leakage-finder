#!/usr/bin/env python3
"""Step 4 - mark the tool's homework against the answer key, then write the report and charts.

Two questions are answered with numbers:
  A. Did the AI READ the documents correctly?   (field-by-field accuracy)
  B. Did the tool FIND the planted mistakes?    (found, missed, false alarms, dollars)

Run:  python 04_score_and_report.py
Outputs (in output/): results_summary.json, report.md, chart_*.png
"""
from __future__ import annotations

import csv
import difflib
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import OUT, TRUTH_DIR, load_config, money, read_json, write_json

COLORS = {"DUPLICATE": "#E4572E", "RATE_OVER": "#17BEBB", "POST_EXPIRY": "#FFC914", "QTY_OVER": "#76B041",
          "SURCHARGE": "#7B5EA7", "MATH_ERROR": "#2E86AB"}
INK = "#1F2933"


def close(a, b, tol=0.005):
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def same_text(a, b, min_ratio=0.9):
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    return difflib.SequenceMatcher(None, a, b).ratio() >= min_ratio


def score_contracts(ex, truth):
    tmap = {t["file"]: t for t in truth}
    hits, total, per_field = 0, 0, defaultdict(lambda: [0, 0])

    def rec(field, ok):
        nonlocal hits, total
        total += 1
        hits += int(ok)
        per_field[field][1] += 1
        per_field[field][0] += int(ok)

    for r in ex:
        t = tmap[r["_file"]]
        for k in ("effective_date", "end_date", "term_unit", "renewal_term_unit", "notice_unit", "billing_frequency", "agreement_ref"):
            rec(k, (r.get(k) or None) == (t.get(k) or None) or (k.endswith("unit") and str(r.get(k) or "")[:3] == str(t.get(k) or "")[:3]))
        for k in ("term_value", "renewal_term_value", "notice_value", "unit_rate", "committed_quantity", "max_quantity"):
            rec(k, close(r.get(k), t.get(k)))
        rec("annual_increase_cap_pct", close(r.get("annual_increase_cap_pct") or 0, t.get("annual_increase_cap_pct") or 0))
        rec("auto_renew", bool(r.get("auto_renew")) == bool(t["auto_renew"]))
        rec("vendor_name", same_text(r.get("vendor_name"), t["vendor_name"]))
        rec("item_description", same_text(r.get("item_description"), t["item_description"], 0.8))
        a = sorted(round(float(x["amount"]), 2) for x in r.get("one_off_fees") or [])
        b = sorted(round(float(x["amount"]), 2) for x in t.get("one_off_fees") or [])
        rec("one_off_fees", a == b)
    return hits, total, per_field


def score_invoices(ex, truth):
    tmap = {t["file"]: t for t in truth}
    hits, total, per_field = 0, 0, defaultdict(lambda: [0, 0])

    def rec(field, ok):
        nonlocal hits, total
        total += 1
        hits += int(ok)
        per_field[field][1] += 1
        per_field[field][0] += int(ok)

    for r in ex:
        t = tmap[r["_file"]]
        for k in ("invoice_no", "invoice_date", "period_start", "period_end"):
            rec(k, (r.get(k) or None) == (t.get(k) or None))
        rec("agreement_ref", (r.get("agreement_ref") or None) == (t.get("agreement_ref") or None))
        rec("vendor_name", same_text(r.get("vendor_name"), t["vendor_name_printed"]))
        for k in ("subtotal", "vat", "total"):
            rec(k, close(r.get(k), t.get(k)))
        rl, tl = r.get("lines") or [], t["lines"]
        rec("line_count", len(rl) == len(tl))
        for i, tline in enumerate(tl):
            ok = i < len(rl) and close(rl[i]["quantity"], tline["quantity"]) and close(rl[i]["unit_rate"], tline["unit_rate"]) and close(rl[i]["amount"], tline["amount"])
            rec("line_values", ok)
    return hits, total, per_field


def main():
    cfg = load_config()
    key = list(csv.DictReader(open(TRUTH_DIR / "answer_key.csv", encoding="utf-8")))
    find = read_json(OUT / "findings.json")
    ren_key = {r["contract_id"]: r for r in csv.DictReader(open(TRUTH_DIR / "renewal_key.csv", encoding="utf-8"))}
    ren = read_json(OUT / "renewals.json")
    exc, exi = read_json(OUT / "extracted_contracts.json"), read_json(OUT / "extracted_invoices.json")
    ctruth, itruth = read_json(TRUTH_DIR / "contracts.json"), read_json(TRUTH_DIR / "invoices.json")
    meta = exi["meta"]
    n_invoices = len(itruth)

    # ---------------- B. finding the mistakes
    kmap = {(r["doc_id"], r["leak_type"]): float(r["overcharge_usd"]) for r in key}
    fmap = defaultdict(float)
    for r in find:
        fmap[(r["doc_id"], r["leak_type"])] += r["overcharge_usd"]
    key_docs = {d for d, _ in kmap}
    found_docs = {d for d, _ in fmap}
    tp_docs = key_docs & found_docs
    fp_docs = found_docs - key_docs
    fn_docs = key_docs - found_docs
    type_ok = sum(1 for d in tp_docs if {t for dd, t in kmap if dd == d} <= {t for dd, t in fmap if dd == d})
    planted = sum(kmap.values())
    matched_usd = sum(min(v, fmap.get(k, 0.0)) for k, v in kmap.items())
    false_alarm_usd = sum(v for (d, _), v in fmap.items() if d in fp_docs)
    found_usd_total = sum(fmap.values())

    by_type = {}
    for t in COLORS:
        pk = {k: v for k, v in kmap.items() if k[1] == t}
        fk = {k for k in pk if k in fmap}
        by_type[t] = dict(planted_invoices=len(pk), found_invoices=len(fk), planted_usd=round(sum(pk.values()), 2),
                          found_usd=round(sum(min(v, fmap[k]) for k, v in pk.items() if k in fmap), 2))

    precision = len(tp_docs) / len(found_docs) if found_docs else 0.0
    recall = len(tp_docs) / len(key_docs) if key_docs else 0.0

    # ---------------- renewals
    r_hit = 0
    r_status = defaultdict(lambda: [0, 0])
    rmap = {}
    # renewal records are keyed by agreement reference; map back through the contract truth
    ref_to_cid = {c["agreement_ref"]: c["contract_id"] for c in ctruth}
    for r in ren:
        cid = ref_to_cid.get(r["contract_id"], r["contract_id"])
        rmap[cid] = r
    for cid, k in ren_key.items():
        got = rmap.get(cid)
        ok = bool(got) and got["status"] == k["status"] and (got["notice_deadline"] or "") == (k["notice_deadline"] or "")
        r_hit += int(ok)
        r_status[k["status"]][1] += 1
        r_status[k["status"]][0] += int(ok)
    act = [r for r in ren if r["status"] == "ACT_NOW"]
    locked = [r for r in ren if r["status"] == "LOCKED_IN"]

    # ---------------- A. reading accuracy
    ch, ct, cf = score_contracts(exc["records"], ctruth)
    ih, it, if_ = score_invoices(exi["records"], itruth)

    secs = meta["seconds_contracts"] + meta["seconds_invoices"]
    docs = meta["contracts"] + meta["invoices"]
    s = dict(
        extractor=meta["extractor"], is_mock=meta["is_mock"], as_of=cfg["rules"]["as_of_date"],
        documents=dict(contracts=meta["contracts"], invoices=meta["invoices"], seconds_total=round(secs, 1),
                       seconds_per_document=round(secs / docs, 2) if docs else None),
        reading_accuracy=dict(contract_fields=dict(correct=ch, total=ct, pct=round(100 * ch / ct, 1)),
                              invoice_fields=dict(correct=ih, total=it, pct=round(100 * ih / it, 1)),
                              weakest_contract_fields=sorted([(k, round(100 * a / b, 1)) for k, (a, b) in cf.items()], key=lambda x: x[1])[:5],
                              weakest_invoice_fields=sorted([(k, round(100 * a / b, 1)) for k, (a, b) in if_.items()], key=lambda x: x[1])[:5]),
        finding=dict(invoices_total=n_invoices, planted_invoices=len(key_docs), flagged_invoices=len(found_docs),
                     caught=len(tp_docs), missed=len(fn_docs), false_alarms=len(fp_docs),
                     precision_pct=round(100 * precision, 1), recall_pct=round(100 * recall, 1),
                     right_type_of_mistake=type_ok, planted_usd=round(planted, 2), caught_usd=round(matched_usd, 2),
                     dollar_recall_pct=round(100 * matched_usd / planted, 1) if planted else None,
                     flagged_usd=round(found_usd_total, 2), false_alarm_usd=round(false_alarm_usd, 2),
                     missed_docs=sorted(fn_docs), false_alarm_docs=sorted(fp_docs), by_type=by_type),
        renewals=dict(contracts=len(ren_key), exactly_right=r_hit, act_now=len(act), locked_in=len(locked),
                      act_now_annual_value=round(sum(r["annual_value_usd"] for r in act), 2),
                      locked_in_annual_value=round(sum(r["annual_value_usd"] for r in locked), 2)),
    )
    write_json(OUT / "results_summary.json", s)

    # ---------------- charts
    plt.rcParams.update({"font.size": 11, "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    types = list(COLORS)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = range(len(types))
    ax.barh([i + 0.2 for i in y], [by_type[t]["planted_usd"] for t in types], height=0.38, color="#D9DEE4", label="Planted in the test data")
    ax.barh([i - 0.2 for i in y], [by_type[t]["found_usd"] for t in types], height=0.38, color=[COLORS[t] for t in types], label="Found by the tool")
    ax.set_yticks(list(y))
    ax.set_yticklabels([t.replace("_", " ").title() for t in types])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
    ax.set_xlabel("Money leaking out (before VAT)")
    ax.set_title("What was hidden in the paperwork, and what the tool found", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    if meta["is_mock"]:
        fig.text(0.5, 0.5, "MOCK RUN - NOT A RESULT", ha="center", va="center", fontsize=26, color="#E4572E", alpha=0.18, rotation=20)
    fig.tight_layout()
    fig.savefig(OUT / "chart_leakage_by_type.png", dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 3.8))
    grp = [("Contract facts read\ncorrectly", s["reading_accuracy"]["contract_fields"]["pct"], "#2E86AB"),
           ("Invoice facts read\ncorrectly", s["reading_accuracy"]["invoice_fields"]["pct"], "#17BEBB"),
           ("Mistakes caught\n(of invoices)", s["finding"]["recall_pct"], "#76B041"),
           ("Flags that were\nreal mistakes", s["finding"]["precision_pct"], "#FFC914")]
    ax.bar([g[0] for g in grp], [g[1] for g in grp], color=[g[2] for g in grp], width=0.55)
    for i, g in enumerate(grp):
        ax.text(i, g[1] + 1.5, f"{g[1]:.0f}%", ha="center", fontweight="bold")
    ax.set_ylim(0, 112)
    ax.set_ylabel("Percent")
    ax.set_title("How well did it do?", loc="left", fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    if meta["is_mock"]:
        fig.text(0.5, 0.5, "MOCK RUN - NOT A RESULT", ha="center", va="center", fontsize=26, color="#E4572E", alpha=0.18, rotation=15)
    fig.tight_layout()
    fig.savefig(OUT / "chart_scorecard.png", dpi=170)
    plt.close(fig)

    # ---------------- written report
    f_ = s["finding"]
    ra = s["reading_accuracy"]
    banner = ("> **MOCK RUN.** These numbers come from a stand-in reader, not an AI model. They prove the plumbing works. "
              "They say nothing about how well the AI reads documents. Run `python 02_extract.py` with Ollama to get a real result.\n\n"
              if meta["is_mock"] else "")
    lines = [f"# Test results\n", banner,
             f"Reader: **{meta['extractor']}**  |  Documents: {meta['contracts']} contracts, {meta['invoices']} invoices  |  "
             f"Time: {s['documents']['seconds_total']:,.0f} seconds ({s['documents']['seconds_per_document']} s per document)  |  Cost: $0 beyond electricity\n",
             "## Did it read the documents correctly?\n",
             f"- Contract facts: **{ra['contract_fields']['pct']}%** correct ({ra['contract_fields']['correct']:,} of {ra['contract_fields']['total']:,})",
             f"- Invoice facts: **{ra['invoice_fields']['pct']}%** correct ({ra['invoice_fields']['correct']:,} of {ra['invoice_fields']['total']:,})",
             f"- Weakest contract fields: " + ", ".join(f"{k} ({v}%)" for k, v in ra["weakest_contract_fields"]),
             f"- Weakest invoice fields: " + ", ".join(f"{k} ({v}%)" for k, v in ra["weakest_invoice_fields"]),
             "\n## Did it find the planted mistakes?\n",
             f"- {f_['planted_invoices']} of {f_['invoices_total']} invoices had a planted mistake. The tool caught **{f_['caught']}** and missed **{f_['missed']}**.",
             f"- It raised **{f_['false_alarms']}** false alarm(s) on clean invoices (precision {f_['precision_pct']}%, recall {f_['recall_pct']}%).",
             f"- Money: {money(f_['planted_usd'])} was planted. The tool pinned down **{money(f_['caught_usd'])}** ({f_['dollar_recall_pct']}%). False alarms were worth {money(f_['false_alarm_usd'])}.",
             "\n| Mistake type | Planted | Found | Planted $ | Found $ |", "|---|---:|---:|---:|---:|"]
    for t, v in f_["by_type"].items():
        lines.append(f"| {t.replace('_', ' ').title()} | {v['planted_invoices']} | {v['found_invoices']} | {money(v['planted_usd'])} | {money(v['found_usd'])} |")
    if f_["missed_docs"]:
        lines.append(f"\nMissed: {', '.join(f_['missed_docs'])}")
    if f_["false_alarm_docs"]:
        lines.append(f"\nFalse alarms: {', '.join(f_['false_alarm_docs'])}")
    r_ = s["renewals"]
    lines += ["\n## Renewal watch-list\n",
              f"- Deadline and status exactly right for **{r_['exactly_right']} of {r_['contracts']}** contracts.",
              f"- **{r_['act_now']} contracts to act on now**, worth {money(r_['act_now_annual_value'])} a year, and **{r_['locked_in']} already locked in** (notice date passed), worth {money(r_['locked_in_annual_value'])} a year.",
              "- This is cost avoidance, not recovered cash. Treat it as a softer number than the table above.",
              "\n![Leakage by type](chart_leakage_by_type.png)\n\n![Scorecard](chart_scorecard.png)\n"]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print(("[MOCK RUN - plumbing test, not a result]\n" if meta["is_mock"] else "") +
          f"Reading accuracy: contracts {ra['contract_fields']['pct']}%, invoices {ra['invoice_fields']['pct']}%\n"
          f"Caught {f_['caught']}/{f_['planted_invoices']} planted invoices, {f_['false_alarms']} false alarm(s), "
          f"{money(f_['caught_usd'])} of {money(f_['planted_usd'])} found ({f_['dollar_recall_pct']}%)\n"
          f"Renewals exactly right: {r_['exactly_right']}/{r_['contracts']}")
    print("Wrote output/report.md and results_summary.json")


if __name__ == "__main__":
    main()
