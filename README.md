# Credence — your bank statement, told like a story

Upload a bank statement (CSV, XLSX or password-protected PDF), watch your money Wrapped (roast or hype mode), see where the money goes, get saving tips in ₹, and chat with an advisor whose numbers always come from code, not from the model (LLM: Groq).

## Quickstart
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # add GROQ_API_KEY to enable chat (dashboard and tips work without it)
.venv/bin/uvicorn app.main:app --port 8000   # open http://localhost:8000
```
Deploy (Render/Railway): start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env var `GROQ_API_KEY`.

## Checks
```bash
.venv/bin/python scripts/make_sample.py     # regenerate data/samples (seeded)
.venv/bin/python tests/test_core.py         # ingestion, categorization, analytics, redaction, chat loop (fake client)
.venv/bin/python eval/run_eval.py           # 25-question eval against the real model; writes eval/results.md (needs API key)
```

## 3-minute demo script
1. Problem: household savings at a 47-year low, 24 billion UPI payments a month, nobody can read their statement.
2. Click **Try sample PDF (password-protected)** → dashboard appears in under a second.
3. Tip card: "check if you use cultfit (₹1,499/month)".
4. Chat: "How can I save ₹5,000 a month?" → click a 🧾 receipt chip to show the tool output behind each number.
5. What-if slider: cut Food & Dining 30%. Goal planner: ₹90,000 in 6 months.
6. Chat: "Which mutual fund should I buy?" → polite refusal pointing to a SEBI-registered adviser.
7. **Delete my data**.

## Design
- `app/ingest.py` any statement → normalized table · `app/categorize.py` narration parser, rules, LLM fallback with a fixed category enum · `app/analytics.py` deterministic insights (the LLM's tools) · `app/chat.py` PII redaction + tool-use loop · `app/main.py` routes · `app/static/` single-page UI.
- Privacy: in-memory sessions (30 min TTL), masked before the model sees anything, one-click delete. Limits: 10 MB upload, 20,000 rows.
- Budgeting help only. No securities recommendations.
