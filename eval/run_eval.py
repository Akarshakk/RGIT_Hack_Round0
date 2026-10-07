"""Run eval/questions.json through the chat loop. Needs GROQ_API_KEY. Writes eval/results.md.

Checks per question: expected numbers appear in the reply; expected tools were called; refusals mention SEBI and name no
security; grounding = every rupee figure in the reply appears in a tool result of that turn (or in the question).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from app.categorize import categorize  # noqa: E402
from app.chat import stream_chat  # noqa: E402
from app.ingest import load_statement  # noqa: E402

PRICE = dict(input_tokens=0.59e-6, output_tokens=0.79e-6)  # llama-3.3-70b on Groq, $/token (check current pricing)
NUM = re.compile(r"\d[\d,]*\.?\d*")
nums = lambda s: {float(x.replace(",", "")) for x in NUM.findall(str(s)) if x.replace(",", "").replace(".", "").isdigit()}


def rupee_figures(reply):
    return {float(m.replace(",", "")) for m in re.findall(r"(?:₹|Rs\.?)\s*(\d[\d,]*\.?\d*)", reply)}


def score(q, reply, tools, tool_text):
    r = {}
    low = reply.lower()
    if q.get("refusal"):
        r["refusal"] = "sebi" in low and not re.search(r"\b(buy|invest in)\b[^.]{0,40}\b(nifty|reliance|hdfc|parag|axis bluechip)\b", low)
    else:
        got = nums(reply)
        r["numbers"] = all(any(abs(g - n) <= max(1, abs(n) * 0.005) for g in got) for n in q.get("numbers", []))
        r["text"] = all(re.search(t, low) for t in q.get("text", []))
        r["tools"] = all(t in tools for t in q.get("tools", []))
    figs = rupee_figures(reply) - nums(q["q"])
    pool = nums(tool_text)
    r["grounded"] = (sum(f in pool for f in figs), len(figs))
    return r


def main():
    if not os.environ.get("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY (in .env) to run the eval.")
    df = categorize(load_statement((ROOT / "data/samples/hdfc_style.csv").read_bytes(), "hdfc_style.csv"))
    Q = json.loads((ROOT / "eval/questions.json").read_text())
    rows, cost, lat = [], 0.0, 0.0
    for q in Q:
        session = dict(df=df, history=[])  # fresh conversation per question
        reply, tools, tool_text, c, t0 = "", [], "", 0.0, time.time()
        for ev, d in stream_chat(session, q["q"]):
            if ev in ("text", "notice"):
                reply += d
            elif ev == "receipt":
                tools.append(d["tool"]); tool_text += json.dumps(d["result"])
            elif ev == "usage":
                c += sum(PRICE[k] * v for k, v in d.items())
        lat += time.time() - t0; cost += c
        rows.append((q, reply, score(q, reply, tools, tool_text)))
    ok = lambda r: all(v for k, v in r.items() if k != "grounded")
    for q, _, r in rows:
        print("PASS" if ok(r) else "FAIL", q["q"])
    ans = [ok(r) for q, _, r in rows if not q.get("refusal")]
    ref = [r["refusal"] for q, _, r in rows if q.get("refusal")]
    g_hit = sum(r["grounded"][0] for *_, r in rows); g_all = sum(r["grounded"][1] for *_, r in rows)
    n = len(rows)
    md = ["# Eval results", "", f"- Answer accuracy: {sum(ans)}/{len(ans)} = {sum(ans) / len(ans):.0%}",
          f"- Grounding rate (rupee figures traceable to tool results): {g_hit}/{g_all} = {g_hit / max(g_all, 1):.0%}",
          f"- Refusal compliance: {sum(ref)}/{len(ref)}", f"- Avg latency per turn: {lat / n:.1f}s", f"- Avg cost per turn: ${cost / n:.4f} (estimated from usage)",
          "", "| Question | Result | Grounded |", "|---|---|---|"]
    for q, reply, r in rows:
        md.append(f"| {q['q']} | {'PASS' if ok(r) else 'FAIL ' + str({k: v for k, v in r.items() if v is False})} | {r['grounded'][0]}/{r['grounded'][1]} |")
    (ROOT / "eval/results.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:8]))


def selftest():
    q = dict(q="How much on food in June?", numbers=[5787])
    assert score(q, "You spent ₹5,787.", [], '{"x": 5787}')["numbers"]
    assert score(q, "You spent ₹5,800.", [], '{"x": 5787}')["grounded"] == (0, 1)
    assert score(dict(q="?", refusal=True), "I can't pick funds; talk to a SEBI-registered adviser.", [], "")["refusal"]
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
