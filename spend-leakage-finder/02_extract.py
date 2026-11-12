#!/usr/bin/env python3
"""Step 2 - let the AI read the paperwork.

The AI's only job: read each PDF and copy the facts into a fixed form (JSON).
It is told NOT to calculate anything. Dates, deadlines, allowed rates and
differences are all worked out later by plain code (03_reconcile.py).

Extractors
  ollama      (default) a local language model served by Ollama. Nothing leaves the machine.
  mock        reads the answer key and returns perfect answers. Plumbing test only.
  noisy_mock  like mock but makes some deliberate reading mistakes. Plumbing test only.

Mock runs prove the pipeline works. They are NOT a measurement of AI accuracy.

Run:   python 02_extract.py                      (uses the model in config.toml)
       python 02_extract.py --limit 5            (try 5 documents of each kind first)
       python 02_extract.py --extractor mock     (no AI, test the plumbing)
Results are cached in output/cache/ so a stopped run picks up where it left off.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import time

import pymupdf
import requests

from common import CACHE, CONTRACT_DIR, INVOICE_DIR, OUT, TRUTH_DIR, load_config, read_json, write_json


def nullable(t):
    return {"anyOf": [{"type": t}, {"type": "null"}]}


CONTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "agreement_ref": nullable("string"), "vendor_name": nullable("string"),
        "effective_date": nullable("string"), "term_value": nullable("number"), "term_unit": nullable("string"),
        "end_date": nullable("string"), "auto_renew": {"type": "boolean"},
        "renewal_term_value": nullable("number"), "renewal_term_unit": nullable("string"),
        "notice_value": nullable("number"), "notice_unit": nullable("string"),
        "billing_frequency": nullable("string"), "item_description": nullable("string"),
        "unit_rate": nullable("number"), "committed_quantity": nullable("number"), "max_quantity": nullable("number"),
        "annual_increase_cap_pct": nullable("number"),
        "one_off_fees": {"type": "array", "items": {"type": "object", "properties": {
            "description": {"type": "string"}, "amount": {"type": "number"}}, "required": ["description", "amount"]}},
    },
    "required": ["agreement_ref", "vendor_name", "effective_date", "term_value", "term_unit", "end_date", "auto_renew",
                 "renewal_term_value", "renewal_term_unit", "notice_value", "notice_unit", "billing_frequency",
                 "item_description", "unit_rate", "committed_quantity", "max_quantity", "annual_increase_cap_pct", "one_off_fees"],
}

INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_no": nullable("string"), "vendor_name": nullable("string"), "agreement_ref": nullable("string"),
        "invoice_date": nullable("string"), "period_start": nullable("string"), "period_end": nullable("string"),
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "description": {"type": "string"}, "quantity": {"type": "number"},
            "unit_rate": {"type": "number"}, "amount": {"type": "number"}},
            "required": ["description", "quantity", "unit_rate", "amount"]}},
        "subtotal": nullable("number"), "vat": nullable("number"), "total": nullable("number"),
    },
    "required": ["invoice_no", "vendor_name", "agreement_ref", "invoice_date", "period_start", "period_end", "lines",
                 "subtotal", "vat", "total"],
}

CONTRACT_PROMPT = """You are a careful clerk. Read the supplier contract below and copy the requested facts into the JSON form.
Rules:
- Copy values exactly as written. Do NOT calculate, convert or guess. If a fact is not stated, use null.
- Dates must be written as YYYY-MM-DD (change the format only).
- term_value / term_unit: the length of the initial term exactly as written (for example 36 and "months", or 3 and "years"). If the contract gives an expiry date instead of a length, leave both null and put the expiry date in end_date.
- auto_renew: true only if the contract renews automatically; false if it ends and does not renew.
- renewal_term_value / renewal_term_unit: the length of each automatic renewal as written, else null.
- notice_value / notice_unit: how much notice of non-renewal is required, as written ("days" or "months"), else null.
- billing_frequency: one of monthly, quarterly, annual.
- unit_rate: the price per unit (or the fixed fee) for one billing period, as a plain number.
- committed_quantity: the initial quantity (use 1 for a fixed fee). max_quantity: the maximum quantity allowed, else null.
- annual_increase_cap_pct: the most the rate may rise each year, as a number (0 if the rate is fixed).
- one_off_fees: any one-time fees the contract allows, else an empty list.

CONTRACT TEXT:
"""

INVOICE_PROMPT = """You are a careful clerk. Read the supplier invoice below and copy the requested facts into the JSON form.
Rules:
- Copy values exactly as written. Do NOT calculate or correct anything, even if the arithmetic looks wrong. If a fact is not stated, use null.
- Dates must be written as YYYY-MM-DD (change the format only).
- invoice_no: the invoice number. agreement_ref: the agreement or contract reference if the invoice quotes one, else null.
- period_start / period_end: the service period the invoice covers.
- lines: one entry for every charge on the invoice, including surcharges and fees. Give description, quantity, unit_rate and amount exactly as printed.
- subtotal, vat, total: exactly as printed on the invoice.

INVOICE TEXT:
"""


def pdf_text(path) -> str:
    with pymupdf.open(path) as d:
        return "\n".join(page.get_text() for page in d).strip()


def call_ollama(cfg, prompt, text, schema):
    o = cfg["ollama"]
    body = {"model": o["model"], "stream": False, "format": schema,
            "messages": [{"role": "user", "content": prompt + text}],
            "options": {"temperature": 0, "num_ctx": o["num_ctx"]}}
    last = None
    for _ in range(2):
        r = requests.post(o["url"].rstrip("/") + "/api/chat", json=body, timeout=o["timeout_seconds"])
        r.raise_for_status()
        try:
            return json.loads(r.json()["message"]["content"])
        except (json.JSONDecodeError, KeyError) as e:
            last = e
    raise RuntimeError(f"model did not return valid JSON: {last}")


# ---------------------------------------------------------------------------- mocks
def mock_contract(truth):
    keep = ["agreement_ref", "vendor_name", "effective_date", "term_value", "term_unit", "end_date", "auto_renew",
            "renewal_term_value", "renewal_term_unit", "notice_value", "notice_unit", "billing_frequency",
            "item_description", "unit_rate", "committed_quantity", "max_quantity", "annual_increase_cap_pct", "one_off_fees"]
    out = {k: copy.deepcopy(truth[k]) for k in keep}
    out["annual_increase_cap_pct"] = out["annual_increase_cap_pct"] or 0
    return out


def mock_invoice(truth):
    keep = ["invoice_no", "agreement_ref", "invoice_date", "period_start", "period_end", "subtotal", "vat", "total"]
    out = {k: truth[k] for k in keep}
    out["vendor_name"] = truth["vendor_name_printed"]
    out["lines"] = [{k: l[k] for k in ("description", "quantity", "unit_rate", "amount")} for l in truth["lines"]]
    return out


def noisy(kind, rec, rnd):
    """Deliberate reading mistakes at a low rate, to prove the scoring catches them."""
    rec = copy.deepcopy(rec)
    if kind == "contract":
        if rnd.random() < 0.10:
            rec["unit_rate"] = round(rec["unit_rate"] * rnd.choice([0.9, 1.1, 10]), 2)
        if rnd.random() < 0.06 and rec["notice_value"]:
            rec["notice_value"] = rec["notice_value"] + 30
        if rnd.random() < 0.05:
            rec["annual_increase_cap_pct"] = (rec["annual_increase_cap_pct"] or 0) + 2
        if rnd.random() < 0.04 and rec["max_quantity"]:
            rec["max_quantity"] = None
    else:
        if rnd.random() < 0.06:
            rec["lines"][0]["unit_rate"] = round(rec["lines"][0]["unit_rate"] * 1.01, 2)
        if rnd.random() < 0.04 and len(rec["lines"]) > 1:
            rec["lines"] = rec["lines"][:1]
        if rnd.random() < 0.04:
            rec["invoice_no"] = rec["invoice_no"][:-1] + str((int(rec["invoice_no"][-1]) + 1) % 10)
        if rnd.random() < 0.03:
            rec["period_start"], rec["period_end"] = rec["period_end"], rec["period_start"]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["ollama", "mock", "noisy_mock"], default="ollama")
    ap.add_argument("--limit", type=int, default=0, help="only the first N documents of each kind")
    ap.add_argument("--only", choices=["contracts", "invoices"])
    ap.add_argument("--fresh", action="store_true", help="ignore the cache")
    a = ap.parse_args()
    cfg = load_config()
    rnd = random.Random(7)
    tag = a.extractor if a.extractor != "ollama" else f"ollama:{cfg['ollama']['model']}"
    cache = CACHE / "extracted" / a.extractor.replace(":", "_")
    cache.mkdir(parents=True, exist_ok=True)

    ctruth = {t["file"]: t for t in read_json(TRUTH_DIR / "contracts.json")}
    itruth = {t["file"]: t for t in read_json(TRUTH_DIR / "invoices.json")}

    jobs = []
    if a.only != "invoices":
        files = sorted(CONTRACT_DIR.glob("*.pdf"))
        jobs += [("contract", f) for f in (files[:a.limit] if a.limit else files)]
    if a.only != "contracts":
        files = sorted(INVOICE_DIR.glob("*.pdf"))
        jobs += [("invoice", f) for f in (files[:a.limit] if a.limit else files)]

    results = {"contract": [], "invoice": []}
    secs = {"contract": 0.0, "invoice": 0.0}
    t_all = time.time()
    for i, (kind, f) in enumerate(jobs, 1):
        cf = cache / (f.stem + ".json")
        if cf.exists() and not a.fresh:
            rec = read_json(cf)
        else:
            t0 = time.time()
            if a.extractor == "ollama":
                text = pdf_text(f)
                rec = call_ollama(cfg, CONTRACT_PROMPT if kind == "contract" else INVOICE_PROMPT, text,
                                  CONTRACT_SCHEMA if kind == "contract" else INVOICE_SCHEMA)
            else:
                base = mock_contract(ctruth[f.name]) if kind == "contract" else mock_invoice(itruth[f.name])
                rec = noisy(kind, base, rnd) if a.extractor == "noisy_mock" else base
            rec["_seconds"] = round(time.time() - t0, 2)
            write_json(cf, rec)
        rec["_file"] = f.name
        results[kind].append(rec)
        secs[kind] += rec.get("_seconds", 0)
        if i % 10 == 0 or i == len(jobs):
            print(f"  read {i}/{len(jobs)} documents  ({time.time() - t_all:,.0f}s)", flush=True)

    meta = {"extractor": tag, "is_mock": a.extractor != "ollama",
            "contracts": len(results["contract"]), "invoices": len(results["invoice"]),
            "seconds_contracts": round(secs["contract"], 1), "seconds_invoices": round(secs["invoice"], 1)}
    write_json(OUT / "extracted_contracts.json", {"meta": meta, "records": results["contract"]})
    write_json(OUT / "extracted_invoices.json", {"meta": meta, "records": results["invoice"]})
    banner = "MOCK RUN - plumbing test only, not a measurement of AI accuracy" if meta["is_mock"] else f"model {tag}"
    print(f"Done: {meta['contracts']} contracts, {meta['invoices']} invoices read ({banner}).")


if __name__ == "__main__":
    main()
