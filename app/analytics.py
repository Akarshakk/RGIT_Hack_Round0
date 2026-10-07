"""Deterministic analytics ("semantic layer"). Every function takes the categorized DataFrame and returns
small JSON-serializable dicts/lists with rounded rupees and row ids (df.index) as evidence.

Conventions: income = credits categorized Income. spend = all debits except Investments (cash and P2P count as
spend). saved = income - spend, so SIPs count as savings.
"""
import re

import pandas as pd

R = lambda x: int(round(float(x)))
SUB_USAGE_UNKNOWN = re.compile(r"gym|cult|fitness", re.I)  # usage can't be seen in a statement; ask the user


def _period(df, period):
    """None/'all' | 'last_month' | 'YYYY-MM'."""
    if period in (None, "all"):
        return df
    ym = df["date"].dt.strftime("%Y-%m")
    return df[ym == (ym.max() if period == "last_month" else period)]


def _spend(df):
    return df[(df.amount < 0) & (df.category != "Investments")]


def _months(df):
    return max(df["date"].dt.to_period("M").nunique(), 1)


def get_overview(df, period=None):
    d = _period(df, period)
    income, spend = d.amount[d.category == "Income"].sum(), -_spend(d).amount.sum()
    inv = -d.amount[d.category == "Investments"].sum()
    m = d.groupby(d["date"].dt.strftime("%Y-%m")).balance.last()
    return dict(period=period or "all", from_date=str(d.date.min().date()), to_date=str(d.date.max().date()),
                income=R(income), spend=R(spend), invested=R(inv), net_savings=R(income - spend),
                savings_rate_pct=round(float(100 * (income - spend) / income), 1) if income else None,
                balance_trend={k: R(v) for k, v in m.items()}, transactions=len(d))


def category_breakdown(df, period=None, bucket=None):
    d = _period(df, period)
    d = d[(d.amount < 0) & (d.bucket == bucket)] if bucket else _spend(d)
    g = d.groupby("category").amount.agg(["sum", "count"])
    tot = -g["sum"].sum()
    return [dict(category=c, amount=R(-r["sum"]), pct=round(100 * -r["sum"] / tot, 1), count=int(r["count"]))
            for c, r in g.sort_values("sum").iterrows()]


def top_merchants(df, period=None, category=None, n=10):
    d = _spend(_period(df, period))
    if category:
        d = d[d.category == category]
    g = d.groupby("merchant").amount.agg(["sum", "count"]).sort_values("sum").head(n)
    return [dict(merchant=m, total=R(-r["sum"]), count=int(r["count"])) for m, r in g.iterrows()]


def monthly_trend(df, category=None):
    d = _spend(df)
    if category:
        d = d[d.category == category]
    return {k: R(-v) for k, v in d.groupby(d["date"].dt.strftime("%Y-%m")).amount.sum().items()}


def search_transactions(df, query=None, category=None, min_amount=None, period=None, limit=20):
    d = _period(df, period)
    if query:
        d = d[d.narration.str.contains(query, case=False, regex=False) | d.merchant.str.contains(query, case=False, regex=False)]
    if category:
        d = d[d.category == category]
    if min_amount is not None:
        d = d[d.amount.abs() >= min_amount]
    return [dict(id=int(i), date=str(r.date.date()), merchant=r.merchant, category=r.category, amount=R(r.amount))
            for i, r in d.head(limit).iterrows()]


def find_recurring(df):
    """Same merchant, amounts within +-10% of the median, every gap 25-35 days, >=2 occurrences."""
    out = []
    for m, g in df[df.amount < 0].groupby("merchant"):
        if len(g) < 2:
            continue
        a = -g.amount
        gaps = g.date.diff().dt.days.dropna()
        if ((a - a.median()).abs() <= 0.1 * a.median()).all() and gaps.between(25, 35).all():
            cat = g.category.iloc[0]
            out.append(dict(merchant=m, category=cat, monthly_cost=R(a.median()), count=len(g), last_date=str(g.date.max().date()),
                            is_subscription=cat == "Subscriptions",
                            possibly_unused=cat == "Subscriptions" and bool(SUB_USAGE_UNKNOWN.search(m)),
                            ids=[int(i) for i in g.index]))
    return sorted(out, key=lambda x: -x["monthly_cost"])


def find_anomalies(df):
    """Debit > 3x its category median (categories with >=5 debits), or a one-off merchant over Rs 5,000."""
    recurring = {r["merchant"] for r in find_recurring(df)}
    d = df[(df.amount < 0) & ~df.category.isin(["Investments", "Rent", "EMI & Loans"]) & ~df.merchant.isin(recurring)]
    med = d.groupby("category").amount.transform(lambda s: (-s).median() if len(s) >= 5 else float("inf"))
    seen = d.groupby("merchant").amount.transform("size")
    hit = d[((-d.amount) > 3 * med) | (((-d.amount) > 5000) & (seen == 1))]
    return [dict(id=int(i), date=str(r.date.date()), merchant=r.merchant, category=r.category, amount=R(-r.amount))
            for i, r in hit.iterrows()]


def _ids(d, n=10):
    return [int(i) for i in d.index[:n]]


def generate_insights(df):
    n = _months(df)
    income = df.amount[df.category == "Income"].sum() / n
    sp = _spend(df)
    out = []

    def add(id, title, severity, evidence, saving=0):
        out.append(dict(id=id, title=title, severity=severity, evidence=evidence, monthly_saving_estimate=R(saving)))

    # 1. 50/30/20
    if income > 0:
        pct = {b: round(100 * -sp.amount[sp.bucket == b].sum() / n / income, 1) for b in ("Need", "Want", "Transfer")}
        wants = pct["Want"] + pct["Transfer"]
        saved = round(100 * (income - -sp.amount.sum() / n) / income, 1)
        over = max(0, (wants - 30) / 100 * income)
        add("rule_50_30_20", f"Needs {pct['Need']}% / wants {wants}% / saved {saved}% of income (target 50/30/20)",
            "high" if over > 0.1 * income else "medium" if over else "low",
            dict(needs_pct=pct["Need"], wants_pct=wants, saved_pct=saved), over)

    # 2. subscription audit
    subs = [r for r in find_recurring(df) if r["is_subscription"]]
    if subs:
        unused = [s for s in subs if s["possibly_unused"]]
        add("subscription_audit", f"{len(subs)} subscriptions cost ₹{sum(s['monthly_cost'] for s in subs):,}/month"
            + (f"; check if you use {', '.join(s['merchant'] for s in unused)} (₹{sum(s['monthly_cost'] for s in unused):,}/month)" if unused else ""),
            "high" if unused else "low",
            dict(subscriptions=[{k: s[k] for k in ("merchant", "monthly_cost", "possibly_unused", "ids")} for s in subs]),
            sum(s["monthly_cost"] for s in unused))

    # 3. small-spend leak: many food orders under ₹600
    small = sp[(sp.category == "Food & Dining") & (sp.amount > -600)]
    if len(small) >= 4:
        add("small_spend_leak", f"{len(small)} small food orders (under ₹600) add up to ₹{R(-small.amount.sum() / n):,}/month",
            "medium", dict(orders=len(small), total=R(-small.amount.sum()), ids=_ids(small)), 0.25 * -small.amount.sum() / n)

    # 4. category spike: latest month vs average of earlier months
    ym = sp.date.dt.strftime("%Y-%m")
    if ym.nunique() >= 2:
        last = ym.max()
        piv = sp.groupby([sp.category, ym == last]).amount.sum().unstack(fill_value=0) * -1
        if True in piv.columns and False in piv.columns:
            prev = piv[False] / (ym.nunique() - 1)
            diff = (piv[True] - prev)
            c = diff.idxmax()
            if diff[c] > 1000 and piv[True][c] > 1.3 * prev[c]:
                add("category_spike", f"{c} spend in {last} was ₹{R(piv[True][c]):,}, up ₹{R(diff[c]):,} from the earlier monthly average",
                    "medium", dict(category=c, month=last, amount=R(piv[True][c]), usual=R(prev[c])), diff[c])

    # 5. weekend effect (food)
    food = sp[sp.category == "Food & Dining"]
    if len(food) >= 6:
        wk = food[food.date.dt.weekday >= 5]
        share = wk.amount.sum() / food.amount.sum()
        if share > 0.6:
            add("weekend_effect", f"{R(share * 100)}% of food spend happens on weekends (₹{R(-wk.amount.sum() / n):,}/month)",
                "medium", dict(weekend_share_pct=R(share * 100), ids=_ids(wk)), 0.3 * -wk.amount.sum() / n)

    # 6. fees
    fees = sp[sp.category == "Fees & Charges"]
    if len(fees):
        add("avoidable_fees", f"₹{R(-fees.amount.sum()):,} paid in fees/penalties", "high" if len(fees) > 1 else "medium",
            dict(total=R(-fees.amount.sum()), ids=_ids(fees)), -fees.amount.sum() / n)

    # 7. emergency runway
    need = -sp.amount[sp.bucket == "Need"].sum() / n
    bal = df.balance.dropna().iloc[-1] if df.balance.notna().any() else None
    if bal is not None and need > 0:
        months = round(bal / need, 1)
        add("emergency_runway", f"Balance covers {months} months of essentials (aim for 6)",
            "high" if months < 3 else "medium" if months < 6 else "low", dict(balance=R(bal), monthly_needs=R(need), months=months))

    # 8. anomalies
    an = find_anomalies(df)
    if an:
        add("anomaly", f"Unusual spend: ₹{an[0]['amount']:,} at {an[0]['merchant']} on {an[0]['date']}", "medium",
            dict(transactions=an[:5], ids=[a["id"] for a in an[:5]]))

    return sorted(out, key=lambda x: -x["monthly_saving_estimate"])


def simulate_savings(df, changes, months=12):
    """changes: [{category|merchant, cut_pct}] -> monthly/annual saving and the new savings rate."""
    n, sp = _months(df), _spend(df)
    income = df.amount[df.category == "Income"].sum() / n
    rows, total = [], 0.0
    for c in changes:
        d = sp[sp.category == c["category"]] if c.get("category") else sp[sp.merchant == c.get("merchant")]
        monthly = -d.amount.sum() / n
        save = monthly * c["cut_pct"] / 100
        total += save
        rows.append(dict(target=c.get("category") or c.get("merchant"), cut_pct=c["cut_pct"], current_monthly=R(monthly), monthly_saving=R(save)))
    base = income - -sp.amount.sum() / n
    return dict(changes=rows, monthly_saving=R(total), saving_over_period=R(total * months), months=months,
                savings_rate_pct_before=round(float(100 * base / income), 1) if income else None,
                savings_rate_pct_after=round(float(100 * (base + total) / income), 1) if income else None)


def plan_goal(df, target, months):
    """Monthly saving needed for a goal vs the current surplus, and which tips would close the gap."""
    n = _months(df)
    surplus = (df.amount[df.category == "Income"].sum() + _spend(df).amount.sum()) / n
    need = target / months
    gap = max(0.0, need - surplus)
    picks, covered = [], 0.0
    for i in generate_insights(df):
        if gap - covered <= 0:
            break
        if i["monthly_saving_estimate"] > 0 and i["id"] != "rule_50_30_20":  # the 50/30/20 estimate overlaps the others
            picks.append(dict(id=i["id"], title=i["title"], monthly_saving_estimate=i["monthly_saving_estimate"]))
            covered += i["monthly_saving_estimate"]
    return dict(target=R(target), months=months, monthly_needed=R(need), current_monthly_surplus=R(surplus), gap=R(gap),
                on_track=bool(gap == 0), tips_to_close_gap=picks, gap_after_tips=R(max(0.0, gap - covered)))


def quick_wins(df, target_monthly=None):
    """Non-overlapping saving actions (weekend food OR small orders, unused subscription, fees, a spike) with ₹/month.
    With a target, also says how far the wins get you, so nobody has to add them up by hand."""
    ins = {i["id"]: i for i in generate_insights(df)}
    wins = []
    if "weekend_effect" in ins:
        wins.append(("Cut weekend food orders by 30%", ins["weekend_effect"]["monthly_saving_estimate"]))
    elif "small_spend_leak" in ins:
        wins.append(("Skip one in four small food orders", ins["small_spend_leak"]["monthly_saving_estimate"]))
    unused = [s for s in find_recurring(df) if s["possibly_unused"]]
    if unused:
        wins.append((f"Drop {unused[0]['merchant'].title()} if you've stopped going", unused[0]["monthly_cost"]))
    if "avoidable_fees" in ins:
        wins.append(("Pay bills on time, no late fees", ins["avoidable_fees"]["monthly_saving_estimate"]))
    if "category_spike" in ins and len(wins) < 3:
        wins.append((f"Bring {ins['category_spike']['evidence']['category']} back to normal", ins["category_spike"]["monthly_saving_estimate"]))
    wins = [dict(action=t, monthly_saving=R(v)) for t, v in wins if v > 0]
    out = dict(wins=wins, monthly_total=sum(w["monthly_saving"] for w in wins))
    if target_monthly:
        out.update(target_monthly=R(target_monthly), meets_target=out["monthly_total"] >= target_monthly,
                   shortfall=R(max(0, target_monthly - out["monthly_total"])),
                   biggest_categories_to_trim=[c["category"] for c in category_breakdown(df, bucket="Want")[:3]])
    return out


def future_you(df, monthly=None, years=10, rate_pct=10.0):
    """What a monthly saving grows to, compounded monthly at an ILLUSTRATIVE annual rate (not a product or a promise).
    monthly defaults to the quick-wins total."""
    monthly = float(quick_wins(df)["monthly_total"] if monthly is None else monthly)
    years, r = max(1, min(int(years), 40)), float(rate_pct) / 100 / 12
    bal, series = 0.0, []
    for m in range(1, years * 12 + 1):
        bal = bal * (1 + r) + monthly
        if m % 12 == 0:
            series.append(dict(year=m // 12, value=R(bal), contributed=R(monthly * m)))
    end_year = int(df.date.max().year) + years
    return dict(monthly=R(monthly), years=years, illustrative_rate_pct=rate_pct, final_value=R(bal), contributed=R(monthly * years * 12),
                growth=R(bal - monthly * years * 12), by_year=end_year, series=series,
                note="Illustrative compounding only. Not a forecast or an investment recommendation.")


def friend_ledger(df):
    """Money sent to and received from people (UPI P2P / IMPS transfers), per person."""
    p = df[df.counterparty.notna() & (df.category != "Income") & (df.category != "Rent")]
    if not len(p):
        return dict(people=[], sent=0, received=0)
    g = p.groupby("merchant").amount.agg(sent=lambda s: -s[s < 0].sum(), received=lambda s: s[s > 0].sum(), payments="size")
    people = [dict(name=m, sent=R(r.sent), received=R(r.received), payments=int(r.payments), net=R(r.received - r.sent))
              for m, r in g.sort_values("sent", ascending=False).iterrows()]
    return dict(people=people, sent=R(g.sent.sum()), received=R(g.received.sum()))
