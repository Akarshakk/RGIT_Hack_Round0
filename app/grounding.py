"""Live grounding check: is every ₹ figure and percentage in a reply traceable to a tool result (or the user's question)?

Shared by the chat stream (the UI shows a "numbers verified" badge per answer) and eval/run_eval.py.
"""
import json
import re

_RUPEE = re.compile(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d+)?)", re.I)
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_ANY = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _pool(*sources):
    out = set()
    for s in sources:
        text = s if isinstance(s, str) else json.dumps(s, default=str, ensure_ascii=False)
        for x in _ANY.findall(text):
            try:
                out.add(abs(float(x.replace(",", ""))))
            except ValueError:
                pass
    return out


def check(reply, tool_results, user_text=""):
    """-> {verified, total, unverified: ['₹5,000', '64%']}. Rupees match within ₹1, percentages within 0.5 points
    (so a tool's 34.4% may be quoted as 34%)."""
    pool = _pool(user_text, *tool_results)
    claims = [("₹" + m, float(m.replace(",", "")), 1.0) for m in _RUPEE.findall(reply)]
    claims += [(m + "%", float(m), 0.5) for m in _PCT.findall(reply)]
    bad = [label for label, v, tol in claims if not any(abs(v - p) <= tol for p in pool)]
    return dict(verified=len(claims) - len(bad), total=len(claims), unverified=list(dict.fromkeys(bad)))
