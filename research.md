# Research — Personal Finance Advisor Chatbot (PS-2)

> **Problem statement:** A conversational assistant that analyzes spending patterns from uploaded bank statements/CSV and gives saving tips.
>
> Working name: **Kharcha** ("spending" in Hindi). Research date: 7 Oct 2026.

---

## 1. The problem, in numbers

### 1.1 Indians are saving less and borrowing more
- India's **net household financial savings fell to 5.3% of GDP in FY23, a 47-year low** (down from 7.3% in FY22). [NextIAS](https://www.nextias.com/ca/current-affairs/07-07-2025/india-household-savings-fall), [Policy Circle](https://www.policycircle.org/economy/indias-household-savings-crisis/amp/)
- Between FY21 and FY23, gross household financial savings grew ~10.3% a year, but **household financial liabilities grew ~30.1% a year**. Households have been borrowing faster than they save since the pandemic. [Policy Circle](https://www.policycircle.org/?p=36841)
- RBI data shows a small recovery in FY24 (5.1% of gross national disposable income), and swings from quarter to quarter (about 3–4% of GDP, then 7.6% in Q4 FY25). [Grant Thornton](https://www.grantthornton.in/en/insights/articles/how-to-address-indias-falling-household-savings)
- The reasons given are persistent inflation squeezing purchasing power, and low real returns on deposits pushing people away from traditional saving. [Grant Thornton](https://www.grantthornton.in/insights/articles/how-to-address-indias-falling-household-savings/)

### 1.2 Most people lack the literacy to fix this on their own
- **Only 27% of Indian adults are financially literate** (NCFE Financial Literacy & Inclusion Survey 2019). [NCFE 2019 report](https://old.ncfe.org.in/images/pdfs/reports/NCFE%202019_Final_Report.pdf), [Punekar News](https://www.punekarnews.in/?p=214882)
- An older S&P global survey found **76% of Indian adults financially illiterate**. [Moneylife](https://www.moneylife.in/article/76-percentage-indian-adults-financially-illiterate-survey/44508.html)
- Financial literacy varies a lot by region. Western India scores highest, and Eastern and Central India lag. [Equities India / NCFE](https://equitiesindia.com/glossary/financial-literacy-india)

### 1.3 Spending is now digital and fragmented, which makes it invisible
- UPI handled **24.51 billion transactions (₹29.82 lakh crore) in August 2026**, the highest monthly volume so far, and **24.07 billion in September 2026**. Daily volume passed 800 million for the first time. [StartupTalky Aug](https://startuptalky.com/india-upi-transactions-august-2026-record-volume/), [StartupTalky Sep](https://startuptalky.com/india-upi-transactions-september-2026/)
- UPI volume grew almost **13,000-fold in 10 years**. [Outlook Business](https://www.outlookbusiness.com/news/upi-completes-10-years-clocks-nearly-13000-fold-rise-in-transaction-volume)
- **What this means:** a typical young earner makes dozens of ₹50–₹500 UPI payments a week (food delivery, cabs, snacks, recharges). Each one is too small to notice, but together they add up to a large amount. The bank statement records every payment, but in a form nobody can read easily (see §3.2).

### 1.4 Subscriptions leak money silently
- A YouGov survey found **more than half of subscribers pay for at least one subscription they do not use**. [YouGov](https://business.yougov.com/content/50030-subscription-graveyard-how-many-unused-subscriptions-are-consumers-currently-paying-for)
- 71% of Indian consumers spend under ₹1,000 a month on subscriptions, and 20% spend more. [Expert Market Research](https://www.expertmarketresearch.com/featured-articles/money-spent-on-subscription-services)

### 1.5 Personalized nudges do change behavior
- SMS saving-nudge experiments show that responses vary a lot between people: **about a quarter cut spending and about a quarter raised savings**. This fits mental-accounting theory. [Bank of England slides (Ruan)](https://www.bankofengland.co.uk/-/media/boe/files/events/2023/june/t-ruan-slides.pdf)
- Personalized, automated interventions are reported to make people much more likely to reach savings goals. Separate "mental accounts" (needs, wants, buffer, goals) help people stick to a plan. [LSMA paper](https://lsma.ro/index.php/lsma/article/view/2783)
- **Design implication:** generic advice ("spend less on food") does not work. Advice must be **specific to the user's own transactions** ("you spent ₹6,240 across 31 Swiggy orders; capping at 3 a week saves ~₹2,900 a month").

---

## 2. Existing solutions and the gap

| Product | What it does | Gap for our user |
|---|---|---|
| **Cleo** (US/UK) | Chat-first AI money coach with read-only bank link, plain-language spending insights, round-up savings, and voice and memory in Cleo 3.0 [Penny Hoarder](https://www.thepennyhoarder.com/budgeting/cleo-app-review/), [TNW](https://thenextweb.com/news/cleo-launches-ai-money-coach-fix-spending-habits) | Not available in India, does not understand UPI or Indian banks |
| **Copilot Money** | ML categorization and spending prediction, about $95/yr, iOS/Mac/web [Dupple](https://dupple.com/learn/best-ai-personal-finance-tools) | Paid, US bank feeds only |
| **Monarch Money** | AI assistant, auto-categorization, weekly recap, $99.99/yr [Dupple](https://dupple.com/learn/best-ai-personal-finance-tools) | Paid, US-centric |
| Indian expense apps (SMS-parsing trackers, investment apps)* | Track spends from SMS or linked accounts, push investment products | Dashboards rather than conversation, advice is often a funnel to sell products, need SMS or account permissions |
| Spreadsheets / bank app "insights" | Manual, or very coarse categories | Need effort and literacy, which is exactly what users lack |

\*This research pass did not verify the current feature sets of Indian apps. They are listed as a category only.

**The gap we target:**
1. **Upload-and-ask**: no account linking, no SMS permission, no sign-up. Drop a CSV or PDF statement and start asking questions.
2. **Built for India**: understands UPI, NEFT, IMPS and NACH narrations, Indian merchants, ₹ and lakh formatting, and password-protected bank PDFs.
3. **Explains, not just charts**: answers "where did my money go?" in plain language (English or Hinglish) and gives **actionable tips with numbers**.
4. **Trustworthy numbers**: every figure the bot states comes from code, not from the LLM's arithmetic (see §4.3).
5. **Neutral**: no product to sell, and no securities recommendations (see §5.2).

---

## 3. Data: what bank statements actually look like

### 3.1 Formats users will upload
- **CSV / XLS / XLSX** exports from net banking (HDFC, ICICI, SBI, Axis, Kotak). Column names differ between banks, for example `Narration` / `Description` / `Particulars` / `Remarks`, `Withdrawal Amt` / `Debit` / `Dr`, `Deposit Amt` / `Credit` / `Cr`, and `Value Dt` / `Txn Date`. Some banks use a single `Amount` column with a `Dr/Cr` flag column. Header rows are often **not on line 1** because there are 10–20 lines of account metadata first.
- **PDF statements** (most common, since banks email them monthly). They are usually **password-protected** (the password is often some combination of name, DOB or customer ID) and machine-generated, so text extraction works and OCR is not needed.
  - `pdfplumber.open(path, password=...)` handles encrypted, machine-generated PDFs and gives fine-grained control over table extraction. [pdfplumber README](https://cdn.jsdelivr.net/gh/jsvine/pdfplumber@stable/README.md)
  - Camelot has `lattice` (ruled tables, typical of bank statements) and `stream` modes and supports `password=`, but only ASCII passwords with algorithm code 1/2. [Camelot API](https://camelot-py.readthedocs.io/en/latest/api.html)
  - **Decision:** use pdfplumber (one dependency, no Ghostscript). If a table is not detected, fall back to sending the extracted page text to the LLM with structured outputs. Keep that as a fallback only.

### 3.2 Narrations are the hard part
Raw narrations are cryptic, and each bank formats them differently:

| Rail | Example narration | What we can extract |
|---|---|---|
| UPI P2M (merchant) | `UPI/P2M/123456789012/swiggy@ybl/ORDER-891` | VPA → merchant (`swiggy`) |
| UPI P2P (person) | `UPI/P2P/[ref]/RAHUL KUMAR` | Person transfer (→ "Transfers", name redacted before LLM) |
| NEFT | `NEFT CR:HDFC2268012345678 ABC CORP INV-2024-001` | Credit, often salary |
| IMPS | `IMPS/9876543210/RAHUL KUMAR/9876` | Transfer |
| NACH | `NACH/BATCH-20260315-001/HDFC0000001` | Auto-debit: **EMI / SIP / insurance**, so recurring |
| Cheque | `CLG/123456/HDFC0001234/20260315` | Cheque |

Sources: [Terra Insight — narration patterns](https://www.terra-insight.com/insights/bank-statement-narration-patterns-india), [Terra Insight — PDF parsing](https://www.terra-insight.com/insights/bank-statement-pdf-parsing-india), [AI Accountant — narration parsing guide](https://aiaccountant.com/blog/smart-narration-parsing-indian-statements), [upi-transaction-parser (GitHub)](https://github.com/SurajMeena/upi-transaction-parser)

- HDFC separates fields with `/`, ICICI with `-`, and Axis with spaces. A single regex will not work, so parse by **finding the VPA (`\S+@\S+`)** and by **rail prefix** (`UPI`, `NEFT`, `IMPS`, `NACH`, `ATM`, `POS`). [Terra Insight](https://www.terra-insight.com/insights/bank-narration-parsing-excel-formulas-india/)
- VPA handles show the PSP app: `@ybl` (PhonePe), `@okhdfcbank`/`@okicici`/`@oksbi` (Google Pay), `@paytm`. The **part before `@` is usually the merchant name** for P2M payments.

### 3.3 Demo data
Real statements are private, so we **generate synthetic statements** in 2 bank layouts (HDFC-style CSV, SBI-style with a single Amount + Dr/Cr column). They include realistic Indian merchants, a salary credit, rent, EMI over NACH, 3–4 subscriptions (one "forgotten"), weekend food-delivery spikes, and one anomaly. This also gives us **ground truth** to measure categorization accuracy and chat answers against.

---

## 4. Technical findings

### 4.1 Categorization: pure LLM is not good enough, hybrid is
- A benchmark by Digits found general-purpose LLMs reach **about 66% accuracy** on transaction classification, against **over 93% for purpose-built systems**. It also found more invalid-JSON and made-up-category failures in newer models. [Digits whitepaper](https://digits.com/_assets/downloads/beyond-the-hype-evaluating-llms-vs-digits-agl.pdf)
- Other reports put LLMs at 92–97% on European bank feeds, against 70–80% for rule engines. [Freenance](https://freenance.io/financial-tools/ai-categorization-transactions-2026-europe-how-it-works-accuracy-banks-supported-vs-rules-comparison/)
- **Hybrid rules + ML + conditional LLM** reached **98.43%**. [transaction-ai benchmarks](https://transaction-ai.readthedocs.io/en/latest/BENCHMARKS/)
- Using two LLM agents (classify, then verify) beats using one. [Parafin](https://www.parafin.com/blog/why-two-llm-agents-beat-one-on-financial-classification)
- **Decision, a three-tier categorizer:**
  1. **Rules**: a dictionary of Indian merchants and VPAs (Swiggy, Zomato, Uber, Ola, Rapido, Blinkit, Zepto, BigBasket, Amazon, Flipkart, Myntra, Netflix, Spotify, Hotstar, Jio, Airtel, IRCTC, BESCOM/MSEB…) plus rail rules (NACH → EMI/Investments, salary keywords → Income, ATM → Cash). Fast, free and deterministic.
  2. **LLM fallback** only for rows the rules did not match. These are batched, deduplicated by merchant key, and returned through **structured outputs** (a JSON schema whose `enum` lists our fixed categories, so the LLM cannot invent a category).
  3. **User correction → new rule** ("Swiggy Instamart is Groceries, not Food"). The fix is stored and applied from then on.

### 4.2 Category taxonomy (fixed, enum)
`Income, Rent, Bills & Utilities, Groceries, Food & Dining, Transport, Shopping, Entertainment & Subscriptions, Health, Education, EMI & Loans, Investments, Insurance, Transfers, Cash Withdrawal, Fees & Charges, Other`. Each category is tagged **Need / Want / Savings** so we can apply the 50/30/20 rule (50% needs, 30% wants, 20% savings).

### 4.3 LLMs make up numbers. Compute in code, talk in LLM.
- When LLMs summarize tables they **"hallucinate numerical values, misattribute entities to rows, fabricate rankings, and conflate temporal references."** [Semantic Layers paper, arXiv 2604.25149](https://arxiv.org/pdf/2604.25149)
- The same paper found that giving models **explicit semantic definitions** lifted accuracy from **about 45–50% to about 68%** for every model tested. Most of the gain came from turning "inference" into "retrieval". [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Free-form text-to-SQL has its own schema and logic hallucinations. [arXiv 2512.22250](https://arxiv.org/html/2512.22250v1), [arXiv 2405.15307](https://arxiv.org/pdf/2405.15307)
- **Decision:** do **not** give the LLM the raw CSV and do **not** let it write SQL or pandas code. Give it a **small set of typed, deterministic tools** (a "semantic layer"): `get_overview`, `category_breakdown`, `top_merchants`, `monthly_trend`, `find_recurring`, `find_anomalies`, `search_transactions`, `simulate_savings`. The LLM picks the tools and explains the results. **Every number in a reply comes from a tool result**, and the UI shows those results as clickable "receipts". This is the core trust feature.

### 4.4 Saving tips: rules-driven, LLM-phrased
Insight generators are deterministic. Each one outputs `{type, evidence, monthly_saving_estimate}`:

| Insight | Logic |
|---|---|
| **50/30/20 check** | Share of Needs, Wants and Savings vs the 50/30/20 targets |
| **Subscription audit** | Same merchant, similar amount (±10%), roughly 30-day interval, 2 or more times → recurring. Flag ones with no other use |
| **Small-spend leak ("latte factor")** | Count and sum of debits under ₹300 by merchant. Shows the cumulative cost of habits |
| **Category spike** | This month vs the average of earlier months, flagged if more than 1.5× |
| **Anomaly** | Debit more than 3× the median in its category, or a first-time merchant over ₹5,000 |
| **Weekend effect** | Weekend vs weekday spending per day |
| **Fees** | Bank charges, late fees, ATM fees: costs that can be avoided completely |
| **Emergency-fund runway** | Average balance ÷ average monthly Needs = months covered (target is 6) |

The LLM turns these into friendly, prioritized tips. It **may not add numbers** that the insights do not contain.

### 4.5 LLM choice (Claude API)
From the Claude API reference (cached 2026-09-25):

| Model | ID | Input / Output per 1M tokens | Use |
|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | $4 / $20 | Default for chat with tool use (`effort: "low"` for chat routes to cut cost and latency) |
| Claude Haiku 4.5 | `claude-haiku-4-5` | $1 / $5 | Optional: bulk categorization of unmatched merchants, only if cost or latency matters |

API notes that affect the design:
- **Structured outputs** use `output_config: {format: …}` (the old `output_format` is deprecated). Tools use `strict: true` for schema-valid arguments.
- **Forced `tool_choice` (`any`/`tool`) returns a 400 on Opus 5.5.** Use `auto` with a prompt instruction, or use structured outputs.
- Thinking cannot be disabled on Opus 5.5. Control it with `effort`, whose **default is `medium`**, so set it explicitly.
- **No assistant prefill.** Stream chat responses. Enable server-side refusal `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`).
- Prompt caching: keep the system prompt and tool list byte-stable so they cache across chat turns.
- Rough cost: one chat turn is about 6k input + 600 output tokens ≈ **$0.036** on Opus 5.5 before caching. A 50-turn demo costs well under $2.

### 4.6 Stack decision (hackathon-optimized)
| Layer | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** | pandas and pdfplumber are Python, and there is one language end to end |
| Data | **pandas DataFrame in memory**, per session | A statement is a few thousand rows at most, so no database is needed. Add SQLite only if multi-user history becomes necessary |
| PDF | **pdfplumber** | Supports passwords and needs no system dependencies |
| LLM | **Anthropic Python SDK**, `claude-opus-5-5` | Tool use, structured outputs and streaming |
| Frontend | **Single `index.html` + vanilla JS + Chart.js (CDN)**, served by FastAPI | No build step, one deploy. Move to React only if the UI grows past one page |
| Streaming | Server-Sent Events (`StreamingResponse`) | Native browser `EventSource` / `fetch` stream |
| Deploy | Render / Railway / a local laptop | One `uvicorn` process |

---

## 5. Privacy, regulation and trust

### 5.1 DPDP Act 2023 + DPDP Rules 2025
- The **DPDP Rules were notified on 14 Nov 2025**. Most obligations (rules 3, 5–16, 22–23) take effect **18 months after publication, around May 2027**. [Mondaq](https://www.mondaq.com/india/data-protection/1708164/digital-personal-data-protection-rules-2025-notified), [SCC Online](https://www.scconline.com/blog/post/2025/11/14/meity-notified-digital-personal-data-protection-rules-2025/), [PIB](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf)
- A consent notice must be **standalone, in clear and plain language**, list the **personal data itemized** with its **specific purpose**, and allow **withdrawing consent as easily as giving it**. [SCC Online](https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/)
- **Our design (privacy by default):**
  - A plain-language consent screen before upload ("we read your statement only to answer your questions; nothing is stored after you close the tab").
  - **Data is processed in memory only**, the session has a TTL, and a **"Delete my data"** button wipes it immediately.
  - **PII redaction before anything is sent to the LLM**: account numbers, phone numbers, emails and P2P counterparty names are masked (`RAHUL KUMAR` → `Person#3`). Only merchant names, amounts, dates and categories go to the LLM, and in most turns only **aggregates** (tool results), not raw rows.

### 5.2 SEBI: do not become an unregistered investment adviser
- SEBI requires **registration for anyone giving investment advice on securities**, directly or indirectly. Labelling it "for educational purposes" does not exempt buy/sell calls. [Outlook Money](https://www.outlookmoney.com/news/sebi-vs-finfluencers-market-regulator-introduces-new-rule-to-curb-spread-of-investment-advice-from-unregistered-advisories), [Sansa Legal](https://www.sansalegal.com/post/sebi-rules-education-courses-providing-buy-sell-calls-constitute-unregistered-investment-advisory-ac)
- SEBI's position on AI is that **using AI does not reduce the adviser's accountability**. [Mondaq](https://webiis10.mondaq.com/india/securities/1759228/sebis-new-digital-compliance-rules-what-investment-advisers-must-know-in-2026)
- **Our guardrail:** the bot gives **budgeting and saving guidance** (spending, subscriptions, emergency fund, the general idea of saving a set % each month). It **refuses to name specific stocks, mutual funds or securities** and suggests consulting a SEBI-registered adviser. This is enforced in the system prompt and checked in our eval set.

### 5.3 Future integration: the Account Aggregator (AA) framework
- AA is RBI's consent-based framework for sharing financial data. As of 31 Mar 2026: **179 FIPs live, 2.88 billion accounts enabled, 284.6 million accounts linked, 989 FIUs live**. [Dept. of Financial Services](https://financialservices.gov.in/account-aggregator-framework), [HyperVerge](https://hyperverge.co/blog/account-aggregator-framework-rbi/)
- **Future scope:** replace manual upload with AA consent-based fetching (we would become an FIU through a licensed AA). This gives live, structured data and removes PDF parsing entirely. It is out of scope for the hackathon because it needs regulatory onboarding.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Unknown bank format breaks the parser | Column auto-detection by synonyms plus a header-row search. If that fails, a "map your columns" UI (3 dropdowns). If that fails, LLM structured extraction |
| Wrong categories → wrong advice | Hybrid categorizer, a confidence flag, one-click recategorize that learns a rule, and an eval against synthetic ground truth |
| LLM makes up numbers | Tools-only numbers, receipts shown in the UI, a system-prompt rule, and an eval check comparing figures in replies with tool outputs |
| Privacy leak | PII redaction, aggregates-only by default, no persistence, delete button |
| Regulatory overreach (investment advice) | Hard guardrail with a refusal plus a pointer to a SEBI-registered adviser. Eval cases for it |
| Demo-day API failure | Cached demo session plus a deterministic "insights" panel that works without the LLM |

---

## 7. References
1. NextIAS — Concern over falling household savings in India (2025). https://www.nextias.com/ca/current-affairs/07-07-2025/india-household-savings-fall
2. Policy Circle — India's household savings crisis. https://www.policycircle.org/?p=36841
3. Grant Thornton Bharat — How to address India's falling household savings. https://www.grantthornton.in/en/insights/articles/how-to-address-indias-falling-household-savings
4. NCFE — Financial Literacy & Inclusion Survey 2019. https://old.ncfe.org.in/images/pdfs/reports/NCFE%202019_Final_Report.pdf
5. Moneylife — 76% Indian adults financially illiterate. https://www.moneylife.in/article/76-percentage-indian-adults-financially-illiterate-survey/44508.html
6. StartupTalky — UPI August 2026 record volume. https://startuptalky.com/india-upi-transactions-august-2026-record-volume/
7. StartupTalky — UPI September 2026. https://startuptalky.com/india-upi-transactions-september-2026/
8. Outlook Business — UPI completes 10 years. https://www.outlookbusiness.com/news/upi-completes-10-years-clocks-nearly-13000-fold-rise-in-transaction-volume
9. YouGov — Subscription graveyard. https://business.yougov.com/content/50030-subscription-graveyard-how-many-unused-subscriptions-are-consumers-currently-paying-for
10. Expert Market Research — Money spent on subscription services. https://www.expertmarketresearch.com/featured-articles/money-spent-on-subscription-services
11. Bank of England (Ruan) — Saving nudges, slides. https://www.bankofengland.co.uk/-/media/boe/files/events/2023/june/t-ruan-slides.pdf
12. LSMA — Behavioral finance in the digital age. https://lsma.ro/index.php/lsma/article/view/2783
13. Penny Hoarder — Cleo review 2026. https://www.thepennyhoarder.com/budgeting/cleo-app-review/
14. TNW — Cleo launches AI money coach. https://thenextweb.com/news/cleo-launches-ai-money-coach-fix-spending-habits
15. Dupple — Best AI personal finance tools 2026. https://dupple.com/learn/best-ai-personal-finance-tools
16. Terra Insight — Bank statement narration patterns (India). https://www.terra-insight.com/insights/bank-statement-narration-patterns-india
17. Terra Insight — Bank statement PDF parsing (India). https://www.terra-insight.com/insights/bank-statement-pdf-parsing-india
18. AI Accountant — Smart narration parsing for Indian statements. https://aiaccountant.com/blog/smart-narration-parsing-indian-statements
19. GitHub — upi-transaction-parser. https://github.com/SurajMeena/upi-transaction-parser
20. pdfplumber README. https://cdn.jsdelivr.net/gh/jsvine/pdfplumber@stable/README.md
21. Camelot API reference. https://camelot-py.readthedocs.io/en/latest/api.html
22. Digits — Beyond the hype: evaluating LLMs vs Digits AGL. https://digits.com/_assets/downloads/beyond-the-hype-evaluating-llms-vs-digits-agl.pdf
23. transaction-ai — Classification benchmarks. https://transaction-ai.readthedocs.io/en/latest/BENCHMARKS/
24. Parafin — Why two LLM agents beat one on financial classification. https://www.parafin.com/blog/why-two-llm-agents-beat-one-on-financial-classification
25. Freenance — AI transaction categorisation 2026 (EU). https://freenance.io/financial-tools/ai-categorization-transactions-2026-europe-how-it-works-accuracy-banks-supported-vs-rules-comparison/
26. arXiv 2604.25149 — Semantic layers for reliable LLM-powered data analytics. https://arxiv.org/abs/2604.25149
27. arXiv 2512.22250 — Hallucination detection for LLM text-to-SQL. https://arxiv.org/html/2512.22250v1
28. Mondaq — DPDP Rules 2025 notified. https://www.mondaq.com/india/data-protection/1708164/digital-personal-data-protection-rules-2025-notified
29. SCC Online — DPDP Rules 2025 key highlights. https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/
30. PIB — DPDP Rules 2025 document. https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf
31. Outlook Money — SEBI vs finfluencers. https://www.outlookmoney.com/news/sebi-vs-finfluencers-market-regulator-introduces-new-rule-to-curb-spread-of-investment-advice-from-unregistered-advisories
32. Mondaq — SEBI digital compliance rules 2026. https://webiis10.mondaq.com/india/securities/1759228/sebis-new-digital-compliance-rules-what-investment-advisers-must-know-in-2026
33. Dept. of Financial Services — Account Aggregator framework. https://financialservices.gov.in/account-aggregator-framework
34. HyperVerge — Account Aggregator framework 2026 guide. https://hyperverge.co/blog/account-aggregator-framework-rbi/
