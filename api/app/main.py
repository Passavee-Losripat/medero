"""Medero API: intake, visit WebSocket, prescription, insurance, eval results."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from . import fixed_text as fx
from .config import get_settings
from .pipeline import documents, intake
from .pipeline.visit import VisitSession, new_session
from .providers import asr
from .providers.llm import METER, router_provider, spark_provider
from .safety import glossary
from .schemas import CapturedDoc, IntakeAnswers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("medero.api")

ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "data" / "mock"
EVAL_LATEST = ROOT / "eval" / "results" / "latest.md"
MAX_UPLOAD = 8 * 1024 * 1024
SESSION_TTL_S = 2 * 3600

app = FastAPI(title="Medero API")
settings = get_settings()
# localhost plus private LAN addresses, so a phone/iPad on the same Wi-Fi can use the dev server
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin, "http://localhost:3000"],
                   allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
                                      r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])

# ---------------- in-memory session store (guardrail 10: nothing persisted) ----------------

SESSIONS: dict[str, tuple[VisitSession, float]] = {}


def _sweep() -> None:
    now = time.time()
    for sid in [k for k, (_, t) in SESSIONS.items() if now - t > SESSION_TTL_S]:
        SESSIONS.pop(sid, None)


def get_session(sid: str) -> VisitSession:
    _sweep()
    item = SESSIONS.get(sid)
    if item is None:
        raise HTTPException(404, "session not found")
    SESSIONS[sid] = (item[0], time.time())
    return item[0]


# ---------------- demo protection ----------------

_hits: dict[str, deque] = defaultdict(deque)
_day = {"date": date.today(), "calls_at_start": 0}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _budget_left() -> bool:
    s = get_settings()
    if _day["date"] != date.today():
        _day.update(date=date.today(), calls_at_start=METER.calls)
    if METER.calls - _day["calls_at_start"] >= s.demo_daily_call_cap:
        return False
    cost = METER.est_cost_usd(s)
    return cost is None or cost < s.demo_daily_spend_cap_usd


def _rate_ok(ip: str) -> bool:
    s = get_settings()
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= s.demo_rate_limit_per_min:
        return False
    q.append(now)
    return True


@app.middleware("http")
async def demo_guard(request: Request, call_next):
    s = get_settings()
    if s.demo_mode and request.method != "OPTIONS" and request.url.path not in ("/health", "/eval/latest"):
        if not _rate_ok(_client_ip(request)):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        if not _budget_left():
            return JSONResponse({"error": "daily_demo_budget_reached"}, status_code=503)
    return await call_next(request)


# ---------------- basic ----------------


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "fake_models": s.use_fake, "router": s.router_provider, "demo_mode": s.demo_mode,
            "spark_model": s.spark_model}


@app.get("/demo/case")
def demo_case():
    return json.loads((MOCK / "demo_case.json").read_text(encoding="utf-8"))


@app.get("/glossary")
def get_glossary():
    return {"terms": glossary()}


@app.get("/emergency")
def emergency_card():
    return fx.EMERGENCY_CARD


@app.get("/eval/latest", response_class=PlainTextResponse)
def eval_latest():
    if not EVAL_LATEST.exists():
        return PlainTextResponse("No eval results yet. Run `make eval`.", status_code=404)
    return EVAL_LATEST.read_text(encoding="utf-8")


# ---------------- intake / case card ----------------


@app.post("/intake")
def create_intake(a: IntakeAnswers):
    term = intake.intake_emergency(a)
    if term:
        return {"emergency": True, "card": fx.EMERGENCY_CARD}
    card = intake.build_card(a)
    s = get_settings()
    sess = new_session(card, spark_provider(s), router_provider(s), verifier_model=s.verifier_model_check)
    SESSIONS[sess.id] = (sess, time.time())
    return {"emergency": False, "session_id": sess.id, "card": card.model_dump()}


class Approval(BaseModel):
    approved_ids: list[str]


@app.post("/sessions/{sid}/approve")
async def approve_card(sid: str, body: Approval):
    sess = get_session(sid)
    intake.approve(sess.card, body.approved_ids)
    card, untranslated, err = await intake.render_korean(sess.card, sess.spark)
    return {"card": card.model_dump(), "untranslated_terms": untranslated, "error": err,
            "fake_models": get_settings().use_fake}


@app.get("/sessions/{sid}")
def read_session(sid: str):
    sess = get_session(sid)
    return {"card": sess.card.model_dump(), "consent": sess.consent, "emergency": sess.emergency,
            "summary": sess.summary()}


@app.delete("/sessions/{sid}")
def delete_session(sid: str):
    SESSIONS.pop(sid, None)
    return {"deleted": True}


@app.get("/sessions/{sid}/report")
def session_report(sid: str):
    """Blocked replies and per-turn metrics, for the eval report and the latency overlay."""
    sess = get_session(sid)
    return {"blocked": sess.blocked_log, "metrics": sess.metrics}


# ---------------- visit WebSocket ----------------


@app.websocket("/sessions/{sid}/visit")
async def visit_ws(ws: WebSocket, sid: str):
    await ws.accept()
    item = SESSIONS.get(sid)
    if item is None:
        await ws.send_json({"type": "error", "code": "session_not_found"})
        await ws.close()
        return
    sess = item[0]
    s = get_settings()
    lock = asyncio.Lock()

    async def send_all(events):
        for e in events:
            await ws.send_json(e)

    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            SESSIONS[sid] = (sess, time.time())
            if s.demo_mode and kind in ("clinician_text", "audio_turn", "answer") and not _budget_left():
                await ws.send_json({"type": "error", "code": "daily_demo_budget_reached"})
                continue
            async with lock:
                if kind == "start":
                    await ws.send_json(sess.disclosure())
                elif kind == "consent":
                    await ws.send_json(sess.set_consent(bool(msg.get("accepted"))))
                elif kind == "clinician_text":
                    await send_all(await sess.clinician_turn(str(msg.get("text") or ""),
                                                             uncertain=bool(msg.get("uncertain"))))
                elif kind == "audio_turn":
                    audio = base64.b64decode(msg.get("data") or "")
                    if len(audio) > MAX_UPLOAD:
                        await ws.send_json({"type": "error", "code": "audio_too_large"})
                        continue
                    tr = await asr.transcribe_file(audio, str(msg.get("mime") or "audio/webm"),
                                                   keywords=[t["ko"] for t in glossary()][:50])
                    del audio  # raw audio is never stored
                    if tr.error or not tr.text:
                        await ws.send_json({"type": "asr_failed", "error": tr.error,
                                            "text_patient": fx.patient_text("transcript_uncertain",
                                                                            sess.card.patient_language)})
                        continue
                    await send_all(await sess.clinician_turn(tr.text, uncertain=tr.uncertain,
                                                             asr_ms=tr.latency_ms))
                elif kind == "answer":
                    await send_all(await sess.patient_answer(str(msg.get("ask_id")), str(msg.get("text") or "")))
                elif kind == "summary":
                    await ws.send_json(sess.summary())
                elif kind == "confirm_summary":
                    sess.record.patient_confirmed = True
                    await ws.send_json(sess.summary())
                else:
                    await ws.send_json({"type": "error", "code": "unknown_message"})
    except WebSocketDisconnect:
        return


# ---------------- prescription (P1) ----------------


async def _read_upload(f: UploadFile) -> tuple[bytes, str]:
    data = await f.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file too large")
    return data, f.content_type or "application/octet-stream"


@app.post("/prescription")
async def prescription(file: UploadFile = File(...), lang: str = Form("en")):
    data, mime = await _read_upload(file)
    reading = await documents.read_prescription(data, mime, lang, spark_provider())
    return {**reading.model_dump(), "fake_models": get_settings().use_fake}


# ---------------- insurance (P1) ----------------


@app.post("/insurance/checklist")
async def insurance_checklist(file: UploadFile | None = File(None), text: str | None = Form(None)):
    if file is None and not text:
        raise HTTPException(400, "upload the insurer's page/PDF or paste its text")
    if file is not None:
        data, mime = await _read_upload(file)
        name, docs, err = await documents.parse_checklist(spark_provider(), data=data, mime=mime)
    else:
        name, docs, err = await documents.parse_checklist(spark_provider(), text=text)
    return {"insurer_name": name, "required_docs": docs, "error": err, "fake_models": get_settings().use_fake,
            "notice": fx.patient_text("insurance_notice", "en")}


@app.post("/insurance/capture")
async def insurance_capture(file: UploadFile = File(...)):
    data, mime = await _read_upload(file)
    doc = await documents.capture_doc(data, mime, spark_provider())
    return {**doc.model_dump(), "fake_models": get_settings().use_fake}


class PackRequest(BaseModel):
    insurer_name: str | None = None
    required_docs: list[str]
    captured: list[CapturedDoc] = []
    have: list[str] = []
    lang: str = "en"


@app.post("/insurance/pack")
def insurance_pack(body: PackRequest):
    pack = documents.build_pack(body.insurer_name, body.required_docs, body.captured, body.have)
    return {**pack.model_dump(), "notice": fx.patient_text("insurance_notice", body.lang)}
