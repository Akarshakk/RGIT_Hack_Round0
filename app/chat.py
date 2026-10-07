"""PII redaction + Groq (OpenAI-style) tool-use loop. Numbers come from analytics tools; the model only explains them."""
import json
import os
import re
import time

from app import analytics as an
from app import grounding
from app.categorize import CATEGORIES

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK = os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")  # separate rate-limit bucket on Groq
HISTORY_TURNS = 3  # user turns of history sent to the model; the free tier allows 8k tokens/minute
MAX_TURNS = 8

SYSTEM = """You are Credence, a friendly Indian personal-finance coach. You help the user understand their own bank statement and save money.

Language:
- Mirror the user. If they write Hindi or Hinglish (words like kitna, kya, mera, kharcha, paisa, bata, hai), reply in Hinglish written in Roman script. Otherwise reply in English.

Numbers (most important):
- Every number you state must be copied from a tool result in this conversation, or from the user's own message. Call a tool whenever you need a number. If the data cannot answer, say so.
- Never work numbers out yourself: no adding categories or tips together, no shares or percentages unless a tool returned that exact `pct`, no "≈", "about" or "roughly" figures. Each answer is automatically checked and any number not found in a tool result is flagged to the user.
- Use the whole statement (period null) unless the user names a month or says "last month".
- Write money in rupees with Indian digit grouping, e.g. ₹1,23,456.

Advice:
- Give tips as specific actions with the expected monthly saving, taken from `monthly_saving_estimate`, `quick_wins` or `simulate_savings`.
- For "future me / long term / what will this become" questions, use `future_you` and say its rate is illustrative, not a promise.
- Merchant and person names in tool results are already masked; use them as given.

Investments (regulatory, non-negotiable):
- You are not a SEBI-registered investment adviser. If asked which stock, mutual fund, fund type, SIP, ETF, crypto or other security to buy, or how to allocate money between them: say in one or two sentences that you can't recommend investments, suggest a SEBI-registered investment adviser, and offer budgeting help instead (for example how much they could free up each month, via `quick_wins`). Do not name fund categories, returns, benchmarks or allocation percentages.

Style: a direct answer first, then at most three short bullets. Prefer bullets over tables. Keep it under 120 words."""

PERIOD = {"type": ["string", "null"], "description": "'last_month', a month like '2026-08', or null for all data"}
STR = lambda d: {"type": ["string", "null"], "description": d}
_CHANGE = {"type": "object", "additionalProperties": False, "required": ["cut_pct"], "properties": {
    "category": {"type": ["string", "null"], "enum": CATEGORIES + [None]}, "merchant": STR("merchant key, if cutting one merchant"),
    "cut_pct": {"type": "number", "description": "percent reduction, 0-100"}}}


def _optional(spec):
    t = spec.get("type")
    return isinstance(t, list) and "null" in t


def _tool(name, description, props):
    """Nullable parameters are optional: Groq validates tool calls and rejects ones missing a 'required' field."""
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "additionalProperties": False,
                           "required": [k for k, v in props.items() if not _optional(v)], "properties": props}}}


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
    _tool("future_you", "Illustrative long-term value of a monthly saving (defaults to the user's quick wins), compounded at an assumed annual rate.",
          {"monthly": {"type": ["number", "null"], "description": "rupees per month; null = the quick-wins total"},
           "years": {"type": "integer"}, "rate_pct": {"type": ["number", "null"], "description": "illustrative annual rate, default 10"}}),
    _tool("friend_ledger", "Money sent to and received back from people over UPI/IMPS, per person.", {}),
    _tool("quick_wins", "The few non-overlapping saving actions and their combined monthly total.", {}),
    _tool("simulate_savings", "What-if: saving and new savings rate if spending in categories or merchants is cut by a percentage.",
          {"changes": {"type": "array", "items": _CHANGE}, "months": {"type": "integer"}}),
]
FUNCS = {f.__name__: f for f in (an.get_overview, an.category_breakdown, an.top_merchants, an.monthly_trend, an.search_transactions,
                                 an.find_recurring, an.find_anomalies, an.generate_insights, an.simulate_savings, an.plan_goal,
                                 an.future_you, an.friend_ledger, an.quick_wins)}

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


def _create(client, groq, messages, tries=3):
    """Start a streamed completion. On a rate limit, switch to the fallback model (its own quota) before waiting; also
    retries transient server errors and the model's occasional malformed tool call (Groq 400 tool_use_failed)."""
    models = [MODEL, FALLBACK] if FALLBACK and FALLBACK != MODEL else [MODEL]
    for i in range(tries):
        model = models[min(i, len(models) - 1)]
        try:
            return client.chat.completions.create(model=model, messages=messages, tools=TOOLS, tool_choice="auto", stream=True,
                                                  max_tokens=1000, temperature=0.2, reasoning_effort="low")
        except (getattr(groq, "RateLimitError", ()), getattr(groq, "InternalServerError", ()), getattr(groq, "APIConnectionError", ())):
            if i == tries - 1:
                raise
            if i + 1 >= len(models):
                time.sleep(2.0 * i)
        except getattr(groq, "BadRequestError", ()) as e:
            if "tool_use_failed" not in str(e) or i == tries - 1:
                raise
            print("retrying malformed tool call")


def _for_model(result):
    """Tool result as the model sees it: evidence row-id lists dropped (the UI receipt keeps the full result)."""
    if isinstance(result, dict):
        return {k: _for_model(v) for k, v in result.items() if k not in ("ids", "evidence_ids")}
    if isinstance(result, list):
        return [_for_model(v) for v in result]
    return result


def _recent(msgs):
    """The last HISTORY_TURNS user turns with their tool calls, cut at a user message so tool pairs stay intact."""
    starts = [i for i, m in enumerate(msgs) if m["role"] == "user"]
    return msgs[starts[-HISTORY_TURNS]:] if len(starts) > HISTORY_TURNS else msgs


def stream_chat(session, user_text, client=None):
    """Yields (event, data): ('text', delta) | ('receipt', {tool,args,result}) | ('usage', {...}) | ('notice', msg) | ('done', None)."""
    if client is None:
        if not os.environ.get("GROQ_API_KEY"):
            yield "notice", "Chat is off: set GROQ_API_KEY on the server. The dashboard and tips still work."
            yield "done", None
            return
        import groq
        client = groq.Groq(max_retries=0)  # _create handles retries and the fallback model
    import groq

    df = redact(session["df"])
    msgs = session["history"]
    msgs.append({"role": "user", "content": user_text})
    answer, results = "", []
    try:
        bad_calls = 0
        for _ in range(MAX_TURNS):
            text, calls, finish, usage = "", {}, None, None
            try:
                for chunk in _create(client, groq, messages=[{"role": "system", "content": SYSTEM}] + _recent(msgs)):
                    usage = getattr(getattr(chunk, "x_groq", None), "usage", None) or getattr(chunk, "usage", None) or usage
                    if not chunk.choices:
                        continue
                    ch = chunk.choices[0]
                    finish = ch.finish_reason or finish
                    if ch.delta.content:
                        text += ch.delta.content
                        answer += ch.delta.content
                        yield "text", ch.delta.content
                    for tc in ch.delta.tool_calls or []:
                        c = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                        c["id"] = tc.id or c["id"]
                        if tc.function:
                            c["name"] += tc.function.name or ""
                            c["arguments"] += tc.function.arguments or ""
            except getattr(groq, "APIError", Exception) as e:
                # a malformed tool call fails validation before any text is shown: ask the model again
                if "validation failed" in str(e) and not text and bad_calls < 2:
                    bad_calls += 1
                    print("retrying round after tool-call validation error")
                    continue
                raise
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
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(_for_model(out), ensure_ascii=False)})
                    results.append(out)
                    yield "receipt", {"tool": c["name"], "args": args, "result": out}
                except Exception as e:
                    msgs.append({"role": "tool", "tool_call_id": c["id"], "content": f"error: {e}"})
    except groq.RateLimitError:
        yield "notice", "The AI is getting a lot of questions right now (rate limit). Try again in a few seconds."
    except groq.APIError as e:
        print("chat error:", type(e).__name__, getattr(e, "message", e))
        yield "notice", f"The AI service had a problem ({type(e).__name__}). Please try again."
    if answer:
        yield "grounding", grounding.check(answer, results, user_text)
    yield "done", None
