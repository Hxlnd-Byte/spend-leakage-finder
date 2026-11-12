# Why these tools and design choices

Every choice below was made for one of four reasons: it costs nothing, it runs on one workstation, it keeps data on the machine, or an IT person can explain it to a CFO in a sentence.

## The big decision: AI reads, code calculates

| Job | Who does it | Why |
|---|---|---|
| Read a messy PDF and find the rate, dates and notice period | AI | Wording and layouts differ for every supplier. Rules cannot cover them all |
| Work out an end date, a notice deadline, an allowed price | Code | Maths must be exact and repeatable. A language model can be confidently wrong |
| Compare an invoice to a contract | Code | Anyone can read the rule and challenge it. An auditor can see why an invoice was flagged |
| Decide whether to dispute with a supplier | A person | Money, relationships and judgement |

The AI is also told to copy, not calculate, and to say "not stated" instead of guessing. That is why the reading form asks for "36 months" and "start date" separately instead of "end date".

Honest note: much of this project is ordinary software. The AI is needed for one part, reading unstructured documents. That is the real shape of most first AI wins in a company.

## Tool by tool

| Choice | Alternatives | Why this one |
|---|---|---|
| **Python 3.12** | Excel macros, Power Automate | Free, readable, and every library here supports it |
| **Ollama** to run the model | LM Studio, llama.cpp directly, vLLM | Free, one installer on Windows, simple local web address, and supports forcing the answer into a fixed JSON shape. LM Studio is a fine alternative if you prefer a visual app |
| **A 7-8B parameter instruct model** (default `qwen2.5:7b`) | Larger 14-32B models, cloud models | Fits in 8 GB of graphics memory and is fast enough for about 200 documents. Larger models read better but need more memory. Swap the name in `config.toml` and compare |
| **Forced JSON output** at temperature 0 | Free-text answers parsed afterwards | The model must answer in the shape we ask for, and gives the same answer each time. This removes a whole class of failures |
| **PyMuPDF** to pull text out of PDFs | pypdf, pdfplumber, OCR tools | Fast and accurate on text PDFs. Licence note: it is AGPL or commercial. For a company product, check the licence or use `pypdf` (permissive) |
| **reportlab** to make the fake PDFs | Word templates | Lets the script make 196 different documents in three layouts with a fixed seed |
| **TOML files** for settings and assumptions | A database, a web form | Plain text a finance person can open and edit |
| **matplotlib** for charts | Excel, BI tool | Free, scripted, same chart every run |
| **GitHub** for code, **LinkedIn / Medium** for the story | | Where recruiters, hiring managers and engineers actually look |

## Things deliberately left out

- **No vector database or "chat with your documents".** The task is checking specific facts, not answering open questions. Adding retrieval would add moving parts and no accuracy.
- **No agent framework.** Nothing here needs to decide what to do next. It reads, checks and reports. Autonomy would add risk (paying or disputing the wrong invoice) and no value at this stage. A later project covers agents, with limits on what they may do.
- **No cloud service.** See sovereignty, below.
- **No OCR.** The generated documents are text PDFs. Scanned paper needs an OCR step in front of the AI step.
- **No automatic dispute or payment.** The output is a review list for a person.

## The sovereignty angle

Contracts and invoices reveal prices, volumes, suppliers and negotiating positions. Sending them to a public AI service is a decision many companies cannot make quickly, because of confidentiality clauses, regulators or customer expectations.

Running the model on your own machine removes that question. Documents never leave the building, nothing is logged by a third party, and the tool still works with the internet unplugged after setup.

What local does **not** solve: a small local model is less accurate than a large cloud one, and local still needs people to maintain it. A sensible next step for a real company is to keep sensitive documents local and send only non-sensitive work to larger cloud models. That "selective sovereignty" idea is a good follow-up project.

## Retrofitting to Microsoft, AWS or Google

The reading step is one function (`call_ollama` in `02_extract.py`). In a Microsoft estate the same job could be done with Azure AI services plus Power Automate; on AWS with Textract and Bedrock; on Google with Document AI. The rules in `03_reconcile.py` stay the same, which is the point: the business logic is portable, the reader is replaceable.
