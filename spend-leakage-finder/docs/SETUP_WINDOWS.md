# Setup guide: Windows workstation

Time needed: about 30 minutes of your time, plus download and run time.
Cost: nothing. Every tool here is free.
Tested on: the code and rules were tested on Linux with a stand-in reader. The steps below for installing Python, Ollama and the model on Windows are written from the tools' documented behaviour; see "If something goes wrong" and report anything that differs.

## What you need

| Item | Why |
|---|---|
| Windows 10 or 11 | Where this was designed to run |
| 16 GB RAM or more | The workstation in the example has 64 GB. More is comfortable, not required |
| A graphics card with 8 GB of memory | Runs a 7-8 billion parameter model quickly. A CPU-only machine also works, just slower |
| About 10 GB free disk space | The model is roughly 5 GB |

## Step 1. Install the three programs

Open **PowerShell** (press the Windows key, type PowerShell, press Enter). Run:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install Ollama.Ollama
```

If `winget` is missing or a name is not found, download them by hand instead: python.org, git-scm.com, ollama.com. When installing Python by hand, tick **Add python.exe to PATH**.

Close PowerShell and open it again so Windows sees the new programs.

**Why these three?** Python runs the scripts. Git copies the project and later publishes it. Ollama runs the AI model on your own machine. [WHY_THESE_CHOICES.md](WHY_THESE_CHOICES.md) explains each choice.

## Step 2. Get the project

```powershell
git clone https://github.com/<your-name>/spend-leakage-finder
cd spend-leakage-finder
```

No GitHub copy yet? Download the zip, unzip it, and open PowerShell inside that folder.

## Step 3. Set up Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The first line makes a private box for this project's libraries. The prompt will start with `(.venv)` when it is active. If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

## Step 4. Download the AI model

```powershell
ollama pull qwen2.5:7b
```

This downloads about 5 GB once. Then check that it answers:

```powershell
ollama run qwen2.5:7b "Reply with the single word: ready"
```

Type `/bye` to leave. Ollama runs in the background, and its address (`http://localhost:11434`) only works on your own machine.

**Check your graphics card is being used:** while a model is running, open a second PowerShell and run `ollama ps`. The PROCESSOR column should say GPU. If it says CPU, runs will be slower but still correct.

**Want a different model?** Edit `model` in `config.toml` to any instruct model you have pulled. A newer 7-8B model may do better; the test in step 6 tells you.

## Step 5. Build the made-up company

```powershell
python 01_generate_data.py
```

You should see 30 contracts, 166 invoices, 28 invoices with a planted mistake, and about $162,000 of planted leakage. Open any file in `data\contracts` or `data\invoices` to see what the AI will read. The folder `data\truth` holds the answer key. The AI never sees it.

## Step 6. Run it

Start small to learn your machine's speed:

```powershell
python run_all.py --limit 5
```

Note the seconds per document in the output. Multiply by 196 for the full run. Then:

```powershell
python run_all.py
```

If the run stops, run it again. Finished documents are saved in `output\cache` and are not redone. Use `python 02_extract.py --fresh` to start over.

## Step 7. Read the results

Open these in the `output` folder:

| File | What it tells you |
|---|---|
| `report.md` | How well the AI read, what it caught, what it missed, false alarms |
| `findings.csv` | Every flagged invoice with a plain-English reason. Open in Excel |
| `renewals.csv` | Contracts to act on now, and ones already locked in |
| `value_model.md` | The low / base / high cost-benefit table |
| `chart_*.png` | Charts you can drop into a post |

Then plug your measured catch rate into the cost model:

```powershell
python 05_value_model.py --use-measured
```

## Step 8. Check the plumbing (optional, needs no AI)

```powershell
python -m unittest discover tests -v
```

## Step 9. Publish to GitHub

1. Sign in at github.com, click **New repository**, name it `spend-leakage-finder`, leave it empty (no README), click **Create**.
2. In PowerShell inside the project folder:

```powershell
git init
git add .
git commit -m "Spend Leakage Finder: first release"
git branch -M main
git remote add origin https://github.com/<your-name>/spend-leakage-finder.git
git push -u origin main
```

GitHub will ask you to sign in the first time. Prefer clicks to commands? **GitHub Desktop** does the same job.

Before you publish, open `report.md` and paste your real results into `docs/TESTING_AND_RESULTS.md`. The `output` folder is deliberately not uploaded.

## Using your own documents later

Put PDFs in `data\contracts` and `data\invoices`, and keep only text-based PDFs for now (if you can select text on the page, it is text-based). You will also need to adapt the field list in `02_extract.py` to your contract wording. Never upload real contracts to a public repository.

## If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `python` is not recognised | Close and reopen PowerShell. If still missing, reinstall Python with "Add to PATH" ticked |
| `connection refused` on port 11434 | Ollama is not running. Open the Ollama app from the Start menu, or run `ollama serve` |
| Model not found | Run `ollama pull <model name from config.toml>` |
| Very slow, `ollama ps` says CPU | The model does not fit your graphics memory, or drivers are old. Use a smaller model or update graphics drivers |
| "model did not return valid JSON" | Rare. Re-run (finished documents are kept). If it repeats for one file, try a larger model |
| Out of memory | Lower `num_ctx` in `config.toml` to 4096 |
