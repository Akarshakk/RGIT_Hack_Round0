"""FastAPI app: upload -> dashboard -> chat. State lives in memory only, per session cookie, 30 min TTL."""
import json
import os
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, Cookie, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from app import analytics as an  # noqa: E402
from app.categorize import BUCKET, CATEGORIES, categorize, recategorize  # noqa: E402
from app.chat import stream_chat  # noqa: E402
from app.ingest import NeedsMapping, load_statement  # noqa: E402
from app import wrapped as wr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES, MAX_ROWS, TTL = 10 * 1024 * 1024, 20000, 30 * 60
SESSIONS = {}
app = FastAPI(title="Credence")


def _session(sid):
    now = time.time()
    for k in [k for k, v in SESSIONS.items() if now - v["ts"] > TTL]:
        del SESSIONS[k]
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(401, "No statement loaded (or the session expired). Upload a statement first.")
    s["ts"] = now
    return s


def _start(resp, df):
    if len(df) > MAX_ROWS:
        raise HTTPException(413, f"Too many transactions ({len(df)}). The limit is {MAX_ROWS}.")
    sid = secrets.token_urlsafe(16)
    SESSIONS[sid] = dict(df=categorize(df), overrides={}, history=[], ts=time.time())
    resp.set_cookie("sid", sid, httponly=True, samesite="lax", max_age=TTL)
    return dict(rows=len(df), from_date=str(df.date.min().date()), to_date=str(df.date.max().date()))


def _ingest(resp, data, name, password, mapping):
    try:
        return _start(resp, load_statement(data, name, password or None, mapping))
    except NeedsMapping as e:
        if not e.columns:
            raise HTTPException(400, "Could not find a transaction table in this file.")
        return dict(needs_mapping=True, columns=e.columns)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Could not read this file. Try a CSV, XLSX or PDF bank statement.")


@app.get("/status")
def status(sid: str | None = Cookie(None)):
    live = sid in SESSIONS and time.time() - SESSIONS[sid]["ts"] <= TTL
    return dict(chat_enabled=bool(os.environ.get("GROQ_API_KEY")), categories=CATEGORIES, has_session=live)


@app.post("/upload")
async def upload(response: Response, file: UploadFile = File(...), password: str = Form(""), mapping: str = Form("")):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    return _ingest(response, data, file.filename or "statement", password, json.loads(mapping) if mapping else None)


@app.post("/sample")
def sample(response: Response, kind: str = "csv"):
    name, pw = ("statement.pdf", "kharcha123") if kind == "pdf" else ("hdfc_style.csv", None)
    return _ingest(response, (ROOT / "data" / "samples" / name).read_bytes(), name, pw, None)


@app.get("/overview")
def overview(period: str | None = None, sid: str | None = Cookie(None)):
    df = _session(sid)["df"]
    return dict(overview=an.get_overview(df, period), categories=an.category_breakdown(df, period),
                buckets=_buckets(df, period), trend=an.monthly_trend(df), trend_buckets=_trend_buckets(df),
                insights=an.generate_insights(df))


def _trend_buckets(df):
    d = an._spend(df)
    g = d.groupby([d["date"].dt.strftime("%Y-%m"), "bucket"]).amount.sum().unstack(fill_value=0)
    return {m: {b: an.R(-r.get(b, 0)) for b in ("Need", "Want", "Transfer")} for m, r in g.iterrows()}


def _buckets(df, period):
    d = an._spend(an._period(df, period))
    tot = -d.amount.sum()
    return {b: round(float(100 * -d.amount[d.bucket == b].sum() / tot), 1) for b in ("Need", "Want", "Transfer")} if tot else {}


@app.get("/insights")
def insights(sid: str | None = Cookie(None)):
    return an.generate_insights(_session(sid)["df"])


@app.get("/transactions")
def transactions(limit: int = 200, sid: str | None = Cookie(None)):
    df = _session(sid)["df"].tail(limit).iloc[::-1]
    return [dict(id=int(i), date=str(r.date.date()), narration=r.narration, merchant=r.merchant, amount=round(float(r.amount)),
                 category=r.category, cat_source=r.cat_source) for i, r in df.iterrows()]


@app.post("/recategorize")
def recat(merchant: str = Body(...), category: str = Body(...), sid: str | None = Cookie(None)):
    s = _session(sid)
    if category not in BUCKET:
        raise HTTPException(400, "Unknown category")
    recategorize(s["df"], s["overrides"], merchant, category)
    return dict(ok=True)


@app.post("/simulate")
def simulate(changes: list[dict] = Body(..., embed=True), sid: str | None = Cookie(None)):
    return an.simulate_savings(_session(sid)["df"], changes)


@app.post("/goal")
def goal(target: float = Body(..., embed=True), months: int = Body(..., embed=True), sid: str | None = Cookie(None)):
    return an.plan_goal(_session(sid)["df"], target, max(1, months))


@app.get("/wrapped")
def wrapped(sid: str | None = Cookie(None)):
    s = _session(sid)
    s["story"] = wr.build(s["df"])
    return s["story"]


@app.post("/wrapped/ai")
def wrapped_ai(sid: str | None = Cookie(None)):
    """LLM-written quips for the story; each one is dropped unless every number in it is already on its card."""
    s = _session(sid)
    story = s.get("story") or wr.build(s["df"])
    return dict(quips=wr.ai_quips(story))


@app.post("/chat")
def chat(message: str = Body(..., embed=True), sid: str | None = Cookie(None)):
    s = _session(sid)

    def gen():
        for event, data in stream_chat(s, message[:2000]):
            yield f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.delete("/session")
def delete(response: Response, sid: str | None = Cookie(None)):
    SESSIONS.pop(sid, None)
    response.delete_cookie("sid")
    return dict(deleted=True)


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
