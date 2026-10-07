# Build Plan — Kharcha: Personal Finance Advisor Chatbot (PS-2)

> Read `research.md` first. Every design decision here is justified there.
> **Living doc rule:** at the end of every phase, update `presentation_reference.md` (each phase lists which sections) and tick the phase in the tracker below.

## Guiding principles (from research)
1. **Numbers come from code, words come from the LLM.** The LLM never does arithmetic on raw rows. It calls deterministic tools and explains their output (research §4.3).
2. **Hybrid categorization:** rules → LLM fallback with an enum schema → user corrections become rules (research §4.1).
3. **Privacy by default:** in-memory only, PII redacted before the LLM sees anything, one-click delete (research §5.1).
4. **No securities advice:** budgeting and saving only (research §5.2).
5. **Lazy stack:** FastAPI + pandas + pdfplumber + one `index.html` with Chart.js from a CDN. No database, no build step, no auth.

## Target file layout (keep it this small)
```
app/
  main.py          # FastAPI routes: upload, overview, insights, chat (SSE), recategorize, delete
  ingest.py        # CSV/XLSX/PDF -> normalized DataFrame
  categorize.py    # narration parsing + rules + LLM fallback
  merchants.json   # merchant/VPA keyword -> category dictionary
  analytics.py     # deterministic queries + insight generators
  chat.py          # PII redaction + Claude tool-use loop
  static/index.html, static/app.js
scripts/make_sample.py   # synthetic statements + ground truth
data/samples/            # generated demo CSVs (+ one PDF)
tests/test_core.py       # one self-check file: parsing, categorizing, analytics
eval/questions.json, eval/run_eval.py
requirements.txt, .env.example, README.md
```

## Phase tracker
| Phase | Name | Status |
|---|---|---|
| P0 | Setup + synthetic data | ☑ |
| P1 | Ingestion (CSV/XLSX/PDF → normalized table) | ☑ |
| P2 | Categorization (rules + UPI parsing + LLM fallback) | ☑ (LLM tier unverified: no API key) |
| P3 | Analytics engine + saving-tip generators | ☑ |
| P4 | Chat agent (Claude tool use, streaming, guardrails, redaction) | ☑ (live-model parts unverified: no API key) |
| P5 | Web UI (upload → dashboard → chat → tips) | ☑ (live-model parts unverified: no API key) |
| P6 | Differentiators (what-if simulator, Hinglish, report export) + eval | ☑ (live-model parts unverified: no API key) |
| P7 | Hardening, deploy, demo script, final presentation material | ☑ (live-model parts unverified: no API key) |

The schedule is ordered by dependencies. P0–P3 work with **no API key**. P4 is the first phase that needs `ANTHROPIC_API_KEY`. If time runs short, **cut P6 first**: P0–P5 on their own make a complete demo.

---

## P0 — Setup + synthetic data

**Goal:** a repo you can run, and realistic statements with known answers.

**Deliverables**
- `requirements.txt`: `fastapi uvicorn[standard] pandas openpyxl pdfplumber anthropic python-multipart python-dotenv` (plus `reportlab` only for generating the sample PDF).
- `.env.example` with `ANTHROPIC_API_KEY=`, and `.gitignore` (`.env`, `.venv`, `__pycache__`).
- `scripts/make_sample.py` generates 3–6 months of transactions for one persona (a 24-year-old in Mumbai, salary ₹65,000):
  - `data/samples/hdfc_style.csv`: metadata header lines, then `Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance`.
  - `data/samples/sbi_style.csv`: `Txn Date, Description, Amount, Dr/Cr, Balance`.
  - `data/samples/statement.pdf`: the same data as a ruled table, password `kharcha123`.
  - `data/samples/ground_truth.json`: the true category per row, plus known facts (total food spend per month, list of subscriptions, the injected anomaly, the unused subscription).
  - The data includes: salary over NEFT, rent over IMPS, EMI over NACH, an SIP over NACH, Netflix/Spotify/Hotstar/a gym subscription (gym = "forgotten"), heavy Swiggy/Zomato use on weekends, Uber/Rapido, Blinkit/Zepto, Amazon, Jio recharge, electricity, ATM withdrawals, P2P transfers to friends, one ₹18,999 anomaly, and a ₹590 late-payment fee.
  - Narrations use real formats (`UPI/P2M/<12 digits>/swiggy@ybl/...`, `NACH/...`, `NEFT CR:...`).

**Exit check:** `python scripts/make_sample.py` writes all 4 files, and opening the CSVs looks like a real bank export.

**Prompt**
```
Read research.md §3 and plan.md P0. Set up the repo: requirements.txt, .env.example, .gitignore, venv.
Write scripts/make_sample.py that generates a realistic synthetic Indian bank statement for one persona
(24yo, Mumbai, ₹65k salary) over 4 months, seeded random, in TWO CSV layouts (HDFC-style with metadata
lines before the header + separate Withdrawal/Deposit columns; SBI-style with single Amount + Dr/Cr column),
plus a password-protected PDF (password kharcha123) and ground_truth.json (true category per row and the
known facts listed in plan.md P0). Narrations must use real Indian formats (UPI/P2M/<ref>/<vpa>, NACH, NEFT CR, IMPS, ATM).
Run it and show the first 15 rows of each output. Then update presentation_reference.md §5 (Research/datasets).
```

---

## P1 — Ingestion

**Goal:** any reasonable statement turns into one normalized DataFrame:
`date (datetime), narration (str), amount (float, +credit/−debit), balance (float|NaN), source (str)`.

**Deliverables (`app/ingest.py`)**
- `load_statement(file_bytes, filename, password=None) -> DataFrame`
- **Header detection:** scan the first ~30 rows for the row that contains a date-like synonym *and* a narration synonym.
- **Column synonyms:** date {date, txn date, transaction date, value dt}, narration {narration, description, particulars, remarks, details}, debit {withdrawal, debit, dr}, credit {deposit, credit, cr}, amount + type flag, balance {balance, closing balance}.
- Amount cleanup: `₹`, commas, `Dr`/`Cr` suffixes, blanks → 0. Dates with `dayfirst=True`.
- PDF: `pdfplumber.open(..., password=)`, then `page.extract_tables()` on every page, concatenate, and run the same normalization. A wrong password gives a clear 400 error ("This PDF is password-protected").
- If the columns cannot be detected, return `needs_mapping` with the column list. The UI then shows 3 dropdowns (this is cheaper than calling an LLM).
- Drop opening/closing balance rows and totals. Deduplicate exact repeats.

**Exit check:** in `tests/test_core.py`, all 3 sample files produce the same row count and the same total debit/credit as `ground_truth.json`.

**Prompt**
```
Implement app/ingest.py per plan.md P1. Use pandas + pdfplumber only. Normalize to columns
date, narration, amount(+credit/-debit), balance, source. Handle header rows not on line 1, column-name
synonyms, single-Amount+Dr/Cr layouts, ₹/comma cleanup, dayfirst dates, password-protected PDFs, and
return a needs_mapping signal when columns can't be detected. Add tests/test_core.py with a check that all
three files in data/samples/ load to identical row counts and debit/credit totals matching ground_truth.json.
Run the test. Then update presentation_reference.md §3 (Technical approach → ingestion) and the build log.
```

---

## P2 — Categorization

**Goal:** every row gets `merchant`, `rail`, `category`, `bucket (Need/Want/Savings/Income/Transfer)` and `cat_source (rule|llm|user)`.

**Deliverables (`app/categorize.py`, `app/merchants.json`)**
- `parse_narration(s) -> {rail, vpa, merchant_key, counterparty}`. Detect the rail by prefix (UPI/NEFT/IMPS/NACH/ATM/POS/CLG/charges), get the VPA with `\S+@\S+`, and take the merchant key from the VPA user part or the cleaned narration tokens. P2P/IMPS names become `counterparty` (to be redacted later).
- `merchants.json`: about 150 Indian merchant keywords → category (see research §4.1 for the list).
- Rules, in order: user overrides → merchant dictionary → rail rules (NACH+SIP/MF → Investments, NACH otherwise → EMI & Loans, ATM → Cash Withdrawal, salary/NEFT CR from the same payer monthly → Income, charge/fee/penalty → Fees & Charges, P2P → Transfers).
- **LLM fallback** for unmatched rows: deduplicate by `merchant_key`, send one batched call to `claude-opus-5-5` with **structured outputs** (`output_config.format` JSON schema, where `category` is an `enum` of the fixed taxonomy and there is also a `confidence` field). Send only the merchant key and the redacted narration. Cache results in memory per merchant key. If there is no API key, fall back to `Other`.
- `recategorize(merchant_key, category)` stores a user override and re-applies it to all matching rows.

**Exit check:** rules alone categorize at least 85% of sample rows correctly. With the LLM fallback, at least 95% match `ground_truth.json`. Print both numbers. These go in the deck.

**Prompt**
```
Implement app/categorize.py + app/merchants.json per plan.md P2 and research.md §3.2/§4.1–4.2.
Narration parser handles HDFC '/', ICICI '-', Axis space separators via VPA regex + rail prefixes.
Rules first; LLM fallback only for unmatched merchant keys, batched and deduped, using the Anthropic
Python SDK with claude-opus-5-5, output_config.format JSON schema with an enum of our categories
(read the claude-api skill's python README first; no forced tool_choice, no prefill). Redact P2P names
before sending. Add accuracy checks to tests/test_core.py against ground_truth.json: report rule-only
accuracy and rule+LLM accuracy. Run them. Record both numbers in presentation_reference.md §3 and §4.
```

---

## P3 — Analytics engine + saving-tip generators

**Goal:** a deterministic "semantic layer". These functions are the LLM's tools and also feed the dashboard.

**Deliverables (`app/analytics.py`)**: every function takes a DataFrame and returns small JSON (rounded ₹, plus the row ids used as evidence).
- `get_overview(period)`: income, spend, net savings, savings rate, date range, balance trend.
- `category_breakdown(period, bucket=None)`
- `top_merchants(period, category=None, n=10)`: total and count.
- `monthly_trend(category=None)`
- `search_transactions(query=None, category=None, min_amount=None, period=None, limit=20)`
- `find_recurring()`: same merchant key, amount within ±10%, interval 25–35 days, at least 2 occurrences, giving the subscription list with the monthly cost.
- `find_anomalies()`: debit more than 3× its category median, or a new merchant over ₹5k.
- `generate_insights()` runs every insight generator from research §4.4 (50/30/20, subscription audit, small-spend leak, category spike, weekend effect, fees, emergency runway). Each returns `{id, title, severity, evidence, monthly_saving_estimate}`, sorted by saving.
- `simulate_savings(changes=[{category|merchant, cut_pct}], months=12)` returns monthly and annual savings and the new savings rate. The P6 what-if feature uses this.

**Exit check:** `tests/test_core.py` asserts that the analytics reproduce the ground-truth facts: monthly food total, the subscription list including the gym, the ₹18,999 anomaly, and the ₹590 fee.

**Prompt**
```
Implement app/analytics.py per plan.md P3 and research.md §4.4. Pure pandas, deterministic, each function
returns compact JSON-serializable dicts with rounded rupee values and evidence row ids. Include
generate_insights() with all 8 insight types and simulate_savings(). Extend tests/test_core.py to assert the
ground-truth facts (food total, recurring list incl. unused gym, anomaly, late fee). Run tests.
Then fill presentation_reference.md §2 (key features: insight list) and §3 (semantic-layer design).
```

---

## P4 — Chat agent

**Goal:** a grounded, streaming conversational advisor.

**Deliverables (`app/chat.py`)**
- `redact(df)`: mask account numbers, phone numbers and emails. Map P2P counterparties to `Person#n`. Tool results go through the same masking.
- **Tools:** the P3 functions exposed as Claude tools with `strict: true` JSON schemas (`additionalProperties: false`). Keep the tool list and system prompt **byte-stable** so they are prompt-cached.
- **System prompt rules:**
  - You are Kharcha, a friendly Indian personal-finance coach. Reply in the user's language (English or Hinglish).
  - **Every number you state must come from a tool result in this conversation. Never estimate or compute totals yourself. If you need a number, call a tool.**
  - Format money as ₹ in Indian style (₹1,23,456).
  - Give tips as specific actions with the expected monthly saving, taken from `monthly_saving_estimate` or `simulate_savings`.
  - **Do not recommend specific stocks, mutual funds or other securities.** For investment-product questions, explain the general principle and suggest a SEBI-registered investment adviser.
  - If the data cannot answer the question, say so.
- Loop: `client.messages.stream(model="claude-opus-5-5", output_config={"effort":"low"}, tools=..., tool_choice auto)`. Handle `tool_use` (run the tools, return all results in one user message), `refusal`, and `max_tokens`. Enable `fallbacks: "default"` with beta `server-side-fallback-2026-07-01`.
- `POST /chat` streams SSE events: `text` deltas, plus a `receipt` event per tool call (`{tool, args, result}`) so the UI can show where each number came from.
- Conversation history is kept per session in memory (append-only, so thinking blocks stay valid).

**Exit check:** these 5 questions return correct, grounded answers on the sample data:
1. "Where did most of my money go last month?"
2. "How much did I spend on Swiggy and Zomato?"
3. "Which subscriptions am I paying for?"
4. "How can I save ₹5,000 a month?"
5. "Which mutual fund should I buy?" → a polite refusal and a pointer to a SEBI-registered adviser.

**Prompt**
```
Read the claude-api skill (python README, tool-use.md, streaming.md) before writing code.
Implement app/chat.py per plan.md P4: PII redaction, P3 analytics exposed as strict tools, the system
prompt rules listed in plan.md, a streaming tool-use loop on claude-opus-5-5 with effort low,
tool_choice auto, refusal handling and fallbacks "default". Emit SSE events for text deltas and a
'receipt' per tool call. Wire POST /chat in app/main.py. Test the 5 exit-check questions via curl against
the sample data and paste the answers. Update presentation_reference.md §3 (agent design, guardrails)
and §2 (chat features), plus the build log.
```

---

## P5 — Web UI

**Goal:** a single-page app that works on a laptop and a phone.

**Deliverables (`app/static/index.html`, `app/static/app.js`, routes in `main.py`)**
- **Screen 1, Upload:** a drag-and-drop zone (CSV/XLSX/PDF), a password field shown when the upload is a PDF, a plain-language consent note (DPDP), and a "Try sample statement" button.
- If the columns cannot be detected, show the **column-mapping step** (3 `<select>` dropdowns).
- **Screen 2, Dashboard + Chat** (two columns on desktop, tabs on mobile):
  - Left: KPI tiles (Income, Spend, Saved, Savings rate), a category donut, a monthly trend bar chart (Chart.js), a 50/30/20 bar, and **Tip cards** from `generate_insights()` (title, ₹/month saving, "Ask about this" button).
  - Right: chat with streaming text, **receipt chips** under each answer (click one to see the tool and data), suggested-question chips, and a "Delete my data" button.
  - A transactions table with an inline category `<select>` that calls `/recategorize` and refreshes everything.
- Routes: `POST /upload`, `GET /overview`, `GET /insights`, `GET /transactions`, `POST /recategorize`, `POST /chat` (SSE), `DELETE /session`. The session id is kept in a cookie or `localStorage`.

**Exit check:** a full flow on a fresh browser: sample statement → dashboard → ask 3 questions → recategorize one row → delete data. Take screenshots for the deck.

**Prompt**
```
Build app/static/index.html + app.js per plan.md P5 (vanilla JS, Chart.js from cdnjs, no build step) and
the remaining FastAPI routes in app/main.py. Mobile-friendly. Include upload w/ PDF password, consent
note, column-mapping fallback, KPI tiles, donut, monthly trend, 50/30/20 bar, tip cards, streaming chat
with receipt chips, transactions table with inline recategorize, delete-my-data. Run the app, walk the full
flow, take screenshots into docs/screens/. Update presentation_reference.md §5 (wireframes → real
screenshots) and the build log.
```

---

## P6 — Differentiators + evaluation (cut first if short on time)

**Deliverables**
- **What-if simulator** in the UI: sliders per top category ("cut Food & Dining by 30%"), which call `simulate_savings` and show the yearly saving and the new savings rate. Chat can call the same tool ("what if I stop ordering on weekdays?").
- **Goal planner:** "I want ₹60,000 for a trip in 6 months" → the required monthly saving vs the current surplus, and which tips close the gap (deterministic, uses existing tools).
- **Hinglish** check: the system prompt already mirrors the user's language. Test it.
- **Export:** a "Download my report" button that prints a print-styled page (`window.print()`). No PDF library needed.
- **Eval (`eval/questions.json` + `eval/run_eval.py`):** about 25 questions with expected facts from `ground_truth.json` (numbers, merchant lists, refusals). The script runs each one through the chat loop and checks (a) every expected number appears in the reply, (b) every ₹ figure in the reply appears in some tool result of that turn (the **grounding rate**), and (c) the refusal cases refuse. It prints answer accuracy, grounding rate, refusal compliance, and average latency and cost per turn.

**Exit check:** the eval report is saved to `eval/results.md`. Goals: grounding ≥ 98%, refusal compliance 100%, answer accuracy ≥ 90%.

**Prompt**
```
Implement plan.md P6: what-if sliders + goal planner (reuse simulate_savings, no new math), Hinglish
check, print-to-PDF report, and eval/run_eval.py with ~25 questions derived from ground_truth.json that
measures answer accuracy, grounding rate (every ₹ figure in reply must appear in that turn's tool results),
refusal compliance, latency and cost per turn. Run it, write eval/results.md, and put the headline numbers
in presentation_reference.md §3 (innovation evidence) and §4 (impact).
```

---

## P7 — Hardening, deploy, demo

**Deliverables**
- Limits: 10 MB upload cap, a row cap, a session TTL of 30 minutes, a friendly error for every failure path, and a no-API-key mode (dashboard and tips still work, chat is disabled with a notice).
- `README.md`: a 3-command quickstart.
- Deploy to Render or Railway, or run locally behind the demo laptop. Pre-warm with the sample statement.
- **Demo script (3 minutes):** problem stat → upload a password-protected PDF → dashboard appears → tip "Unused gym membership ₹1,499/mo" → ask "How can I save ₹5,000 a month?" → click a receipt chip to show the grounding → what-if slider → ask for a mutual-fund tip to show the guardrail → delete data.
- Finish `presentation_reference.md`: replace every `[TBD]` and add the final screenshots and metrics.

**Prompt**
```
Do plan.md P7: add upload/row/TTL limits, no-API-key mode, friendly errors, README quickstart. Run the
full demo script end to end and fix anything rough. Then finalize presentation_reference.md: fill every
[TBD] with real numbers/screenshots from this build, make sure each of the 5 sections is slide-ready.
```

---

## Explicitly out of scope (and when to add each)
- **Account Aggregator integration:** needs FIU onboarding. Add after the hackathon (research §5.3).
- **User accounts and history across months:** add SQLite when a returning-user flow is needed.
- **OCR for scanned PDFs:** bank e-statements are machine-generated. Add it if users upload photos.
- **React frontend:** only if the UI grows past one page.
