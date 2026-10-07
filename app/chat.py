"""PII redaction + Groq (OpenAI-style) tool-use loop. Numbers come from analytics tools; the model only explains them."""
import json
import os
import re

from app import analytics as an
from app.categorize import CATEGORIES

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TURNS = 8

SYSTEM = """You are Kharcha, a friendly Indian personal-finance coach. You help the user understand their own bank statement and save money.

Rules:
- Reply in the user's language: English, or Hinglish if they write in Hinglish.
- Every number you state must come from a tool result in this conversation. Never estimate, add up or compute totals yourself. If you need a number, call a tool. If the data cannot answer the question, say so.
- Never add, subtract or compute percentages yourself, including totals of tips: quote the tool's figures one by one. Use the whole statement (period null) unless the user names a month.
- Write money in rupees with Indian digit grouping, e.g. ₹1,23,456.
- Give tips as specific actions with the expected monthly saving, taken from `monthly_saving_estimate` or `simulate_savings`.
- Do not recommend specific stocks, mutual funds or other securities. For investment-product questions, explain only the general principle in words (emergency fund first, diversification, low costs), give no allocation percentages or fund names, and suggest a SEBI-registered investment adviser.
- Merchant and person names in tool results are already masked; use them as given.
- Keep answers short: a direct answer first, then at most three supporting points."""

PERIOD = {"type": ["string", "null"], "description": "'last_month', a month like '2026-08', or null for all data"}
STR = lambda d: {"type": ["string", "null"], "description": d}
_CHANGE = {"type": "object", "additionalProperties": False, "required": ["category", "merchant", "cut_pct"], "properties": {
    "category": {"type": ["string", "null"], "enum": CATEGORIES + [None]}, "merchant": STR("merchant key, if cutting one merchant"),
    "cut_pct": {"type": "number", "description": "percent reduction, 0-100"}}}


def _tool(name, description, props):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}}}


TOOLS = [
    _tool("get_overview", "Income, spend, net savings, savings rate and balance trend for a period.", {"period": PERIOD}),
    _tool("category_breakdown", "Spend by category for a period, optionally limited to a bucket.",
          {"period": PERIOD, "bucket": {"type": ["string", "null"], "enum": ["Need", "Want", "Savings", "Transfer", None]}}),
    _tool("top_merchants", "Top merchants by spend, optionally within one category.",
          {"period": PERIOD, "category": {"type": ["string", "null"], "enum": CATEGORIES + [None]}, "n": {"type": "integer"}}),
    _tool("monthly_trend", "Monthly spend, optionally for one category.", {"category": {"type": ["string", "null"], "enum": CATEGORIES + [None]}}),
    _tool("search_transactions", "Find individual transactions.", {
        "query": STR("text to match in merchant or narration"), "category": {"type": ["string", "null"], "enum": CATEGORIES + [None]},
        "min_amount": {"type": ["number", "null"]}, "period": PERIOD, "limit": {"type": "integer"}}),
    _tool("find_recurring", "Recurring payments and subscriptions with monthly cost, flagging ones to check for usage.", {}),
    _tool("find_anomalies", "Unusually large or one-off transactions.", {}),
    _tool("generate_insights", "Personalised saving insights, each with a monthly saving estimate. Use for any 'how can I save' question.", {}),
    _tool("plan_goal", "Savings goal planner: monthly saving needed for a target amount in N months vs the current surplus, and which tips close the gap.",
          {"target": {"type": "number"}, "months": {"type": "integer"}}),
    _tool("simulate_savings", "What-if: saving and new savings rate if spending in categories or merchants is cut by a percentage.",
          {"changes": {"type": "array", "items": _CHANGE}, "months": {"type": "integer"}}),
]
FUNCS = {f.__name__: f for f in (an.get_overview, an.category_breakdown, an.top_merchants, an.monthly_trend, an.search_transactions,
                                 an.find_recurring, an.find_anomalies, an.generate_insights, an.simulate_savings, an.plan_goal)}

_ACCT, _PHONE, _EMAIL = re.compile(r"\d{9,18}"), re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"), re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def redact(df):
    """Copy of df safe to show the model: P2P people -> Person#n, long digit runs/phones/emails masked."""
    df = df.copy()
    people = {}
    for i, name in df["counterparty"].dropna().items():
        people.setdefault(name, f"Person#{len(people) + 1}")
    narr = []
    cps = [c if isinstance(c, str) else None for c in df["counterparty"]]
    for n, cp in zip(df["narration"], cps):
        if cp:
            n = re.sub(re.escape(cp), people[cp], n, flags=re.I)
            n = re.sub(r"[\w.]+@\w+", people[cp], n)
        n = _EMAIL.sub("[email]", n)
        narr.append(_ACCT.sub("[acct]", _PHONE.sub("[phone]", n)))
    df["narration"] = narr
    df["merchant"] = [people[cp] if cp else m for m, cp in zip(df["merchant"], cps)]
    return df


def run_tool(df, name, args):
    args = {k: v for k, v in args.items() if v is not None}
    if name == "simulate_savings":
        args["changes"] = [{k: v for k, v in c.items() if v is not None} for c in args.get("changes", [])]
    return FUNCS[name](df, **args)


def stream_chat(session, user_text, client=None):
    """Yields (event, data): ('text', delta) | ('receipt', {tool,args,result}) | ('usage', {...}) | ('notice', msg) | ('done', None)."""
    if client is None:
        if not os.environ.get("GROQ_API_KEY"):
            yield "notice", "Chat is off: set GROQ_API_KEY on the server. The dashboard and tips still work."
            yield "done", None
            return
        import groq
        client = groq.Groq()
    import groq

    df = redact(session["df"])
    msgs = session["history"]
    msgs.append({"role": "user", "content": user_text})
    try:
        for _ in range(MAX_TURNS):
            text, calls, finish, usage = "", {}, None, None
            for chunk in client.chat.completions.create(model=MODEL, messages=[{"role": "system", "content": SYSTEM}] + msgs, tools=TOOLS,
                                                        tool_choice="auto", stream=True, max_tokens=2048, temperature=0.2):
                usage = getattr(getattr(chunk, "x_groq", None), "usage", None) or getattr(chunk, "usage", None) or usage
                if not chunk.choices:
                    continue
                ch = chunk.choices[0]
                finish = ch.finish_reason or finish
                if ch.delta.content:
                    text += ch.delta.content
                    yield "text", ch.delta.content
                for tc in ch.delta.tool_calls or []:
                    c = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    c["id"] = tc.id or c["id"]
                    if tc.function:
                        c["name"] += tc.function.name or ""
                        c["arguments"] += tc.function.arguments or ""
            if usage:
                yield "usage", {"input_tokens": getattr(usage, "prompt_tokens", 0), "output_tokens": getattr(usage, "completion_tokens", 0)}
            msgs.append({"role": "assistant", "content": text or None, **({"tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls.values()]} if calls else {})})
            if finish == "length":
                yield "notice", "(answer cut short, ask me to continue)"
                break
            if not calls:
                break
            for c in calls.values():  # one tool message per call
                try:
                    args = json.loads(c["arguments"] or "{}")
                    out = run_tool(df, c["name"], args)
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(out)})
                    yield "receipt", {"tool": c["name"], "args": args, "result": out}
                except Exception as e:
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": f"error: {e}"})
    except groq.APIError as e:
        yield "notice", f"The AI service had a problem ({type(e).__name__}). Please try again."
    yield "done", None
