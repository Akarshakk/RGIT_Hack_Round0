"""Self-checks. Run: python tests/test_core.py  (also pytest-compatible)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
from types import SimpleNamespace

from app import analytics as an  # noqa: E402
from app.chat import TOOLS, redact, stream_chat  # noqa: E402
from app.categorize import categorize, parse_narration, recategorize  # noqa: E402
from app.ingest import NeedsMapping, load_statement  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
TRUTH = json.loads((SAMPLES / "ground_truth.json").read_text())


def _load(name, **kw):
    return load_statement((SAMPLES / name).read_bytes(), name, **kw)


def test_ingest_all_layouts_match_ground_truth():
    for name, kw in [("hdfc_style.csv", {}), ("sbi_style.csv", {}), ("statement.pdf", {"password": TRUTH["password"]})]:
        df = _load(name, **kw)
        assert len(df) == TRUTH["row_count"], (name, len(df))
        assert round(-df.amount[df.amount < 0].sum(), 2) == TRUTH["total_debit"], name
        assert round(df.amount[df.amount > 0].sum(), 2) == TRUTH["total_credit"], name
        assert df.balance.iloc[-1] == TRUTH["closing_balance"], name


def test_pdf_wrong_password():
    for pw in (None, "nope"):
        try:
            _load("statement.pdf", password=pw)
        except ValueError as e:
            assert "password" in str(e)
        else:
            raise AssertionError("expected password error")


def test_needs_mapping_then_mapped():
    raw = b"When,What,How much\n01/06/2026,Coffee,-120\n02/06/2026,Salary,50000\n"
    try:
        load_statement(raw, "odd.csv")
    except NeedsMapping as e:
        assert e.columns == ["When", "What", "How much"]
    else:
        raise AssertionError("expected NeedsMapping")
    df = load_statement(raw, "odd.csv", mapping={"date": "When", "narration": "What", "amount": "How much"})
    assert list(df.amount) == [-120, 50000]


def _accuracy(use_llm):
    hits = n = 0
    for name in ("hdfc_style.csv", "sbi_style.csv"):
        df = categorize(_load(name), use_llm=use_llm)
        hits += sum(a == t["category"] for a, t in zip(df.category, TRUTH["rows"]))
        n += len(df)
    return hits / n


def test_categorize_accuracy():
    rule = _accuracy(False)
    print(f"  rule-only accuracy {rule:.1%} (synthetic data shares vocabulary with merchants.json: optimistic)")
    assert rule >= 0.85
    if os.environ.get("GROQ_API_KEY"):
        hybrid = _accuracy(True)
        print(f"  rule+LLM accuracy {hybrid:.1%}")
        assert hybrid >= 0.95
    else:
        print("  rule+LLM accuracy: skipped (no GROQ_API_KEY)")


def test_unseen_merchant_and_override():
    df = _load("hdfc_style.csv").head(3).copy()
    df.loc[1, "narration"] = "UPI/P2M/111111111111/chaikingbandra@ybl/Tea"
    df = categorize(df, use_llm=False)
    assert df.category[1] == "Other" and df.cat_source[1] == "rule"
    ov = {}
    recategorize(df, ov, "chaikingbandra", "Food & Dining")
    assert df.category[1] == "Food & Dining" and df.cat_source[1] == "user"
    assert categorize(df, ov, use_llm=False).category[1] == "Food & Dining"


def test_parse_narration_separators():
    for s in ("UPI/P2A/123456789012/rahul.sharma@okicici/Split", "UPI-P2A-123456789012-rahul.sharma@okicici-Split"):
        p = parse_narration(s)
        assert p["rail"] == "UPI" and p["p2p"] and p["counterparty"] == "Rahul Sharma"


def _df():
    return categorize(_load("hdfc_style.csv"), use_llm=False)


def test_analytics_matches_ground_truth():
    df = _df()
    assert an.monthly_trend(df, "Food & Dining") == {k: round(v) for k, v in TRUTH["food_by_month"].items()}
    subs = {r["merchant"]: r for r in an.find_recurring(df) if r["is_subscription"]}
    assert set(subs) == {"netflix", "spotify", "hotstar", "cultfit"}
    assert [m for m, r in subs.items() if r["possibly_unused"]] == ["cultfit"]
    anomalies = an.find_anomalies(df)
    assert [a["id"] for a in anomalies] == [TRUTH["anomaly"]["id"]] and anomalies[0]["amount"] == 18999
    ins = {i["id"]: i for i in an.generate_insights(df)}
    assert ins["avoidable_fees"]["evidence"]["ids"] == [TRUTH["late_fee"]["id"]] and ins["avoidable_fees"]["evidence"]["total"] == 590
    assert ins["subscription_audit"]["monthly_saving_estimate"] == 1499
    assert len(ins) == 8 or len(ins) >= 7


def test_simulate_savings():
    r = an.simulate_savings(_df(), [{"category": "Food & Dining", "cut_pct": 50}])
    assert r["monthly_saving"] > 0 and r["savings_rate_pct_after"] > r["savings_rate_pct_before"]
    assert r["saving_over_period"] == r["monthly_saving"] * 12 or abs(r["saving_over_period"] - r["monthly_saving"] * 12) <= 12


def test_redaction_masks_people_and_numbers():
    df = redact(_df())
    blob = " ".join(df.narration) + " ".join(df.merchant)
    for leak in ("rahul", "sharma", "ramesh", "okicici", "429401965569"):
        assert leak not in blob.lower(), leak
    assert "Person#1" in blob


def _chunk(content=None, tool=None, finish=None):
    tc = [SimpleNamespace(index=0, id=tool[0], function=SimpleNamespace(name=tool[1], arguments=tool[2]))] if tool else None
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, delta=SimpleNamespace(content=content, tool_calls=tc))])


class _Fake:
    """Scripted stand-in for the Groq client: one tool-call turn (args split across chunks), then a text turn."""

    def __init__(self):
        self.turns = [
            [_chunk(tool=("c1", "generate_insights", "")), _chunk(tool=(None, "", "{}"), finish="tool_calls")],
            [_chunk("Cut "), _chunk("the gym."), _chunk(finish="stop")],
        ]
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        assert kw["tools"] == TOOLS and kw["stream"]
        return iter(self.turns.pop(0))


def test_chat_loop_runs_tools_and_streams():
    session = {"df": _df(), "history": []}
    events = list(stream_chat(session, "How can I save?", client=_Fake()))
    kinds = [e for e, _ in events]
    assert kinds == ["receipt", "text", "text", "grounding", "done"], kinds
    assert events[3][1] == {"verified": 0, "total": 0, "unverified": []}
    assert events[0][1]["tool"] == "generate_insights" and events[0][1]["result"]
    h = session["history"]
    assert [m["role"] for m in h] == ["user", "assistant", "tool", "assistant"]
    assert h[1]["tool_calls"][0]["function"]["name"] == "generate_insights" and h[2]["tool_call_id"] == "c1"


def test_plan_goal():
    g = an.plan_goal(_df(), 60000, 6)
    assert g["monthly_needed"] == 10000 and g["current_monthly_surplus"] == round(TRUTH["total_credit"] / 4 - (TRUTH["total_debit"] - 20000) / 4)
    assert (g["gap"] == 0) == g["on_track"] and g["gap_after_tips"] <= g["gap"]


def test_all_tool_outputs_json_serializable():
    from app.chat import run_tool
    df = redact(_df())
    args = dict(period=None, bucket=None, category=None, n=5, query=None, min_amount=None, limit=5, changes=[
        {"category": "Food & Dining", "merchant": None, "cut_pct": 10}], months=12, target=90000, monthly=None, years=10, rate_pct=None, target_monthly=5000)
    for t in TOOLS:
        json.dumps(run_tool(df, t["function"]["name"], {k: args[k] for k in t["function"]["parameters"]["properties"]}))


def test_wrapped_story_matches_ground_truth():
    from app import wrapped as wr
    st = wr.build(_df())
    cards = {c["id"]: c for c in st["cards"]}
    assert list(cards) == ["intro", "picture", "top", "hours", "persona", "peak", "subs", "friends", "outro", "future"]
    assert cards["future"]["big"] == "₹6,95,244"  # 3,394/month for 10 years at an illustrative 10%
    assert cards["top"]["big"] == "Zomato" and "33 payments" in cards["top"]["sub"]
    assert cards["persona"]["big"] == "The Weekend Foodie"
    assert cards["peak"]["big"] == "August." and "₹18,999" in cards["peak"]["sub"]
    assert cards["subs"]["big"] == "₹5,996"  # cultfit 1,499 x 4
    assert cards["friends"]["big"] == "₹9,507" == "₹{:,}".format(TRUTH["spend_by_category"]["Transfers"])
    assert cards["outro"]["big"] == "₹3,394" and cards["outro"]["viz"]["year"] == 3394 * 12
    json.dumps(st)


def test_wrapped_ai_quips_reject_invented_numbers():
    from app import wrapped as wr
    st = wr.build(_df())
    reply = {"cards": {"top": {"roast": "33 orders. Zomato knows your gate code.", "hype": "You saved ₹99,999 on Zomato!"},
                       "intro": {"roast": "Chalo, dekhte hain.", "hype": "Let's go."}}}
    msg = SimpleNamespace(content=json.dumps(reply))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)]))))
    got = wr.ai_quips(st, client=client)
    assert got["top"] == {"roast": "33 orders. Zomato knows your gate code."}  # ₹99,999 is not on the card -> dropped
    assert got["intro"] == {"roast": "Chalo, dekhte hain.", "hype": "Let's go."}


def test_icici_style_headers():
    csv_text = ("ICICI Bank Limited\nS No.,Value Date,Transaction Date,Cheque Number,Transaction Remarks,Withdrawal Amount (INR ),Deposit Amount (INR ),Balance (INR )\n"
                '1,01/08/2026,01/08/2026,,NEFT-INFOSYS LTD-SALARY AUG,,"82,000.00","1,02,000.00"\n'
                '2,02/08/2026,02/08/2026,,UPI-zomato@icici-ZOMATO-Order,"420.00",,"1,01,580.00"\n')
    df = load_statement(csv_text.encode(), "icici.csv")
    assert list(df.amount) == [82000.0, -420.0] and df.balance.iloc[-1] == 101580.0


def test_grounding_flags_invented_numbers():
    from app.grounding import check
    r = check("Rent is ₹18,000 (37%). Together that's roughly 64%, so save ₹5,000.", [{"amount": 18000, "pct": 37.2}], "How do I save ₹5,000?")
    assert r == {"verified": 3, "total": 4, "unverified": ["64%"]}


def test_future_you_and_friend_ledger():
    df = _df()
    f = an.future_you(df, 1000, years=1, rate_pct=0)
    assert f["final_value"] == f["contributed"] == 12000 and f["by_year"] == 2027
    fl = an.friend_ledger(df)
    assert fl["sent"] == TRUTH["spend_by_category"]["Transfers"] and fl["received"] == 0 and fl["people"][0]["name"] == "priya.n"
    assert an.quick_wins(df)["monthly_total"] == 3394


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
