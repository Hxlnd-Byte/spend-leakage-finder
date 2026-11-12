"""Shared helpers for the Spend Leakage Finder.

Rule of the project: the AI reads, plain code does every calculation.
Everything that involves dates, percentages or money lives here, so it can be
tested without a language model.
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import difflib
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONTRACT_DIR = DATA / "contracts"
INVOICE_DIR = DATA / "invoices"
TRUTH_DIR = DATA / "truth"
OUT = ROOT / "output"
CACHE = OUT / "cache"


# ---------------------------------------------------------------- config / io
def load_config() -> dict:
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def load_assumptions() -> dict:
    with open(ROOT / "assumptions.toml", "rb") as f:
        return tomllib.load(f)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# --------------------------------------------------------------------- dates
def parse_date(s):
    if not s:
        return None
    if isinstance(s, dt.date):
        return s
    try:
        return dt.date.fromisoformat(str(s).strip()[:10])
    except ValueError:
        return None


def add_months(d: dt.date, n: int) -> dt.date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def anniversaries_passed(effective: dt.date, on: dt.date) -> int:
    n = on.year - effective.year
    if (on.month, on.day) < (effective.month, effective.day):
        n -= 1
    return max(0, n)


def rate_at(base: float, pct_per_year, effective: dt.date, on: dt.date) -> float:
    """Rate after the yearly increases that have fallen due by `on`."""
    n = anniversaries_passed(effective, on)
    return round(base * (1 + (pct_per_year or 0) / 100.0) ** n, 2)


def resolve_end_date(effective, term_months, end_date):
    """The contract states either an end date or a term in months. Code does the sum."""
    if end_date:
        return end_date
    if effective and term_months:
        return add_months(effective, int(term_months)) - dt.timedelta(days=1)
    return None


def current_term_end(end, renew_months, on):
    """Roll an auto-renewing contract forward until its current term ends on/after `on`."""
    if end is None or not renew_months:
        return end
    while end < on:
        end = add_months(end + dt.timedelta(days=1), int(renew_months)) - dt.timedelta(days=1)
    return end


def notice_deadline(term_end, value, unit):
    if value is None or term_end is None:
        return None
    if str(unit).startswith("month"):
        return add_months(term_end, -int(value))
    return term_end - dt.timedelta(days=int(value))


def renewal_status(auto, term_end, deadline, as_of, window_days):
    if not auto or deadline is None or term_end is None:
        return "NONE"
    if deadline < as_of <= term_end:
        return "LOCKED_IN"  # notice date has passed, term still running: renewal can no longer be stopped
    if as_of <= deadline <= as_of + dt.timedelta(days=window_days):
        return "ACT_NOW"
    return "NONE"


PERIOD_MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}


def annualised_value(subtotals_and_freq):
    """Annual spend estimate from the invoices we have: total / months covered * 12."""
    total = sum(s for s, _ in subtotals_and_freq)
    months = sum(PERIOD_MONTHS.get(f, 1) for _, f in subtotals_and_freq)
    return round(total / months * 12, 2) if months else 0.0


# --------------------------------------------------------------------- names
_SUFFIX = {"ltd", "llc", "fzllc", "fze", "plc", "inc", "co", "limited", "gmbh"}


def norm_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", (name or "").lower().replace("-", ""))
    return " ".join(t for t in s.split() if t not in _SUFFIX)


def name_similarity(a: str, b: str) -> float:
    """0 to 1. A short form of a name ("AquaPure") counts as a strong match for the full name."""
    na, nb = norm_name(a), norm_name(b)
    score = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb and (ta <= tb or tb <= ta):
        score = max(score, 0.85)
    return score


def money(x) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    return f"{sign}${x:,.0f}" if x >= 1000 else f"{sign}${x:,.2f}"
