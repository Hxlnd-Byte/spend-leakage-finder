#!/usr/bin/env python3
"""Step 3 - plain code checks every invoice against its contract.

No AI is used here. Every rule is a few lines you can read, argue with and change.
Rules, in the order they are applied to each invoice:

  1. MATH_ERROR    the invoice does not add up (lines vs subtotal, subtotal + VAT vs total)
  2. DUPLICATE     same contract, same billing period, same amount, already billed
  3. POST_EXPIRY   billed for a period after the contract ended and it does not auto-renew
  4. RATE_OVER     rate is higher than the contract rate plus the allowed yearly increase
  5. QTY_OVER      quantity is above the contract maximum
  6. SURCHARGE     a charge on the invoice that the contract does not allow

It also builds the renewal watch-list: contracts whose notice deadline is close (ACT_NOW)
or has already passed while the term is still running (LOCKED_IN).

Run:  python 03_reconcile.py
"""
from __future__ import annotations

import datetime as dt
import difflib
from collections import defaultdict

from common import (OUT, current_term_end, load_config, name_similarity, notice_deadline, parse_date, rate_at,
                    renewal_status, resolve_end_date, write_csv, write_json, read_json, money, PERIOD_MONTHS)

TOL = 0.02  # a couple of cents of rounding is not a finding


def to_months(value, unit):
    if value is None:
        return None
    return int(round(float(value) * (12 if str(unit or "").lower().startswith("year") else 1)))


def norm_freq(s):
    s = str(s or "").lower()
    return "quarterly" if s.startswith("quarter") else "annual" if s.startswith(("annual", "year")) else "monthly"


def parse_contract(r: dict, warnings: list) -> dict:
    eff = parse_date(r.get("effective_date"))
    term_m = to_months(r.get("term_value"), r.get("term_unit"))
    end = resolve_end_date(eff, term_m, parse_date(r.get("end_date")))
    c = dict(
        contract_id=None, file=r["_file"], agreement_ref=(r.get("agreement_ref") or "").strip().upper() or None,
        vendor_name=r.get("vendor_name") or "", effective=eff, initial_end=end, auto_renew=bool(r.get("auto_renew")),
        renew_months=to_months(r.get("renewal_term_value"), r.get("renewal_term_unit")),
        notice_value=r.get("notice_value"), notice_unit=r.get("notice_unit") or "days",
        freq=norm_freq(r.get("billing_frequency")), item=r.get("item_description") or "",
        rate=r.get("unit_rate"), qty=r.get("committed_quantity") or 1, max_qty=r.get("max_quantity"),
        esc=r.get("annual_increase_cap_pct") or 0, one_offs=r.get("one_off_fees") or [])
    c["contract_id"] = c["agreement_ref"] or r["_file"]
    if eff is None or end is None or c["rate"] is None:
        warnings.append(dict(file=r["_file"], issue="Could not read start date, end date or rate: contract needs a human look"))
    if c["auto_renew"] and not c["renew_months"]:
        c["renew_months"] = 12
        warnings.append(dict(file=r["_file"], issue="Auto-renews but renewal length not found; assumed 12 months"))
    return c


def match_contract(inv: dict, contracts: list[dict]):
    ref = (inv.get("agreement_ref") or "").strip().upper()
    if ref:
        for c in contracts:
            if c["agreement_ref"] == ref:
                return c, "agreement reference", 1.0
    best = max(contracts, key=lambda c: name_similarity(inv.get("vendor_name") or "", c["vendor_name"]))
    s = name_similarity(inv.get("vendor_name") or "", best["vendor_name"])
    return (best, "vendor name", s) if s >= 0.6 else (None, "none", s)


def pick_main(lines, item):
    scored = [(difflib.SequenceMatcher(None, (l["description"] or "").lower(), item.lower()).ratio(), l) for l in lines]
    top = max(scored, key=lambda x: x[0])
    if top[0] >= 0.5:
        return top[1]
    return max(lines, key=lambda l: l["amount"])


def f(v):
    return float(v) if v is not None else 0.0


def main():
    cfg = load_config()
    as_of = dt.date.fromisoformat(cfg["rules"]["as_of_date"])
    win = cfg["rules"]["renewal_window_days"]
    rate_tol = cfg["rules"]["rate_tolerance_pct"] / 100.0

    ex_c = read_json(OUT / "extracted_contracts.json")
    ex_i = read_json(OUT / "extracted_invoices.json")
    warnings: list = []
    contracts = [parse_contract(r, warnings) for r in ex_c["records"]]
    invoices = ex_i["records"]

    # ---- attach each invoice to a contract
    info = []
    for inv in invoices:
        c, how, sim = match_contract(inv, contracts)
        ps = parse_date(inv.get("period_start"))
        if c is None or ps is None:
            warnings.append(dict(file=inv["_file"], issue="Could not match to a contract or read the billing period"))
        info.append(dict(inv=inv, c=c, how=how, sim=sim, ps=ps))

    # ---- duplicates: same contract + period + amount; first by date is the original
    groups = defaultdict(list)
    for k, x in enumerate(info):
        if x["c"] and x["ps"]:
            groups[(x["c"]["contract_id"], x["ps"])].append(k)
    dup_of = {}
    for key, idx in groups.items():
        if len(idx) < 2:
            continue
        idx.sort(key=lambda k: (info[k]["inv"].get("invoice_date") or "", k))
        orig = idx[0]
        for k in idx[1:]:
            if abs(f(info[k]["inv"].get("subtotal")) - f(info[orig]["inv"].get("subtotal"))) <= TOL:
                dup_of[k] = orig
            else:
                warnings.append(dict(file=info[k]["inv"]["_file"], issue="Two invoices for the same period with different amounts: human check"))

    findings = []

    def add(x, typ, amount, why, review=False):
        inv = x["inv"]
        findings.append(dict(doc_id=inv["_file"].split("_")[0], file=inv["_file"], invoice_no=inv.get("invoice_no"),
                             contract_id=x["c"]["contract_id"] if x["c"] else "", vendor=inv.get("vendor_name"),
                             leak_type=typ, overcharge_usd=round(amount, 2), why=why,
                             needs_review="yes" if (review or x["how"] == "vendor name" and x["sim"] < 0.8) else "no"))

    for k, x in enumerate(info):
        inv, c, ps = x["inv"], x["c"], x["ps"]
        if not c or not ps or not inv.get("lines"):
            continue
        lines = inv["lines"]
        sub, vat, tot = f(inv.get("subtotal")), f(inv.get("vat")), f(inv.get("total"))
        line_sum = round(sum(f(l["amount"]) for l in lines), 2)

        # 1. arithmetic
        over = max(0.0, sub - line_sum) + max(0.0, tot - sub - vat)
        if over > TOL:
            add(x, "MATH_ERROR", over, f"Lines add to {money(line_sum)}, subtotal says {money(sub)}; subtotal + VAT is {money(sub + vat)} but total says {money(tot)}.")
        elif abs(round(sub * 0.05, 2) - vat) > 0.05 or abs(line_sum - sub) > TOL:
            warnings.append(dict(file=inv["_file"], issue="Arithmetic differs slightly (VAT or lines vs subtotal): human check"))

        # 2. duplicate
        if k in dup_of:
            o = info[dup_of[k]]["inv"]
            add(x, "DUPLICATE", sub, f"Same contract, same period ({ps}) and same amount as invoice {o.get('invoice_no')} ({o['_file'].split('_')[0]}).")
            continue

        # 3. billed after the contract ended
        end0 = c["initial_end"]
        if end0 and not c["auto_renew"] and ps > end0:
            add(x, "POST_EXPIRY", sub, f"Contract ended {end0} and has no renewal clause; this invoice covers the period starting {ps}.")
            continue

        main_line = pick_main(lines, c["item"])
        rate_inv, qty = f(main_line["unit_rate"]), f(main_line["quantity"])
        allowed = rate_at(f(c["rate"]), c["esc"], c["effective"], ps)

        # 4. rate above contract
        if rate_inv > allowed * (1 + rate_tol) + 0.005:
            add(x, "RATE_OVER", (rate_inv - allowed) * qty, f"Rate {money(rate_inv)} is above the {money(allowed)} the contract allows at this date (base {money(f(c['rate']))}, yearly cap {c['esc']:g}%).")

        # 5. quantity above contract maximum
        if c["max_qty"] is not None and qty > f(c["max_qty"]):
            add(x, "QTY_OVER", (qty - f(c["max_qty"])) * rate_inv, f"{qty:,.0f} billed but the contract maximum is {f(c['max_qty']):,.0f}.")

        # 6. charges the contract does not mention
        for l in lines:
            if l is main_line:
                continue
            ok = any(difflib.SequenceMatcher(None, (l["description"] or "").lower(), (o.get("description") or "").lower()).ratio() >= 0.6
                     and f(l["amount"]) <= f(o.get("amount")) * 1.01 + 0.01 for o in c["one_offs"])
            if not ok:
                add(x, "SURCHARGE", f(l["amount"]), f"'{l['description']}' ({money(f(l['amount']))}) is not a charge the contract allows.")

    # ---- renewal watch-list
    renewals = []
    for c in contracts:
        if not (c["effective"] and c["initial_end"]):
            continue
        te = current_term_end(c["initial_end"], c["renew_months"] if c["auto_renew"] else None, as_of)
        dl = notice_deadline(te, c["notice_value"], c["notice_unit"]) if c["auto_renew"] else None
        st = renewal_status(c["auto_renew"], te, dl, as_of, win)
        fm = PERIOD_MONTHS[c["freq"]]
        annual = round(rate_at(f(c["rate"]), c["esc"], c["effective"], as_of) * f(c["qty"]) * 12 / fm, 2)
        renewals.append(dict(contract_id=c["contract_id"], vendor_name=c["vendor_name"], current_term_end=te.isoformat(),
                             notice_deadline=dl.isoformat() if dl else "", status=st, annual_value_usd=annual,
                             days_to_deadline=(dl - as_of).days if dl else ""))
    renewals.sort(key=lambda r: (r["status"] == "NONE", r["notice_deadline"] or "9999"))

    findings.sort(key=lambda r: (r["doc_id"], r["leak_type"]))
    cols = ["doc_id", "file", "invoice_no", "contract_id", "vendor", "leak_type", "overcharge_usd", "needs_review", "why"]
    write_csv(OUT / "findings.csv", findings, cols)
    write_json(OUT / "findings.json", findings)
    write_csv(OUT / "renewals.csv", renewals, ["contract_id", "vendor_name", "current_term_end", "notice_deadline", "days_to_deadline", "status", "annual_value_usd"])
    write_json(OUT / "renewals.json", renewals)
    write_json(OUT / "review_warnings.json", warnings)
    total = sum(x["overcharge_usd"] for x in findings)
    print(f"Checked {len(invoices)} invoices against {len(contracts)} contracts.")
    print(f"Flagged {len(findings)} findings worth {money(total)} (before VAT). {len(warnings)} items for a human to look at.")
    st = defaultdict(int)
    for r in renewals:
        st[r["status"]] += 1
    print(f"Renewals: {st.get('ACT_NOW', 0)} act-now, {st.get('LOCKED_IN', 0)} already locked in.")
    if ex_i["meta"].get("is_mock"):
        print("NOTE: these inputs came from a MOCK extractor, so this is a plumbing test, not a result.")


if __name__ == "__main__":
    main()
