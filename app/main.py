"""FastAPI app: upload -> dashboard -> chat.

Stateless across server instances: after upload the browser holds a compressed copy of the processed statement in page
memory (never in storage) and sends it with every request. Each instance caches the decoded statement for 30 minutes,
so serverless hosts that spread requests over several instances still answer every call.
"""
import base64
import hashlib
import json
import os
import time
import zlib
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
from fastapi import Body, Cookie, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
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


def _pack(df, overrides):
    d = df.copy()
    d["date"] = d["date"].dt.strftime("%Y-%m-%d")
    raw = json.dumps({"v": 1, "split": json.loads(d.to_json(orient="split")), "overrides": overrides}, separators=(",", ":"))
    return base64.urlsafe_b64encode(zlib.compress(raw.encode(), 6)).decode()


def _unpack(blob):
    p = json.loads(zlib.decompress(base64.urlsafe_b64decode(blob.encode())))
    sp = p["split"]
    df = pd.DataFrame(sp["data"], columns=sp["columns"], index=sp["index"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ("amount", "balance"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, p.get("overrides", {})


def _key(blob):
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _remember(df, overrides, history=None):
    blob = _pack(df, overrides)
    key = _key(blob)
    SESSIONS[key] = dict(df=df, overrides=overrides, history=history or [], ts=time.time(), blob=blob)
    return key, blob


async def _session(request: Request, sid=None):
    """The statement for this request: from this instance's cache, else rebuilt from the blob the browser sent."""
    now = time.time()
    for k in [k for k, v in SESSIONS.items() if now - v["ts"] > TTL]:
        del SESSIONS[k]
    blob = None
    if request.method in ("POST", "DELETE"):
        try:
            body = await request.json()
            blob = body.get("blob") if isinstance(body, dict) else None
        except Exception:
            blob = None
    key = _key(blob) if blob else sid
    s = SESSIONS.get(key)
    if not s and blob:
        try:
            df, overrides = _unpack(blob)
        except Exception:
            raise HTTPException(400, "Your statement data couldn't be read. Upload the statement again.")
        s = SESSIONS[key] = dict(df=df, overrides=overrides, history=[], ts=now, blob=blob)
    if not s:
        raise HTTPException(401, "No statement loaded (or it expired after 30 minutes). Upload a statement first.")
    s["ts"] = now
    return s


def _start(resp, df):
    if len(df) > MAX_ROWS:
        raise HTTPException(413, f"Too many transactions ({len(df)}). The limit is {MAX_ROWS}.")
    key, blob = _remember(categorize(df), {})
    resp.set_cookie("sid", key, httponly=True, samesite="lax", max_age=TTL)
    return dict(rows=len(df), from_date=str(df.date.min().date()), to_date=str(df.date.max().date()), blob=blob)


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
def status(sid: Optional[str] = Cookie(None)):
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
    name, pw = {"pdf": ("statement.pdf", "kharcha123"), "axis": ("axis_style_bengaluru.csv", None)}.get(kind, ("hdfc_style.csv", None))
    return _ingest(response, (ROOT / "data" / "samples" / name).read_bytes(), name, pw, None)


@app.api_route("/overview", methods=["GET", "POST"])
async def overview(request: Request, period: Optional[str] = None, sid: Optional[str] = Cookie(None)):
    df = (await _session(request, sid))["df"]
    return dict(overview=an.get_overview(df, period), categories=an.category_breakdown(df, period),
                buckets=_buckets(df, period), trend=an.monthly_trend(df), trend_buckets=_trend_buckets(df),
                insights=an.generate_insights(df), friends=an.friend_ledger(df), quick_wins=an.quick_wins(df))


def _trend_buckets(df):
    d = an._spend(df)
    g = d.groupby([d["date"].dt.strftime("%Y-%m"), "bucket"]).amount.sum().unstack(fill_value=0)
    return {m: {b: an.R(-r.get(b, 0)) for b in ("Need", "Want", "Transfer")} for m, r in g.iterrows()}


def _buckets(df, period):
    d = an._spend(an._period(df, period))
    tot = -d.amount.sum()
    return {b: round(float(100 * -d.amount[d.bucket == b].sum() / tot), 1) for b in ("Need", "Want", "Transfer")} if tot else {}


@app.api_route("/insights", methods=["GET", "POST"])
async def insights(request: Request, sid: Optional[str] = Cookie(None)):
    return an.generate_insights((await _session(request, sid))["df"])


@app.api_route("/transactions", methods=["GET", "POST"])
async def transactions(request: Request, limit: int = 200, sid: Optional[str] = Cookie(None)):
    df = (await _session(request, sid))["df"].tail(limit).iloc[::-1]
    return [dict(id=int(i), date=str(r.date.date()), narration=r.narration, merchant=r.merchant, amount=round(float(r.amount)),
                 category=r.category, cat_source=r.cat_source) for i, r in df.iterrows()]


@app.post("/recategorize")
async def recat(request: Request, response: Response, merchant: str = Body(...), category: str = Body(...), sid: Optional[str] = Cookie(None)):
    s = await _session(request, sid)
    if category not in BUCKET:
        raise HTTPException(400, "Unknown category")
    df, overrides = s["df"].copy(), dict(s["overrides"])
    recategorize(df, overrides, merchant, category)
    key, blob = _remember(df, overrides, s["history"])
    response.set_cookie("sid", key, httponly=True, samesite="lax", max_age=TTL)
    return dict(ok=True, blob=blob)


@app.post("/simulate")
async def simulate(request: Request, changes: list[dict] = Body(..., embed=True), sid: Optional[str] = Cookie(None)):
    return an.simulate_savings((await _session(request, sid))["df"], changes)


@app.api_route("/future", methods=["GET", "POST"])
async def future(request: Request, monthly: Optional[float] = None, years: int = 10, rate_pct: float = 10.0, sid: Optional[str] = Cookie(None)):
    return an.future_you((await _session(request, sid))["df"], monthly, years, max(0.0, min(rate_pct, 20.0)))


@app.post("/goal")
async def goal(request: Request, target: float = Body(..., embed=True), months: int = Body(..., embed=True), sid: Optional[str] = Cookie(None)):
    return an.plan_goal((await _session(request, sid))["df"], target, max(1, months))


@app.api_route("/wrapped", methods=["GET", "POST"])
async def wrapped(request: Request, sid: Optional[str] = Cookie(None)):
    s = await _session(request, sid)
    s["story"] = wr.build(s["df"])
    return s["story"]


@app.post("/wrapped/ai")
async def wrapped_ai(request: Request, sid: Optional[str] = Cookie(None)):
    """LLM-written quips for the story; each one is dropped unless every number in it is already on its card."""
    s = await _session(request, sid)
    story = s.get("story") or wr.build(s["df"])
    return dict(quips=wr.ai_quips(story))


@app.post("/chat")
async def chat(request: Request, message: str = Body(..., embed=True), sid: Optional[str] = Cookie(None)):
    s = await _session(request, sid)

    def gen():
        for event, data in stream_chat(s, message[:2000]):
            yield f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.delete("/session")
async def delete(request: Request, response: Response, sid: Optional[str] = Cookie(None)):
    blob = None
    try:
        body = await request.json()
        blob = body.get("blob") if isinstance(body, dict) else None
    except Exception:
        pass
    SESSIONS.pop(sid, None)
    if blob:
        SESSIONS.pop(_key(blob), None)
    response.delete_cookie("sid")
    return dict(deleted=True)


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
