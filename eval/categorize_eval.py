"""How well does the categorizer handle merchants that are NOT in merchants.json?

40 real Indian merchants absent from the dictionary, as UPI narrations with a neutral note ("Payment") so the note gives
no hint. Rules alone can only say Other; the LLM tier (enum-constrained, one batched call) has to do the work.
Run: .venv/bin/python eval/categorize_eval.py   (needs GROQ_API_KEY). Appends results to eval/categorize_results.md.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import pandas as pd  # noqa: E402

from app import categorize as cz  # noqa: E402

UNSEEN = {
    "Food & Dining": ["wowmomo", "theobroma", "chaipoint", "mojopizza", "keventers", "lapinoz", "burgersingh"],
    "Groceries": ["spencers", "ratnadeep", "moreretail", "countrydelight", "otipy"],
    "Transport": ["blusmart", "yulu", "quickride", "zoomcar", "ixigo", "cleartrip"],
    "Shopping": ["bewakoof", "boatlifestyle", "mamaearth", "thesouledstore", "pepperfry", "purplle"],
    "Subscriptions": ["crunchyroll", "kukufm", "pocketfm", "storytel"],
    "Health & Fitness": ["fitpass", "truemeds", "thyrocare", "healthians"],
    "Education": ["simplilearn", "testbook", "vedantu", "duolingo"],
    "Utilities & Bills": ["hathway", "torrentpower", "bwssb", "tpddl"],
}
PSP = ["ybl", "paytm", "okaxis", "icici", "axisbank", "hdfcbank"]


def main():
    rows, truth = [], {}
    for cat, names in UNSEEN.items():
        for i, n in enumerate(names):
            assert not cz._dict_match(n), f"{n} is already in merchants.json"
            rows.append(dict(date=pd.Timestamp("2026-09-01"), narration=f"UPI/P2M/{400000000000 + len(rows)}/{n}@{PSP[i % len(PSP)]}/Payment",
                             amount=-499.0, balance=float("nan"), source="eval"))
            truth[n] = cat
    df = pd.DataFrame(rows)
    rules = cz.categorize(df, use_llm=False)
    hybrid = cz.categorize(df, use_llm=True)
    acc = lambda d: sum(truth[m] == c for m, c in zip(d.merchant, d.category))
    n = len(df)
    misses = [(m, truth[m], c) for m, c in zip(hybrid.merchant, hybrid.category) if truth[m] != c]
    lines = [f"# Categorization on {n} unseen merchants", "",
             f"- Rules only: {acc(rules)}/{n} = {acc(rules) / n:.0%} (everything unknown falls to Other)",
             f"- Rules + LLM fallback ({cz.MODEL}, enum-constrained): {acc(hybrid)}/{n} = {acc(hybrid) / n:.0%}", "",
             "Misses (merchant, expected, got):"] + [f"- {m}: {e} → {g}" for m, e, g in misses]
    (ROOT / "eval/categorize_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
