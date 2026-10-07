"""Narration parsing + hybrid categorization: user overrides -> rules -> LLM fallback (enum-constrained)."""
import json
import os
import re
from pathlib import Path

BUCKET = {
    "Income": "Income", "Rent": "Need", "Groceries": "Need", "Utilities & Bills": "Need", "EMI & Loans": "Need",
    "Transport": "Need", "Fees & Charges": "Need", "Health & Fitness": "Need", "Education": "Need",
    "Food & Dining": "Want", "Shopping": "Want", "Subscriptions": "Want", "Entertainment": "Want", "Other": "Want",
    "Investments": "Savings", "Cash Withdrawal": "Transfer", "Transfers": "Transfer",
}
CATEGORIES = list(BUCKET)
MERCHANTS = json.loads((Path(__file__).parent / "merchants.json").read_text())
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

RAILS = ["UPI", "NEFT", "IMPS", "RTGS", "NACH", "ECS", "ACH", "ATM", "POS", "CLG", "CHARGES", "CHG"]
VPA = re.compile(r"([A-Za-z0-9._]+)@([A-Za-z0-9]+)")
NOISE = set(RAILS) | {"P2M", "P2A", "P2P", "DR", "CR", "WDL", "NFS", "CASH", "PAYMENT", "TO", "BY", "TRANSFER"}


def parse_narration(s):
    """-> {rail, vpa, merchant_key, counterparty, p2p}. Handles '/', '-', ':' and space separated narrations."""
    s = str(s)
    up = s.upper()
    rail = next((r for r in RAILS if re.match(rf"\W*{r}\b", up)), "")
    rail = {"CHG": "CHARGES", "ECS": "NACH", "ACH": "NACH"}.get(rail, rail)
    m = VPA.search(s)
    vpa = m.group(0).lower() if m else None
    tokens = [t for t in re.split(r"[/\-:\s]+", VPA.sub(" ", s)) if t and not t.isdigit() and t.upper() not in NOISE]
    tokens = [t for t in tokens if not re.fullmatch(r"[A-Z]{4}0\w{6}|[A-Z]?\d[\w]*\d", t)]  # IFSC codes, refs
    p2p = bool(re.search(r"\bP2A\b", up)) or (rail == "IMPS" and not vpa)
    key = m.group(1).lower() if m else " ".join(tokens[:3]).lower()
    counterparty = None
    if p2p:
        counterparty = re.sub(r"[._]+", " ", m.group(1)).title() if m else " ".join(tokens[:2]).title()
    return dict(rail=rail, vpa=vpa, merchant_key=key.strip(), counterparty=counterparty, p2p=p2p)


def _dict_match(text):
    tl = text.lower()
    for kw, cat in MERCHANTS.items():
        if (kw in tl) if len(kw) >= 5 else re.search(rf"\b{re.escape(kw)}\b", tl):
            return cat


def _rule(narration, amount, p):
    low = narration.lower()
    if p["rail"] == "CHARGES" or re.search(r"late payment|penalty|\bfee\b|\bcharges?\b", low):
        return "Fees & Charges"
    if p["rail"] == "ATM":
        return "Cash Withdrawal"
    if p["rail"] == "NACH":
        return "Investments" if re.search(r"\bsip\b|\bmf\b|mutual|zerodha|groww|kuvera", low) else "EMI & Loans"
    if amount > 0 and (p["rail"] in ("NEFT", "IMPS", "RTGS") or "salary" in low):
        return "Income"
    if p["rail"] == "IMPS" and "rent" in low:
        return "Rent"
    hit = _dict_match(f"{p['merchant_key']} {low}")
    if hit:
        return hit
    if p["p2p"]:
        return "Transfers"
    if amount > 0:
        return "Income"


def _redact(s, p):
    s = re.sub(r"\d{6,}", "#", s)
    if p["counterparty"]:
        s = re.sub(re.escape(p["counterparty"]), "PERSON", s, flags=re.I)
        s = re.sub(r"[A-Za-z0-9._]+@\w+", "PERSON@vpa", s)
    return s


_LLM_CACHE = {}  # merchant_key -> category, in memory per process


def _llm_categorize(items):
    """items: {merchant_key: redacted narration}. Returns {merchant_key: category}. 'Other' when no API key / error."""
    todo = {k: v for k, v in items.items() if k not in _LLM_CACHE}
    if todo and os.environ.get("GROQ_API_KEY"):
        try:
            import groq
            r = groq.Groq(max_retries=4).chat.completions.create(
                model=MODEL, temperature=0, max_tokens=6000, reasoning_effort="low", response_format={"type": "json_object"}, messages=[
                    {"role": "system", "content": "You categorize Indian bank-statement transactions. Each item is a merchant key and one example "
                     "narration (personal data already masked). Allowed categories: " + json.dumps(CATEGORIES) + '. Reply with JSON '
                     '{"results": [{"merchant_key": str, "category": one allowed category, "confidence": 0-1}]} and nothing else.'},
                    {"role": "user", "content": json.dumps(todo)}])
            for x in json.loads(r.choices[0].message.content)["results"]:
                if x.get("merchant_key") in todo:  # enum enforced here: anything outside the taxonomy becomes Other
                    _LLM_CACHE[x["merchant_key"]] = x["category"] if x.get("category") in BUCKET else "Other"
        except Exception as e:  # network, auth, bad JSON... degrade to Other rather than fail the upload
            print("LLM categorization skipped:", e)
    return {k: _LLM_CACHE.get(k, "Other") for k in items}


def categorize(df, overrides=None, use_llm=True):
    """Adds merchant, rail, category, bucket, cat_source columns. overrides: {merchant_key: category}."""
    overrides = overrides or {}
    out = []
    for narr, amt in zip(df["narration"], df["amount"]):
        p = parse_narration(narr)
        if p["merchant_key"] in overrides:
            out.append((p, overrides[p["merchant_key"]], "user"))
        else:
            c = _rule(narr, amt, p)
            out.append((p, c, "rule" if c else None))
    df = df.copy()
    pending = {p["merchant_key"]: _redact(n, p) for (p, c, _), n in zip(out, df["narration"]) if c is None}
    llm = _llm_categorize(pending) if pending and use_llm else {}
    cats, srcs = [], []
    for p, c, src in out:
        if c is None:
            c, src = llm.get(p["merchant_key"], "Other"), ("llm" if p["merchant_key"] in llm and p["merchant_key"] in _LLM_CACHE else "rule")
        cats.append(c)
        srcs.append(src)
    df["merchant"] = [p["merchant_key"] for p, _, _ in out]
    df["rail"] = [p["rail"] for p, _, _ in out]
    df["counterparty"] = [p["counterparty"] for p, _, _ in out]
    df["category"], df["cat_source"] = cats, srcs
    df["bucket"] = df["category"].map(BUCKET)
    return df


def recategorize(df, overrides, merchant_key, category):
    """Store a user override and re-apply it to every row of that merchant."""
    assert category in BUCKET, category
    overrides[merchant_key] = category
    m = df["merchant"] == merchant_key
    df.loc[m, ["category", "cat_source"]] = [category, "user"]
    df.loc[m, "bucket"] = BUCKET[category]
    return df
