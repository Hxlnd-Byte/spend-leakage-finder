# How it was tested, and how to read the results

## The test is an exam with an answer key

`01_generate_data.py` builds a made-up company and plants 28 mistakes in 166 invoices, then writes down exactly what each mistake is and how much it costs (`data/truth/answer_key.csv`). The tool never sees that file. After it runs, `04_score_and_report.py` marks its work.

| What is planted | Invoices | Value (before VAT) |
|---|---:|---:|
| Duplicate invoice | 4 | $108,090 |
| Billed after contract expiry | 5 | $37,462 |
| Quantity over the contract maximum | 4 | $7,392 |
| Rate above what the contract allows | 7 | $6,348 |
| Charge the contract does not allow | 6 | $1,888 |
| Arithmetic error | 2 | $880 |
| **Total** | **28 of 166 (17%)** | **$162,060** |

Value is before VAT because VAT is normally recoverable. Check your own treatment.

Also in the data, on purpose, are **decoys that look suspicious but are fine**: a price rise inside the allowed cap, seat counts growing below the maximum, a one-time setup fee the contract allows, and invoices after a contract that renewed automatically. A tool that flags those is crying wolf.

The error rate is deliberately high so a small test shows something. A real company will have far fewer.

## What has been tested, and what has not

| Part | Status |
|---|---|
| Date maths (end dates, notice deadlines, yearly price rises) | Tested, 9 automated tests pass |
| Matching invoices to contracts, all six rules | Tested with a perfect stand-in reader: all 28 mistakes found, 0 false alarms, every dollar amount exact |
| Scoring and report | Tested. A deliberately sloppy stand-in reader scored visibly worse, so the marking does catch errors |
| **The AI model reading the PDFs** | **Not yet measured.** It needs Ollama and a model, which were not available where the code was written. You run this step and record the result below |

Anything produced with `--extractor mock` or `noisy_mock` is stamped **MOCK RUN** in the output and charts. It proves the plumbing, not the AI.

## A lesson from the sloppy-reader test

When the stand-in reader made small mistakes (about 1 or 2 facts in 100 wrong), the tool still caught 24 of 28 planted invoices but raised **21 false alarms**. Why: a misread contract rate or cap is then used to judge every invoice from that supplier. One bad fact becomes many wrong flags.

Two practical consequences:
1. Check the extracted contract table before trusting the invoice flags. There are only 30 contracts, so a person can do this in minutes. `output/extracted_contracts.json` has it.
2. Every flag in `findings.csv` carries a plain-English reason with the numbers, so a reviewer can accept or reject it in seconds.

## How to run the real test

```powershell
python run_all.py --limit 5     # speed check
python run_all.py               # full run
python 05_value_model.py --use-measured
```

Read `output/report.md`. The numbers that matter:

| Number | Plain meaning | Good looks like |
|---|---|---|
| Contract facts read correctly | Did the AI copy the terms right? | 95% or more. Below 90%, try a larger or newer model |
| Invoice facts read correctly | Same, for invoices | 95% or more |
| Mistakes caught | Of the 28 planted, how many? | Most of them. Note any missed and why |
| False alarms | Clean invoices wrongly flagged | As few as possible. Each costs a reviewer a few minutes |
| Dollar catch rate | Share of planted money pinned down | This feeds the value model |
| Renewals exactly right | Deadlines and status correct? | 30 of 30 if contract reading was right |

## Your results (fill in after your run)

| | Result |
|---|---|
| Model and version | |
| Graphics card | |
| Seconds per document | |
| Contract facts read correctly | |
| Invoice facts read correctly | |
| Planted invoices caught | / 28 |
| False alarms | |
| Dollar catch rate | |
| Mistakes missed, and why | |

## Questions a sceptical reader should ask

- **"You built the test, so of course it passes."** Fair. The test is a proof of method, not a market claim. The documents are clean and the mistakes are obvious. Real documents are messier, and the honest next step is to run it on a company's own anonymised paperwork.
- **"Where does the savings number come from?"** From the value model, which multiplies published leakage rates by an assumed share of spend and an assumed recovery rate. Those inputs are all in `assumptions.toml`. It is a model, not a measurement.
- **"Would a spreadsheet do this?"** For documents that are already structured, often yes. The AI earns its place only where terms are buried in free text, which is the case for most supplier contracts.
