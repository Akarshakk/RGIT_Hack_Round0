"""Credence Wrapped: a story of the statement built from the analytics layer.

Every number on a card comes from pandas. The LLM only rewrites the one-line roast/hype quip, and a quip is
rejected (template kept) if it contains a number that is not already on its card.
"""
import json
import os
import re

from app import analytics as an

R = an.R
HOURS_PER_MONTH = 176  # 22 working days x 8 hours
SKIP = {"Rent", "EMI & Loans", "Transfers", "Cash Withdrawal", "Income", "Investments", "Utilities & Bills", "Fees & Charges"}
inr = lambda n: "₹" + _group(R(n))
pl = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"


def _group(n):
    """Indian digit grouping: 1234567 -> 12,34,567."""
    s, neg = str(abs(int(n))), n < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return ("-" if neg else "") + s


def _period_label(df):
    a, b = df.date.min(), df.date.max()
    return f"{a:%b} – {b:%b %Y}" if a.year == b.year else f"{a:%b %Y} – {b:%b %Y}"


def _card(id, eyebrow, big, sub, quip, receipt=None, viz=None, theme="ink", facts=None):
    return dict(id=id, eyebrow=eyebrow, big=big, sub=sub, quip=quip, receipt=receipt, viz=viz, theme=theme, facts=facts or {})


def build(df):
    n = an._months(df)
    sp = an._spend(df)
    ov = an.get_overview(df)
    income_m = ov["income"] / n if ov["income"] else 0
    hourly = income_m / HOURS_PER_MONTH if income_m else 0
    insights = {i["id"]: i for i in an.generate_insights(df)}
    cards = []

    # 0. intro
    cards.append(_card("intro", f"Credence Wrapped · {_period_label(df)}", "Paisa kahan gaya?",
                       f"{n} months, {int((df.amount < 0).sum())} payments and one statement. Here's where your {inr(ov['spend'])} went.",
                       {"roast": "We read every line. Some of them were embarrassing.",
                        "hype": "Let's see what you did well and where you can win more."}, theme="ink"))

    # 1. big picture
    if ov["income"]:
        cards.append(_card("picture", "The big picture", f"{inr(ov['income'])} in.\n{inr(ov['spend'])} out.",
                           f"You kept {inr(ov['net_savings'])}" + (f", and put {inr(ov['invested'])} into investments." if ov["invested"] else "."),
                           {"roast": f"You saved {ov['savings_rate_pct']}%. The target is 20%. " + ("So close, yet so you." if ov["savings_rate_pct"] < 20 else "Fine. You win this one."),
                            "hype": f"You saved {ov['savings_rate_pct']}% of what came in. That's a habit forming."},
                           receipt=f"{int((df.category == 'Income').sum())} income credits · {int((df.amount < 0).sum())} debits",
                           viz={"type": "flow", "income": ov["income"], "spend": ov["spend"], "saved": ov["net_savings"]},
                           theme="turmeric", facts={"rate": ov["savings_rate_pct"]}))

    # 2. top app (most frequent discretionary merchant)
    disc = sp[~sp.category.isin(SKIP) & sp.counterparty.isna()]
    if len(disc):
        g = disc.groupby("merchant").amount.agg(["size", "sum"]).sort_values(["size", "sum"], ascending=[False, True])
        top, cnt, amt = g.index[0], int(g.iloc[0]["size"]), -g.iloc[0]["sum"]
        cat = disc[disc.merchant == top].category.iloc[0]
        second = (g.index[1], int(g.iloc[1]["size"])) if len(g) > 1 else None
        same = [(m, int(r["size"])) for m, r in g.iterrows() if disc[disc.merchant == m].category.iloc[0] == cat][:2]
        tiles = [{"label": m, "count": c} for m, c in (same if len(same) == 2 else [(top, cnt)])]
        vpa = disc[disc.merchant == top].narration.iloc[0]
        cards.append(_card("top", "Your top app", top.title(),
                           f"{pl(cnt, 'payment')} and {inr(amt)}." + (f" {second[0].title()} came second with {second[1]}." if second else ""),
                           {"roast": f"{cnt} times in {n} months. At this point {top.title()} should be paying you rent.",
                            "hype": "You know exactly what you like. Make it a treat instead of a routine."},
                           receipt=f"{_mask(vpa)} · {cnt} rows", viz={"type": "tiles", "items": tiles}, theme="chili",
                           facts={"count": cnt, "months": n}))

    # 3. hours of work on food delivery / dining
    food = sp[sp.category == "Food & Dining"]
    if hourly and len(food):
        fm = food.groupby("merchant").amount.sum().sort_values().head(2)
        amt = -fm.sum()
        hours = amt / hourly
        days = round(hours / 8, 1)
        names = " and ".join(m.title() for m in fm.index)
        cards.append(_card("hours", "In hours of your life", f"{R(hours)} hours",
                           f"{names} cost you {inr(amt)}. At {inr(hourly)} an hour of work" + (f", that's {days} working days." if days >= 1 else "."),
                           {"roast": (f"You worked {days} days so you'd never have to cook." if days >= 1
                                      else f"You worked {pl(R(hours), 'hour')} so you'd never have to cook."),
                            "hype": f"Win back half of that and you've earned {R(hours / 2)} hours of your life back."},
                           receipt=f"{inr(income_m)}/month income ÷ {HOURS_PER_MONTH} working hours · {int(food.merchant.isin(fm.index).sum())} rows",
                           viz={"type": "days", "days": days}, theme="sky", facts={"days": days, "half": R(hours / 2)}))

    # 4. personality
    cards.append(_personality(df, sp, insights, n))

    # 5. peak month
    trend = an.monthly_trend(df)
    if len(trend) >= 2:
        peak = max(trend, key=trend.get)
        others = [v for k, v in trend.items() if k != peak]
        pm = sp[sp.date.dt.strftime("%Y-%m") == peak]
        big_tx = pm.loc[pm.amount.idxmin()]
        fee = pm[pm.category == "Fees & Charges"]
        label = f"{big_tx.date:%B}"
        sub = f"You spent {inr(trend[peak])}. The biggest hit: {inr(-big_tx.amount)} at {big_tx.merchant.title()} on the {_ord(big_tx.date.day)}"
        sub += f", then a {inr(-fee.amount.sum())} fee." if len(fee) else "."
        ceiling = _ceiling(max(others))
        cards.append(_card("peak", "Plot twist", f"{label}.", sub,
                           {"roast": f"A {inr(-big_tx.amount)} {big_tx.category.lower()} moment" + (", then a fee. Iconic sequel." if len(fee) else ". Main character energy."),
                            "hype": f"One big month. Every other month, you stayed under {inr(ceiling)}."},
                           receipt=f"{_mask(big_tx.narration)}" + (f" · {fee.narration.iloc[0][:40]}" if len(fee) else ""),
                           viz={"type": "months", "months": [{"m": f"{_m(k)}", "v": v, "hot": k == peak} for k, v in trend.items()]},
                           theme="cream", facts={"ceiling": ceiling}))

    # 6. subscriptions
    subs = [r for r in an.find_recurring(df) if r["is_subscription"]]
    if subs:
        flag = next((s for s in subs if s["possibly_unused"]), None) or subs[0]
        tot = sum(s["monthly_cost"] for s in subs)
        cards.append(_card("subs", "The ghost subscription" if flag["possibly_unused"] else "Your subscriptions",
                           inr(flag["monthly_cost"] * flag["count"]),
                           f"paid to {flag['merchant'].title()} so far." + (f" Your {len(subs)} subscriptions cost {inr(tot)} a month." if len(subs) > 1 else ""),
                           {"roast": f"Is your {flag['merchant'].title()} membership working out more than you are?" if flag["possibly_unused"]
                                     else f"{len(subs)} subscriptions. You'd need a second life to use them all." if len(subs) >= 3
                                     else f"Just {pl(len(subs), 'subscription')}. Restraint. We're almost disappointed.",
                            "hype": f"If you still use {flag['merchant'].title()}, keep it. If not, that's {inr(flag['monthly_cost'])} back every month."},
                           receipt=f"{_mask(df.loc[flag['ids'][0], 'narration'])} · every ~30 days",
                           viz={"type": "subs", "items": [{"m": s["merchant"], "v": s["monthly_cost"], "flag": s is flag} for s in subs], "total": tot},
                           theme="indigo"))

    # 7. friend ledger (P2P)
    p2p_out = df[(df.amount < 0) & df.counterparty.notna() & (df.category == "Transfers")]
    if len(p2p_out) >= 2:
        p2p_in = df[(df.amount > 0) & df.counterparty.notna() & (df.category != "Income")]
        g = p2p_out.groupby("merchant").amount.agg(["size", "sum"]).sort_values("sum").head(3)
        sent, back = -p2p_out.amount.sum(), p2p_in.amount.sum()
        cards.append(_card("friends", "The friend ledger", inr(sent), f"sent to friends over UPI in {pl(len(p2p_out), 'payment')}.",
                           {"roast": f"{inr(sent)} out, {inr(back)} back. Are you splitting bills or sponsoring them?" if back < sent * 0.2
                                     else "You and your friends actually pay each other back. Suspiciously healthy.",
                            "hype": "Generous friend energy. If any of these were IOUs, a quick reminder could bring some back."},
                           receipt=f"{_mask(p2p_out.narration.iloc[0])} · {len(p2p_out)} P2P rows, {len(p2p_in)} P2P credits",
                           viz={"type": "friends", "items": [{"m": m, "n": int(r["size"]), "v": R(-r["sum"])} for m, r in g.iterrows()], "back": R(back)},
                           theme="saffron"))

    # 8. outro: non-overlapping wins
    qw = an.quick_wins(df)
    wins, total = [(w["action"], w["monthly_saving"]) for w in qw["wins"]], qw["monthly_total"]
    cards.append(_card("outro", "Here's what you can win back", inr(total), f"a month, from {pl(len(wins), 'small habit')}.",
                       {"roast": "Small changes. Your future self is begging.",
                        "hype": "No big sacrifices. Just a few habits, and you keep everything you love."},
                       viz={"type": "wins", "items": [{"t": t, "v": v} for t, v in wins], "year": total * 12,
                            "hours": R(total / hourly) if hourly else None}, theme="ink"))

    # 9. future you: the same monthly amount, compounded at an illustrative rate
    if total:
        fy = an.future_you(df, total, years=10)
        cards.append(_card("future", f"Future you · {fy['by_year']}", inr(fy["final_value"]),
                           f"If those {inr(total)} a month went into savings for 10 years, at an illustrative {fy['illustrative_rate_pct']:g}% a year.",
                           {"roast": "Future you is watching. Future you wants the Zomato money.",
                            "hype": "That's future you's head start, built from habits, not sacrifice."},
                           receipt="illustrative rate, not a forecast or investment advice",
                           viz={"type": "future", "series": fy["series"], "contributed": fy["contributed"], "growth": fy["growth"]},
                           theme="mint"))

    return dict(period=_period_label(df), hourly=R(hourly), cards=cards)


def _personality(df, sp, insights, n):
    food, wants = sp[sp.category == "Food & Dining"], sp[sp.bucket == "Want"]
    wk = food[food.date.dt.weekday >= 5]
    share = R(100 * wk.amount.sum() / food.amount.sum()) if len(food) else 0
    by_cat = (-wants.groupby("category").amount.sum()).sort_values(ascending=False)
    if share >= 60 and len(food) >= 6:
        name, line, viz = "The Weekend Foodie", f"{share}% of your food spend lands on Saturday and Sunday.", {"type": "split", "weekday": 100 - share, "weekend": share}
        days = wk.groupby(wk.date.dt.date).size()
        d, c = days.idxmax(), int(days.max())
        quip = {"roast": f"Monday you: “I'll cook this week.” {d:%A} {d.day} {d:%b} you: {c} food orders." if c >= 2
                         else "Monday you: “I'll cook this week.” Saturday you: “Order kar dete hain.”",
                "hype": f"Weekdays, you're disciplined. Bring that to one weekend day and save about {inr(insights['weekend_effect']['monthly_saving_estimate'])} a month."
                if "weekend_effect" in insights else "Weekdays, you're disciplined. Bring that energy to the weekend."}
        rc = f"{len(food)} Food & Dining rows · grouped by weekday"
    elif len(by_cat) and by_cat.index[0] == "Shopping":
        name, line, viz = "The Cart Champion", f"Shopping is your biggest want at {inr(by_cat.iloc[0])}.", {"type": "bars", "items": [{"m": k, "v": R(v)} for k, v in by_cat.head(4).items()]}
        quip = {"roast": "Add to cart is your cardio.", "hype": "You buy things you value. A 48-hour wait rule keeps it that way."}
        rc = f"{int((sp.category == 'Shopping').sum())} Shopping rows"
    elif len(by_cat) and by_cat.index[0] == "Subscriptions":
        name, line, viz = "The Subscription Collector", f"Subscriptions are your biggest want at {inr(by_cat.iloc[0])}.", {"type": "bars", "items": [{"m": k, "v": R(v)} for k, v in by_cat.head(4).items()]}
        quip = {"roast": "You don't watch shows. You collect apps.", "hype": "One audit and you could keep the two you love."}
        rc = f"{int((sp.category == 'Subscriptions').sum())} Subscriptions rows"
    else:
        name, line, viz = "The Steady Planner", "No single habit dominates your spending.", {"type": "bars", "items": [{"m": k, "v": R(v)} for k, v in by_cat.head(4).items()]}
        quip = {"roast": "Honestly? Boring. Financially, that's a compliment.", "hype": "Balanced spending is rare. Now point the surplus at a goal."}
        rc = f"{len(wants)} Want rows"
    return _card("persona", "Your money personality", name, line, quip, receipt=rc, viz=viz, theme="rani")


def _mask(narr):
    """Shorten long reference numbers so the receipt reads like a statement line but leaks nothing."""
    return re.sub(r"\d{6,}", "…", str(narr))[:60]


def _ord(d):
    return f"{d}{'th' if 11 <= d % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')}"


def _m(ym):
    import calendar
    return calendar.month_abbr[int(ym[5:])].upper()


def _ceiling(v):
    step = 10000 if v >= 20000 else 5000 if v >= 5000 else 1000
    return int(-(-v // step) * step)


# ---------- optional LLM rewrite of the quips ----------
QUIP_SYSTEM = """You write one-line captions for a Spotify-Wrapped-style story about someone's bank statement, for young Indians.
For each card you get its facts. Write two captions per card:
- "roast": witty and teasing, like a friend roasting you. About money habits only (never looks, body, gender, caste, religion).
- "hype": warm and encouraging, still specific to the card.
Rules:
- Max 14 words each. Light Hinglish is welcome (yaar, bas, kya scene hai).
- Don't restate the card's facts; the card already shows them. Add the joke or the encouragement.
- Prefer no numbers. If you use one, copy it exactly from that card's facts.
- Stay true to the facts: never say they overspent, earned less, or did something the facts don't show.
- Never recommend specific stocks, funds or investment products.
Return JSON: {"cards": {"<card id>": {"roast": "...", "hype": "..."}}}"""

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*(?:k|K|L|lakh|lac|cr|crore)\b)?")


def _nums(s):
    """Numbers as written; shorthand like '3k' or '1.2 lakh' stays distinct so it can't pass as an exact figure."""
    return {re.sub(r"[,\s]", "", x) for x in _NUM.findall(s)}


def ai_quips(story, client=None):
    """Returns {card_id: {roast, hype}} for quips that passed the number check. Empty dict if no key or on error."""
    if client is None:
        if not os.environ.get("GROQ_API_KEY"):
            return {}
        import groq
        client = groq.Groq()
    payload = {c["id"]: {"headline": c["big"], "detail": c["sub"], "eyebrow": c["eyebrow"]} for c in story["cards"]}
    out = None
    for model in dict.fromkeys([os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"), os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")]):
        try:
            r = client.chat.completions.create(
                model=model, temperature=0.9, max_tokens=6000, reasoning_effort="low", response_format={"type": "json_object"},
                messages=[{"role": "system", "content": QUIP_SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
            out = json.loads(r.choices[0].message.content).get("cards", {})
            break
        except Exception as e:  # never break the story because of the model: try the fallback model, then keep templates
            print("wrapped quips:", model, type(e).__name__, str(e)[:160])
    if not out:
        return {}
    good = {}
    for c in story["cards"]:
        q = out.get(c["id"]) or {}
        allowed = _nums(" ".join([c["big"], c["sub"], c["eyebrow"], c["quip"]["roast"], c["quip"]["hype"]]))
        keep = {m: q[m].strip() for m in ("roast", "hype")
                if isinstance(q.get(m), str) and 0 < len(q[m]) <= 160 and _nums(q[m]) <= allowed}
        if keep:
            good[c["id"]] = keep
    return good
