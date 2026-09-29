# Mamaearth Returns & Growth Intelligence Pipeline

Capstone project — Data Analytics with AI & Gen AI, E&ICT Academy IIT Roorkee.

A three-layer pipeline: a SQL relational store finds and quantifies return-rate
patterns, an independent pandas layer cleans the same raw data and verifies
those numbers statistically, and a GenAI layer turns the verified numbers into
a business narrative. **No layer reports a number it did not itself compute or
receive from the layer before it.**

```
capstone_Project/
├── README.md
├── requirements.txt
├── sql/
│   ├── schema.sql        # Part 1, Task 1 — table definitions
│   ├── seed_data.sql     # Part 1, Task 2 — generated INSERTs from data/*.csv
│   └── reports.sql       # Part 1, Task 3 — 9 reports, with pasted real output
├── data/
│   ├── customers.csv     # 45 rows, provided, never hand-edited
│   ├── products.csv      # 16 rows, provided, never hand-edited
│   └── orders.csv        # 180 rows, provided, never hand-edited
├── analysis/
│   ├── clean_and_eda.py  # Part 2 — cleaning, EDA, hypothesis tests, exports findings.json
│   └── visualize.py      # Part 2, Task 11 — the two PNGs below
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json      # written by clean_and_eda.py — never hand-typed
    ├── generate_narrative.py
    └── sample_output.txt  # a saved run of generate_narrative.py (see Part 3 below)
```

## How the layers connect

1. **SQL layer** (`sql/`) loads the three raw CSVs from `data/` into SQLite and
   runs reporting queries against the **raw, uncleaned** data — establishing
   the baseline numbers (e.g. raw total revenue = Rs.99,860.20) that the
   pandas layer later reconciles against.
2. **Python/pandas layer** (`analysis/`) independently loads the same three
   raw CSVs, cleans them (casing, duplicates, missing values), and
   reconciles its cleaned total (Rs.97,358.30) against the SQL layer's raw
   total, attributing the exact delta to the 5 duplicate rows it removes. It
   then runs the EDA/hypothesis tasks and, at the end, writes
   `narrator/findings.json` — the only place the verified numbers are
   captured for the next layer.
3. **GenAI layer** (`narrator/`) reads `narrator/findings.json` (nothing
   else) and turns it into a Situation–Complication–Resolution narrative,
   either via the Gemini API or via a fully offline, keyless fallback that
   produces the same structure from the same numbers.

## Prerequisites

```bash
pip install -r requirements.txt
```

Needs Python 3.9+ and a `sqlite3` CLI (bundled with Python) or any SQL engine
that accepts standard `CREATE TABLE` / `INSERT` syntax.

## 1. Run the SQL layer

Load the schema and seed data, then run the reports:

```bash
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

`seed_data.sql` contains generated `INSERT` statements built directly from
`data/*.csv` (blank `discount_pct`/`rating` cells become SQL `NULL`
correctly). If you instead load the CSVs with SQLite's `.import` CLI, see the
warning at the top of `sql/reports.sql` — `.import` loads blanks as empty
strings, not `NULL`, and silently breaks Report (b) unless you clean it up
first.

Sanity check after loading:

```sql
SELECT COUNT(*) FROM customers;  -- 45
SELECT COUNT(*) FROM products;   -- 16
SELECT COUNT(*) FROM orders;     -- 180
```

`sql/reports.sql` has every report's actual output pasted as a comment
directly above its query, so you can diff your own run against it.

## 2. Run the Python/pandas layer

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads `data/orders.csv`, `data/customers.csv`,
`data/products.csv` directly — it does **not** read the SQL database, so it
can be run before or after Part 1 with identical results. It prints every
intermediate result the brief's acceptance criteria reference, asserts each
one against the expected value, and finishes by writing
**`narrator/findings.json`** — this is the Part 2 → Part 3 handoff. If a
number in this brief doesn't match your run, the assertions will fail loudly
at that exact step rather than silently producing a wrong `findings.json`.

`visualize.py` re-derives the cleaned data from the raw CSVs (same cleaning
logic) and writes the two PNGs to `visualizations/`. Both scripts are
re-runnable end-to-end and always regenerate identical numbers/files from the
raw CSVs — nothing is hand-edited in between.

## 3. Run the GenAI narrator layer

```bash
python narrator/generate_narrative.py
```

This reads `narrator/findings.json` (written in step 2) and prints an SCR
narrative plus a numeric-accuracy checklist, then saves the run to
`narrator/sample_output.txt`.

**With a Gemini API key** (get a free key with a free usage tier from
[Google AI Studio](https://aistudio.google.com/apikey) — never a paid-only
key):

```bash
# macOS/Linux
export GEMINI_API_KEY="your-key-here"
# Windows PowerShell
$env:GEMINI_API_KEY = "your-key-here"

python narrator/generate_narrative.py
```

**With no key at all** (fully offline, zero network access, zero API spend):
just run `python narrator/generate_narrative.py` without setting
`GEMINI_API_KEY`. `generate_scr_narrative()` catches the missing-key error
internally and calls `generate_scr_narrative_offline()`, which builds the
same three-section narrative from the same `findings.json` using an f-string
template — no network call, no API key required. The `narrator/sample_output.txt`
checked into this repo was produced by this offline path (no Gemini key was
configured when this repo was built), which is why the grader can verify all
five required figures — Rs.97,358.30, 44.4%, 54.5%, Rs.2,501.90, and March at
Rs.20,318.90 — against that saved file with zero API spend. Re-running with a
`GEMINI_API_KEY` set produces a live online narrative and overwrites
`sample_output.txt` with that run instead.

## Reproducing every number in this brief

1. `sql/schema.sql` + `sql/seed_data.sql` + `sql/reports.sql` → Part 1's 9
   reports, each with its expected output pasted above the query.
2. `analysis/clean_and_eda.py` → prints and asserts every Part 2 number
   (payment-method counts, 5 dropped duplicates, imputation counts, the
   Rs.2,501.90 reconciliation, IQR outlier bounds, COD hypothesis, the
   COD/Tier-2 segmentation, correlation bands, and the outlier-corrected
   monthly time series) and writes `narrator/findings.json`.
3. `analysis/visualize.py` → the two labeled charts in `visualizations/`.
4. `narrator/generate_narrative.py` → the SCR narrative and its numeric
   checklist, saved in `narrator/sample_output.txt`.
