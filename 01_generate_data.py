#!/usr/bin/env python3
"""Step 1 - build the made-up company's paperwork.

Creates, with a fixed random seed so the result is identical every time:
  data/contracts/*.pdf     30 supplier contracts in three different layouts
  data/invoices/*.pdf      about 150 supplier invoices in three different layouts
  data/truth/*             the ANSWER KEY (what the AI is never shown):
                           the true contract terms, the true invoice contents,
                           every planted mistake, and the renewal deadlines.

Everything is fictional. No real company, person or contract is used.
Amounts are in US dollars for readability; VAT is 5% as in the UAE.

Run:  python 01_generate_data.py
"""
from __future__ import annotations

import csv
import datetime as dt
import random
import shutil
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common import (CONTRACT_DIR, INVOICE_DIR, TRUTH_DIR, add_months, current_term_end,
                    load_config, notice_deadline, rate_at, renewal_status, resolve_end_date,
                    write_csv, write_json)

SEED = 20261111
CUSTOMER = "Halden Group LLC"
CUSTOMER_ADDR = "Level 14, Marsa Tower, Business Bay, Dubai, United Arab Emirates"
VAT_RATE = 0.05
D = dt.date
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
FREQ_MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}
FREQ_TEXT = {"monthly": "monthly in advance", "quarterly": "quarterly in advance", "annual": "annually in advance"}

# --------------------------------------------------------------------------------------
# 1. THE 30 CONTRACTS
# --------------------------------------------------------------------------------------
CONTRACTS: list[dict] = []


def mk(cid, vendor, short, item, unit_text, noun, rate, qty, cap, freq, eff, term_m, renew_m,
       notice, esc, style, stated_end=False, extras=(), growth=0):
    CONTRACTS.append(dict(
        contract_id=cid, vendor_name=vendor, vendor_short=short, item_description=item,
        unit_text=unit_text, noun=noun, unit_rate=rate, committed_quantity=qty, max_quantity=cap,
        billing_frequency=freq, effective_date=eff, term_months=term_m, renew_months=renew_m,
        notice=notice, annual_increase_cap_pct=esc, style=style, end_date_stated=stated_end,
        one_off_fees=[dict(description=d, amount=a) for d, a in extras], growth=growth,
        agreement_ref=f"AGR-{eff.year}-{int(cid[2:]) * 7 + 100:03d}"))


F = "per month (fixed fee)"
mk("C-001", "Bluepeak Cloud Hosting FZ-LLC", "Bluepeak Hosting", "Managed cloud hosting, production environment", F, None, 14200, 1, None, "monthly", D(2024, 3, 1), 36, 12, (90, "days"), 3, 1)
mk("C-002", "Karam Office Supplies LLC", "Karam Office Supplies", "Office stationery supply programme", F, None, 3800, 1, None, "monthly", D(2025, 1, 1), 24, None, (0, "days"), 0, 2)
mk("C-003", "Meridian Cleaning Services LLC", "Meridian Cleaning", "Cleaning services, head office and two branches", F, None, 18500, 1, None, "monthly", D(2023, 9, 1), 36, 12, (60, "days"), 4, 3, stated_end=True)
mk("C-004", "Quillbase Software Ltd", "Quillbase", "Collaboration suite subscription", "per seat per month", "seats", 14.50, 1150, 1300, "monthly", D(2025, 4, 1), 24, 12, (90, "days"), 5, 1, growth=10)
mk("C-005", "Tessera CRM Systems Ltd", "Tessera CRM", "Customer relationship management subscription", "per seat per month", "seats", 62.00, 85, 100, "monthly", D(2024, 7, 1), 36, 12, (60, "days"), 3, 2)
mk("C-006", "Orbix Endpoint Security Inc", "Orbix Security", "Endpoint protection licences", "per device per month", "devices", 4.20, 1400, 1500, "monthly", D(2025, 2, 1), 24, 12, (90, "days"), 0, 3, growth=5)
mk("C-007", "Lumen HR Software Ltd", "Lumen HR", "Human resources platform subscription", "per employee per month", "employees", 3.10, 1200, 1350, "monthly", D(2025, 9, 1), 36, 12, (90, "days"), 4, 1, growth=3)
mk("C-008", "PrintWorks Managed Print LLC", "PrintWorks", "Managed print service, all floors", F, None, 6400, 1, None, "monthly", D(2024, 11, 1), 36, None, (0, "days"), 0, 2)
mk("C-009", "Falcon Security Guarding LLC", "Falcon Security", "Security guarding, 24-hour cover", "per guard per month", "guards", 3150, 12, 14, "monthly", D(2024, 1, 1), 36, 12, (90, "days"), 3, 3)
mk("C-010", "Cobalt Facilities Maintenance LLC", "Cobalt Facilities", "Air-conditioning planned maintenance", F, None, 9750, 1, None, "monthly", D(2023, 9, 1), 36, None, (0, "days"), 3, 1, stated_end=True)
mk("C-011", "Swiftline Courier Services LLC", "Swiftline Courier", "Courier and parcel service, fixed programme", F, None, 2300, 1, None, "monthly", D(2025, 3, 1), 12, 12, (30, "days"), 0, 2)
mk("C-012", "NetAxis Telecom PJSC", "NetAxis", "Corporate mobile lines", "per line per quarter", "lines", 112.50, 420, 450, "quarterly", D(2024, 4, 1), 36, 12, (90, "days"), 3, 3, growth=4)
mk("C-013", "Gulfstream Internet Services LLC", "Gulfstream Internet", "Dedicated internet circuits, three sites", F, None, 5900, 1, None, "monthly", D(2025, 6, 1), 24, None, (0, "days"), 0, 1)
mk("C-014", "Greenleaf Landscaping LLC", "Greenleaf", "Landscaping and irrigation upkeep", F, None, 2150, 1, None, "monthly", D(2023, 7, 1), 36, None, (0, "days"), 2, 2)
mk("C-015", "Safeguard Pest Control LLC", "Safeguard Pest Control", "Pest control visits, all premises", "per quarter (fixed fee)", None, 1480, 1, None, "quarterly", D(2024, 1, 1), 36, 12, (60, "days"), 0, 3)
mk("C-016", "AquaPure Water Systems LLC", "AquaPure", "Water cooler rental and refills", F, None, 1150, 1, None, "monthly", D(2026, 6, 1), 24, None, (0, "days"), 0, 1, extras=[("One-time installation and setup fee", 3500)])
mk("C-017", "CleanSweep Waste Management LLC", "CleanSweep Waste", "Waste collection and disposal", F, None, 4100, 1, None, "monthly", D(2024, 9, 1), 24, 12, (90, "days"), 3, 2)
mk("C-018", "Atlas Vehicle Leasing LLC", "Atlas Leasing", "Pool vehicle lease", "per vehicle per month", "vehicles", 780, 14, 16, "monthly", D(2024, 10, 1), 48, None, (0, "days"), 0, 3)
mk("C-019", "Prism Learning Ltd", "Prism Learning", "Online learning platform licences", "per seat per year", "seats", 96.00, 600, 700, "annual", D(2025, 12, 1), 12, 12, (60, "days"), 5, 1)
mk("C-020", "Ledgerline Audit Support LLC", "Ledgerline", "Annual audit support retainer", "per year (fixed fee)", None, 36000, 1, None, "annual", D(2025, 11, 15), 12, None, (0, "days"), 0, 2)
mk("C-021", "Northgate Insurance Brokers LLC", "Northgate Brokers", "Insurance brokerage and claims handling fee", "per year (fixed fee)", None, 22000, 1, None, "annual", D(2024, 3, 15), 36, 12, (90, "days"), 3, 3)
mk("C-022", "Vertex Fire Safety LLC", "Vertex Fire Safety", "Annual fire safety inspection and certification", "per year (fixed fee)", None, 7800, 1, None, "annual", D(2023, 5, 1), 36, 12, (60, "days"), 2, 1)
mk("C-023", "Zenith Elevator Services LLC", "Zenith Elevators", "Elevator maintenance, six lifts", "per quarter (fixed fee)", None, 3900, 1, None, "quarterly", D(2025, 1, 1), 36, 12, (90, "days"), 3, 2)
mk("C-024", "Harbor Catering Services LLC", "Harbor Catering", "Staff canteen catering", F, None, 11200, 1, None, "monthly", D(2025, 8, 1), 24, None, (0, "days"), 3, 3)
mk("C-025", "Pioneer Shuttle Transport LLC", "Pioneer Shuttle", "Staff shuttle bus service", F, None, 8300, 1, None, "monthly", D(2025, 11, 1), 12, 12, (60, "days"), 0, 1)
mk("C-026", "Orchid Uniforms and Linen LLC", "Orchid Uniforms", "Uniform supply and laundering", "per quarter (fixed fee)", None, 2750, 1, None, "quarterly", D(2024, 7, 1), 24, None, (0, "days"), 0, 2)
mk("C-027", "DataVault Backup Services Ltd", "DataVault", "Cloud backup storage", "per terabyte per month", "terabytes", 41.00, 220, 260, "monthly", D(2025, 5, 1), 36, 12, (90, "days"), 4, 3, growth=3)
mk("C-028", "Summit Recruitment Technology Ltd", "Summit Recruit", "Applicant tracking system subscription", "per year (fixed fee)", None, 15500, 1, None, "annual", D(2025, 12, 10), 12, 12, (90, "days"), 0, 1)
mk("C-029", "Crestline Legal Advisors LLC", "Crestline Legal", "General legal retainer", F, None, 6500, 1, None, "monthly", D(2024, 12, 1), 36, None, (0, "days"), 3, 2)
mk("C-030", "Ember Staffing Support LLC", "Ember Staffing", "Contract support staff", "per person per month", "people", 4350, 6, 8, "monthly", D(2025, 3, 1), 24, 12, (60, "days"), 3, 3)

# --------------------------------------------------------------------------------------
# 2. THE PLANTED MISTAKES (the answer key is built from this list)
# --------------------------------------------------------------------------------------
PLANTS = [
    dict(type="DUPLICATE", cid="C-001", period=D(2026, 10, 1), same_number=False),
    dict(type="DUPLICATE", cid="C-006", period=D(2026, 8, 1), same_number=True),
    dict(type="DUPLICATE", cid="C-012", period=D(2026, 7, 1), same_number=False),
    dict(type="DUPLICATE", cid="C-020", period=D(2025, 11, 15), same_number=True),
    dict(type="RATE_OVER", cid="C-003", start=D(2026, 9, 1), over_pct=5.0),
    dict(type="RATE_OVER", cid="C-018", start=D(2026, 9, 1), new_rate=845.00),
    dict(type="RATE_OVER", cid="C-022", start=D(2026, 5, 1), over_pct=6.0),
    dict(type="POST_EXPIRY", cid="C-010", start=D(2026, 9, 1)),
    dict(type="POST_EXPIRY", cid="C-026", start=D(2026, 7, 1)),
    dict(type="QTY_OVER", cid="C-005", start=D(2026, 9, 1), qty=118),
    dict(type="QTY_OVER", cid="C-019", start=D(2025, 12, 1), qty=740),
    dict(type="SURCHARGE", cid="C-008", start=D(2026, 8, 1), desc="Fuel and logistics surcharge", amount=192.00),
    dict(type="SURCHARGE", cid="C-024", start=D(2026, 10, 1), desc="Delivery surcharge", amount=560.00),
    dict(type="MATH_ERROR", cid="C-029", period=D(2026, 9, 1), mode="subtotal", delta=650.00),
    dict(type="MATH_ERROR", cid="C-030", period=D(2026, 10, 1), mode="total", delta=230.00),
]

EXPLAIN = {
    "DUPLICATE": "Same period billed twice",
    "RATE_OVER": "Rate is higher than the contract allows",
    "POST_EXPIRY": "Billed after the contract ended (no renewal clause)",
    "QTY_OVER": "Quantity billed is above the contract maximum",
    "SURCHARGE": "Charge that the contract does not allow",
    "MATH_ERROR": "Invoice arithmetic does not add up",
}


# --------------------------------------------------------------------------------------
# 3. TRUTH: contract fields exactly as written in the PDF
# --------------------------------------------------------------------------------------
def duration(months: int, style: int):
    """How a duration is written in the contract: months, or whole years in style 3."""
    if style == 3 and months % 12 == 0:
        y = months // 12
        return y, "years", f"{WORDS.get(y, y)} ({y}) year{'s' if y > 1 else ''}"
    return months, "months", f"{months} months"


def fmt_date(d: dt.date, style: int) -> str:
    if style == 1:
        return f"{d.day} {d.strftime('%B %Y')}"
    if style == 2:
        return d.isoformat()
    return d.strftime("%d %b %Y")


def contract_truth(c: dict) -> dict:
    st = c["style"]
    eff = c["effective_date"]
    end = resolve_end_date(eff, c["term_months"], None)
    tv, tu, _ = duration(c["term_months"], st)
    rv = ru = None
    if c["renew_months"]:
        rv, ru, _ = duration(c["renew_months"], st)
    return dict(
        contract_id=c["contract_id"], file=f"{c['contract_id']}_{slug(c['vendor_name'])}.pdf",
        agreement_ref=c["agreement_ref"], vendor_name=c["vendor_name"],
        effective_date=eff.isoformat(),
        term_value=None if c["end_date_stated"] else tv,
        term_unit=None if c["end_date_stated"] else tu,
        end_date=end.isoformat() if c["end_date_stated"] else None,
        auto_renew=bool(c["renew_months"]), renewal_term_value=rv, renewal_term_unit=ru,
        notice_value=c["notice"][0] if c["renew_months"] else None,
        notice_unit=c["notice"][1] if c["renew_months"] else None,
        billing_frequency=c["billing_frequency"], item_description=c["item_description"],
        unit_rate=c["unit_rate"], committed_quantity=c["committed_quantity"],
        max_quantity=c["max_quantity"], annual_increase_cap_pct=float(c["annual_increase_cap_pct"]),
        one_off_fees=c["one_off_fees"], currency="USD",
    )


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")[:40]


# --------------------------------------------------------------------------------------
# 4. PDF WRITING
# --------------------------------------------------------------------------------------
SS = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=SS["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("s", parent=SS["BodyText"], fontSize=8, leading=10, textColor=colors.grey)
H1 = ParagraphStyle("h1", parent=SS["Title"], fontSize=16, leading=20)
H2 = ParagraphStyle("h2", parent=SS["Heading3"], fontSize=10.5, spaceBefore=8, spaceAfter=2)
RIGHT = ParagraphStyle("r", parent=BODY, alignment=2)


def doc_for(path, title):
    return SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                             topMargin=18 * mm, bottomMargin=18 * mm, title=title, author="Fictional supplier")


def usd(x) -> str:
    return f"USD {x:,.2f}"


def contract_clauses(c: dict, t: dict) -> dict[str, str]:
    """The wording of each business clause. Three styles say the same things differently."""
    st = c["style"]
    eff = c["effective_date"]
    _, _, term_txt = duration(c["term_months"], st)
    end = resolve_end_date(eff, c["term_months"], None)
    out = {}
    if c["end_date_stated"]:
        out["term"] = (f"This Agreement starts on {fmt_date(eff, st)} (the Effective Date) and expires on "
                       f"{fmt_date(end, st)}.")
    elif st == 3:
        out["term"] = f"The initial term is {term_txt} from {fmt_date(eff, st)} (the Effective Date)."
    else:
        out["term"] = (f"This Agreement commences on {fmt_date(eff, st)} (the Effective Date) and continues "
                       f"for an initial term of {term_txt}.")
    if c["renew_months"]:
        _, _, rt = duration(c["renew_months"], st)
        nv, nu = c["notice"]
        out["renewal"] = (f"At the end of the initial term and of each renewal term this Agreement renews automatically for a "
                          f"further {rt}, unless either party gives the other written notice of non-renewal at least "
                          f"{nv} {nu} before the end of the term then running.")
    else:
        out["renewal"] = ("This Agreement ends when its term ends and does not renew. Any extension must be agreed in writing "
                          "and signed by both parties before the end date.")
    unit = c["unit_text"]
    fee = f"The Customer shall pay the Supplier {usd(c['unit_rate'])} {unit}, invoiced {FREQ_TEXT[c['billing_frequency']]}."
    if c["noun"]:
        fee += (f" The initial quantity is {c['committed_quantity']:,} {c['noun']}. The Customer may increase the quantity "
                f"up to a maximum of {c['max_quantity']:,} {c['noun']} at the same rate. Any quantity above that maximum "
                f"needs a written order signed by both parties.")
    out["fees"] = fee
    esc = c["annual_increase_cap_pct"]
    if esc:
        out["price"] = (f"On each anniversary of the Effective Date the Supplier may increase the rate by no more than "
                        f"{esc:g}% over the rate that applied in the previous twelve months. No other increase is allowed.")
    else:
        out["price"] = "The rate is fixed for the whole term, including any renewal term, and shall not be increased."
    extra = ""
    if c["one_off_fees"]:
        f0 = c["one_off_fees"][0]
        extra = f" The only exception is a {f0['description'].lower()} of {usd(f0['amount'])}, payable once with the first invoice."
    out["other"] = ("No charges other than those stated in this Agreement are payable. In particular, no fuel, delivery, "
                    "administration, call-out or service surcharge applies." + extra)
    return out


BOILER = [
    ("Confidentiality", "Each party shall keep the terms of this Agreement and any non-public information of the other party confidential and use it only to perform this Agreement."),
    ("Liability", "Neither party is liable for indirect or consequential loss. Each party's total liability in any year is limited to the fees paid in the previous twelve months, except where the law does not allow a limit."),
    ("Payment", "Undisputed invoices are payable within thirty (30) days of receipt. The Customer may withhold a disputed amount while the dispute is resolved in good faith."),
    ("Governing law", "This Agreement is governed by the laws of the Emirate of Dubai and the federal laws of the United Arab Emirates applicable there."),
]


def write_contract_pdf(c: dict, t: dict, path):
    st = c["style"]
    cl = contract_clauses(c, t)
    story = []
    eff = fmt_date(c["effective_date"], st)
    if st == 1:
        story += [Paragraph("SERVICES AGREEMENT", H1),
                  Paragraph(f"Agreement reference: <b>{c['agreement_ref']}</b>", BODY),
                  Paragraph(f"This Agreement is made between <b>{c['vendor_name']}</b> (the Supplier) and <b>{CUSTOMER}</b> "
                            f"of {CUSTOMER_ADDR} (the Customer).", BODY),
                  Paragraph(f"Subject: {c['item_description']}.", BODY),
                  Paragraph("1. Term", H2), Paragraph(cl["term"], BODY),
                  Paragraph("2. Renewal", H2), Paragraph(cl["renewal"], BODY),
                  Paragraph("3. Fees and quantities", H2), Paragraph(cl["fees"], BODY),
                  Paragraph("4. Price changes", H2), Paragraph(cl["price"], BODY),
                  Paragraph("5. Other charges", H2), Paragraph(cl["other"], BODY)]
        for i, (h, tx) in enumerate(BOILER, 6):
            story += [Paragraph(f"{i}. {h}", H2), Paragraph(tx, BODY)]
    elif st == 2:
        rows = [["Agreement reference", c["agreement_ref"]], ["Supplier", c["vendor_name"]], ["Customer", CUSTOMER],
                ["Services", c["item_description"]], ["Billing", FREQ_TEXT[c["billing_frequency"]].capitalize()],
                ["Currency", "US dollars (USD)"]]
        story += [Paragraph("MASTER SERVICE ORDER", H1), Paragraph("Key terms", H2)]
        tb = Table([[Paragraph(a, BODY), Paragraph(b, BODY)] for a, b in rows], colWidths=[45 * mm, 120 * mm])
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
        story += [tb, Spacer(1, 6),
                  Paragraph("Schedule A - Commercial terms", H2),
                  Paragraph(f"<b>Term.</b> {cl['term']}", BODY), Paragraph(f"<b>Renewal.</b> {cl['renewal']}", BODY),
                  Paragraph(f"<b>Fees.</b> {cl['fees']}", BODY), Paragraph(f"<b>Rate review.</b> {cl['price']}", BODY),
                  Paragraph(f"<b>Extra charges.</b> {cl['other']}", BODY), Paragraph("Schedule B - General terms", H2)]
        for h, tx in BOILER:
            story.append(Paragraph(f"<b>{h}.</b> {tx}", BODY))
    else:
        story += [Paragraph(f"{c['vendor_name']}", H1),
                  Paragraph(f"Service agreement with {CUSTOMER} - our reference {c['agreement_ref']}", BODY),
                  Paragraph(f"Dear {CUSTOMER},", BODY),
                  Paragraph(f"Thank you for choosing us for: {c['item_description']}. This letter sets out what we have agreed, "
                            f"and once signed by both of us it forms the agreement between {c['vendor_name']} and {CUSTOMER}.", BODY),
                  Paragraph(f"<b>How long it lasts.</b> {cl['term']}", BODY),
                  Paragraph(f"<b>What happens at the end.</b> {cl['renewal']}", BODY),
                  Paragraph(f"<b>What you pay.</b> {cl['fees']}", BODY),
                  Paragraph(f"<b>Price changes.</b> {cl['price']}", BODY),
                  Paragraph(f"<b>Anything else we charge.</b> {cl['other']}", BODY)]
        for h, tx in BOILER:
            story.append(Paragraph(f"<b>{h}.</b> {tx}", BODY))
    story += [Spacer(1, 14), Paragraph(f"Signed for the Supplier: ______________________ &nbsp;&nbsp; Signed for the Customer: ______________________", SMALL),
              Paragraph(f"Agreement date: {eff}", SMALL)]
    doc_for(path, f"{c['agreement_ref']}").build(story)


def inv_date(d: dt.date, tmpl: int) -> str:
    if tmpl == 1:
        return f"{d.day} {d.strftime('%b %Y')}"
    if tmpl == 2:
        return d.isoformat()
    return d.strftime("%B ") + f"{d.day}, {d.year}"


def write_invoice_pdf(inv: dict, path):
    tm = inv["template"]
    name = inv["vendor_name_printed"]
    ps, pe = dt.date.fromisoformat(inv["period_start"]), dt.date.fromisoformat(inv["period_end"])
    idate = dt.date.fromisoformat(inv["invoice_date"])
    ref_line = inv["agreement_ref"]
    story = []
    cell = lambda s: Paragraph(str(s), BODY)
    line_rows = lambda hdr: [hdr] + [[cell(l["description"]), f"{l['quantity']:,}".rstrip("0").rstrip(".") if isinstance(l['quantity'], float) else f"{l['quantity']:,}",
                                      f"{l['unit_rate']:,.2f}", f"{l['amount']:,.2f}"] for l in inv["lines"]]
    if tm == 1:
        story += [Paragraph(name, H1), Paragraph("TAX INVOICE", H2)]
        meta = [["Invoice No.", inv["invoice_no"], "Invoice date", inv_date(idate, 1)],
                ["Billing period", f"{inv_date(ps, 1)} to {inv_date(pe, 1)}", "Agreement ref", ref_line or "-"]]
        t = Table(meta, colWidths=[28 * mm, 60 * mm, 28 * mm, 50 * mm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
        story += [t, Spacer(1, 6), Paragraph(f"Bill to: {CUSTOMER}, {CUSTOMER_ADDR}", BODY), Spacer(1, 6)]
        lt = Table(line_rows(["Description", "Qty", "Unit price (USD)", "Amount (USD)"]), colWidths=[85 * mm, 20 * mm, 32 * mm, 30 * mm])
        lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
        tot = Table([["Subtotal", f"{inv['subtotal']:,.2f}"], ["VAT 5%", f"{inv['vat']:,.2f}"], ["Total due (USD)", f"{inv['total']:,.2f}"]],
                    colWidths=[40 * mm, 30 * mm], hAlign="RIGHT")
        tot.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"), ("LINEABOVE", (0, 2), (-1, 2), 0.6, colors.black)]))
        story += [lt, Spacer(1, 6), tot]
    elif tm == 2:
        story += [Paragraph(f"<b>{name}</b>", H2), Paragraph("Invoice", H1),
                  Paragraph(f"Ref: {inv['invoice_no']}", BODY), Paragraph(f"Issued: {inv_date(idate, 2)}", BODY),
                  Paragraph(f"Service period: {inv_date(ps, 2)} to {inv_date(pe, 2)}", BODY)]
        if ref_line:
            story.append(Paragraph(f"Under agreement {ref_line}", BODY))
        story += [Paragraph(f"Customer: {CUSTOMER}", BODY), Spacer(1, 6)]
        lt = Table(line_rows(["Item", "Qty", "Rate", "Line total"]), colWidths=[85 * mm, 20 * mm, 30 * mm, 32 * mm])
        lt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
        tot = Table([["Net", f"{inv['subtotal']:,.2f}"], ["VAT (5%)", f"{inv['vat']:,.2f}"], ["Amount payable", f"{inv['total']:,.2f}"]],
                    colWidths=[40 * mm, 30 * mm], hAlign="RIGHT")
        tot.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT")]))
        story += [lt, Spacer(1, 6), tot, Spacer(1, 8), Paragraph("All amounts in US dollars. Payment due in 30 days.", SMALL)]
    else:
        story += [Paragraph(name, H1), Paragraph(f"Invoice number {inv['invoice_no']}, dated {inv_date(idate, 3)}", BODY)]
        intro = f"We are invoicing {CUSTOMER} for services supplied from {inv_date(ps, 3)} to {inv_date(pe, 3)}"
        intro += f" under our agreement {ref_line}." if ref_line else "."
        story += [Paragraph(intro, BODY), Spacer(1, 4)]
        for l in inv["lines"]:
            q = l["quantity"]
            q = f"{q:,}" if not isinstance(q, float) else f"{q:g}"
            story.append(Paragraph(f"- {l['description']}: {q} at USD {l['unit_rate']:,.2f} = USD {l['amount']:,.2f}", BODY))
        story += [Spacer(1, 6), Paragraph(f"Amount before VAT: USD {inv['subtotal']:,.2f}", BODY),
                  Paragraph(f"VAT at 5%: USD {inv['vat']:,.2f}", BODY),
                  Paragraph(f"<b>Please pay: USD {inv['total']:,.2f}</b>", BODY)]
    doc_for(path, inv["invoice_no"]).build(story)


# --------------------------------------------------------------------------------------
# 5. BUILD
# --------------------------------------------------------------------------------------
def periods_for(c: dict, as_of: dt.date) -> list[dt.date]:
    fm = FREQ_MONTHS[c["billing_frequency"]]
    if fm == 1:
        wstart = D(2026, 5, 1)
    elif fm == 3:
        wstart = D(2026, 1, 1)
    else:
        wstart = as_of.replace(year=as_of.year - 1) + dt.timedelta(days=1)
    out, k = [], 0
    while True:
        s = add_months(c["effective_date"], k * fm)
        if s > as_of:
            break
        if s >= wstart:
            out.append(s)
        k += 1
    return out


def make_lines(c, period_start, qty, rate, extras=()):
    desc_suffix = {"monthly": period_start.strftime("%B %Y"), "quarterly": f"quarter starting {period_start.strftime('%d %b %Y')}",
                   "annual": f"year starting {period_start.strftime('%d %b %Y')}"}[c["billing_frequency"]]
    lines = [dict(description=f"{c['item_description']} ({desc_suffix})", quantity=qty, unit_rate=rate,
                  amount=round(qty * rate, 2), kind="MAIN")]
    for d, a in extras:
        lines.append(dict(description=d, quantity=1, unit_rate=a, amount=round(a, 2), kind="EXTRA"))
    return lines


def totals(lines):
    sub = round(sum(l["amount"] for l in lines), 2)
    vat = round(sub * VAT_RATE, 2)
    return sub, vat, round(sub + vat, 2)


def build():
    cfg = load_config()
    as_of = dt.date.fromisoformat(cfg["rules"]["as_of_date"])
    rnd = random.Random(SEED)
    for p in (CONTRACT_DIR, INVOICE_DIR, TRUTH_DIR):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)

    ctruth = {}
    for c in CONTRACTS:
        t = contract_truth(c)
        ctruth[c["contract_id"]] = t
        write_contract_pdf(c, t, CONTRACT_DIR / t["file"])

    invoices, key, seq = [], [], defaultdict(int)
    by_c = {c["contract_id"]: c for c in CONTRACTS}
    plants_by_c = defaultdict(list)
    for p in PLANTS:
        plants_by_c[p["cid"]].append(p)

    def new_number(c):
        seq[c["contract_id"]] += 1
        pre = "".join(w[0] for w in c["vendor_short"].split()[:3]).upper()
        return f"{pre}-{2026}-{seq[c['contract_id']] + 100:04d}"

    def finish(c, inv_no, period_start, qty, rate, extras, plant_info, jitter, doc_flags):
        fm = FREQ_MONTHS[c["billing_frequency"]]
        pe = add_months(period_start, fm) - dt.timedelta(days=1)
        lines = make_lines(c, period_start, qty, rate, extras)
        sub, vat, total = totals(lines)
        math_note = None
        if plant_info and plant_info["type"] == "MATH_ERROR":
            if plant_info["mode"] == "subtotal":
                sub = round(sub + plant_info["delta"], 2)
                vat = round(sub * VAT_RATE, 2)
                total = round(sub + vat, 2)
            else:
                total = round(total + plant_info["delta"], 2)
        short = rnd.random() < 0.3
        inv = dict(
            invoice_no=inv_no, vendor_name_printed=c["vendor_short"] if short else c["vendor_name"],
            agreement_ref=c["agreement_ref"] if rnd.random() < 0.7 else None,
            invoice_date=(period_start + dt.timedelta(days=jitter)).isoformat(),
            period_start=period_start.isoformat(), period_end=pe.isoformat(),
            lines=lines, subtotal=sub, vat=vat, total=total, template=(int(c["contract_id"][2:]) + len(invoices)) % 3 + 1,
            true_contract_id=c["contract_id"], currency="USD")
        inv.update(doc_flags)
        return inv

    for c in CONTRACTS:
        cid = c["contract_id"]
        t = ctruth[cid]
        eff = c["effective_date"]
        end_initial = resolve_end_date(eff, c["term_months"], None)
        cur_end = current_term_end(end_initial, c["renew_months"], as_of)
        post_plants = [p for p in plants_by_c[cid] if p["type"] == "POST_EXPIRY"]
        for k, ps in enumerate(periods_for(c, as_of)):
            expired = (not c["renew_months"]) and ps > end_initial
            post = next((p for p in post_plants if ps >= p["start"]), None)
            if expired and not post:
                continue  # the supplier stopped billing, as it should
            base_rate = rate_at(c["unit_rate"], c["annual_increase_cap_pct"], eff, ps)
            qty = c["committed_quantity"] + c["growth"] * k if c["noun"] else 1
            rate, extras, info, leak = base_rate, [], None, 0.0
            fee_lines = []
            if c["one_off_fees"] and ps == eff:
                fee_lines = [(f["description"], f["amount"]) for f in c["one_off_fees"]]
            extras.extend(fee_lines)
            for p in plants_by_c[cid]:
                if p["type"] == "RATE_OVER" and ps >= p["start"]:
                    rate = p["new_rate"] if "new_rate" in p else round(base_rate * (1 + p["over_pct"] / 100), 2)
                    info, leak = p, round((rate - base_rate) * qty, 2)
                elif p["type"] == "QTY_OVER" and ps >= p["start"]:
                    qty = p["qty"]
                    info, leak = p, round((qty - c["max_quantity"]) * rate, 2)
                elif p["type"] == "SURCHARGE" and ps >= p["start"]:
                    extras.append((p["desc"], p["amount"]))
                    info, leak = p, p["amount"]
                elif p["type"] == "MATH_ERROR" and ps == p["period"]:
                    info, leak = p, p["delta"]
            if post:
                info = post
            inv_no = new_number(c)
            inv = finish(c, inv_no, ps, qty, rate, extras, info, rnd.randint(0, 4), {})
            if post:
                leak = inv["subtotal"]
            invoices.append(inv)
            if info:
                key.append(dict(doc_ref=len(invoices) - 1, leak_type=info["type"], overcharge_usd=round(leak, 2)))
            # duplicates
            for p in plants_by_c[cid]:
                if p["type"] == "DUPLICATE" and ps == p["period"]:
                    dup_no = inv_no if p["same_number"] else new_number(c)
                    dup = finish(c, dup_no, ps, qty, rate, extras, None, rnd.randint(5, 12), {})
                    dup["agreement_ref"] = inv["agreement_ref"]
                    dup["vendor_name_printed"] = inv["vendor_name_printed"]
                    dup["lines"], dup["subtotal"], dup["vat"], dup["total"] = inv["lines"], inv["subtotal"], inv["vat"], inv["total"]
                    dup["template"] = inv["template"]
                    invoices.append(dup)
                    key.append(dict(doc_ref=len(invoices) - 1, leak_type="DUPLICATE", overcharge_usd=inv["subtotal"],
                                    duplicate_of=inv["invoice_no"]))

    # file names and answer key
    n = len(invoices)
    for i, inv in enumerate(invoices, 1):
        inv["doc_id"] = f"I-{i:04d}"
        inv["file"] = f"I-{i:04d}_{slug(inv['vendor_name_printed'])}.pdf"
        write_invoice_pdf(inv, INVOICE_DIR / inv["file"])
    ans = []
    for k in key:
        inv = invoices[k["doc_ref"]]
        ans.append(dict(doc_id=inv["doc_id"], file=inv["file"], invoice_no=inv["invoice_no"], contract_id=inv["true_contract_id"],
                        leak_type=k["leak_type"], overcharge_usd=k["overcharge_usd"], explanation=EXPLAIN[k["leak_type"]]))
    ans.sort(key=lambda r: r["doc_id"])

    # renewal key (uses the TRUE contract data)
    ren = []
    win = cfg["rules"]["renewal_window_days"]
    for c in CONTRACTS:
        t = ctruth[c["contract_id"]]
        end0 = resolve_end_date(c["effective_date"], c["term_months"], None)
        te = current_term_end(end0, c["renew_months"], as_of)
        dl = notice_deadline(te, c["notice"][0], c["notice"][1]) if c["renew_months"] else None
        stat = renewal_status(bool(c["renew_months"]), te, dl, as_of, win)
        fm = FREQ_MONTHS[c["billing_frequency"]]
        rate_now = rate_at(c["unit_rate"], c["annual_increase_cap_pct"], c["effective_date"], as_of)
        qty0 = c["committed_quantity"] if c["noun"] else 1
        ren.append(dict(contract_id=c["contract_id"], vendor_name=c["vendor_name"], current_term_end=te.isoformat(),
                        notice_deadline=dl.isoformat() if dl else "", status=stat,
                        annual_value_usd=round(rate_now * qty0 * 12 / fm, 2)))

    write_json(TRUTH_DIR / "contracts.json", list(ctruth.values()))
    write_json(TRUTH_DIR / "invoices.json", invoices)
    write_csv(TRUTH_DIR / "answer_key.csv", ans, ["doc_id", "file", "invoice_no", "contract_id", "leak_type", "overcharge_usd", "explanation"])
    write_csv(TRUTH_DIR / "renewal_key.csv", ren, ["contract_id", "vendor_name", "current_term_end", "notice_deadline", "status", "annual_value_usd"])

    by_type = defaultdict(lambda: [0, 0.0])
    for r in ans:
        by_type[r["leak_type"]][0] += 1
        by_type[r["leak_type"]][1] += r["overcharge_usd"]
    total_billed = round(sum(i["subtotal"] for i in invoices), 2)
    leak_total = round(sum(v[1] for v in by_type.values()), 2)
    summary = dict(contracts=len(CONTRACTS), invoices=n, flagged_invoices=len(ans),
                   flagged_share=round(len(ans) / n, 4), total_billed_ex_vat=total_billed, planted_leakage_ex_vat=leak_total,
                   leakage_share_of_billed=round(leak_total / total_billed, 4),
                   by_type={k: dict(invoices=v[0], usd=round(v[1], 2)) for k, v in sorted(by_type.items())},
                   renewals={s: sum(1 for r in ren if r["status"] == s) for s in ("ACT_NOW", "LOCKED_IN", "NONE")},
                   renewal_annual_value_act_now=round(sum(r["annual_value_usd"] for r in ren if r["status"] == "ACT_NOW"), 2),
                   renewal_annual_value_locked_in=round(sum(r["annual_value_usd"] for r in ren if r["status"] == "LOCKED_IN"), 2),
                   as_of_date=as_of.isoformat(), seed=SEED)
    write_json(TRUTH_DIR / "dataset_summary.json", summary)
    return summary


if __name__ == "__main__":
    s = build()
    print(f"Contracts: {s['contracts']}   Invoices: {s['invoices']}   Invoices with a planted mistake: {s['flagged_invoices']} ({s['flagged_share']:.1%})")
    print(f"Total billed (before VAT): ${s['total_billed_ex_vat']:,.2f}")
    print(f"Planted leakage (before VAT): ${s['planted_leakage_ex_vat']:,.2f} = {s['leakage_share_of_billed']:.1%} of what was billed in the test window")
    for k, v in s["by_type"].items():
        print(f"  {k:<12} {v['invoices']:>3} invoices  ${v['usd']:>12,.2f}")
    print("Renewals:", s["renewals"], f"| act-now value ${s['renewal_annual_value_act_now']:,.0f}/yr, locked-in ${s['renewal_annual_value_locked_in']:,.0f}/yr")
