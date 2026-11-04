"""Muse Voice Transcribe adapters.

File endpoint: VERIFIED 2026-11-04 against the docs and a live call.
Realtime adapter: still to be aligned with the documented handshake (authorization.accessToken
in the first JSON frame); not used by the UI. Raw audio is never stored (guardrail 10).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from ..config import Settings, get_settings


@dataclass
class Transcript:
    text: str
    final: bool
    latency_ms: float
    uncertain: bool = False
    error: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


def _extract_text(payload: dict) -> str:
    for key in ("text", "transcript"):
        if isinstance(payload.get(key), str):
            return payload[key]
    for key in ("segments", "turns", "results"):
        items = payload.get(key)
        if isinstance(items, list):
            return " ".join(str(i.get("text") or i.get("transcript") or "") for i in items if isinstance(i, dict))
    return ""


def _low_confidence(payload: dict) -> bool:
    conf = payload.get("confidence")
    if isinstance(conf, (int, float)):
        return conf < 0.6
    return False


async def transcribe_file(audio: bytes, mime: str = "audio/wav", *, language_bias: list[str] | None = None,
                          keywords: list[str] | None = None, s: Settings | None = None) -> Transcript:
    """POST /v1/asr/transcribe (VERIFIED 2026-11-04, see docs/api-notes.md).

    Multipart: `request` JSON part + `audio` part. Audio must be mono 16-bit PCM WAV at 16/24 kHz
    (the browser encodes WAV itself). Omit languageBias to auto-detect (Korean vs patient language).
    """
    s = s or get_settings()
    if s.use_fake:
        return Transcript(text="", final=True, latency_ms=0, uncertain=True, error="no_api_key")
    url = s.model_api_base.rstrip("/") + "/asr/transcribe"
    req: dict = {"model": s.asr_model, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
    if keywords:
        req["keywords"] = keywords[:100]
    if language_bias:
        req["languageBias"] = language_bias
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=s.model_timeout_s * 2) as client:
            r = await client.post(url, headers={"Authorization": f"Bearer {s.model_api_key}"},
                                  files={"request": (None, json.dumps(req), "application/json"),
                                         "audio": ("turn.wav", audio, "audio/wav")})
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code >= 400:
            return Transcript(text="", final=True, latency_ms=ms, uncertain=True,
                              error=f"http_{r.status_code}:{r.text[:200]}")
        payload = r.json()
        text = _clean(_extract_text(payload))
        return Transcript(text=text, final=True, latency_ms=ms, uncertain=not text)
    except Exception as e:
        return Transcript(text="", final=True, latency_ms=(time.perf_counter() - t0) * 1000, uncertain=True,
                          error=f"{type(e).__name__}: {e}"[:200])


def _clean(text: str) -> str:
    # Observed: trailing punctuation noise such as "??!" or "?.," on short clips.
    text = text.strip()
    return re.sub(r"([?.!,]){2,}$", lambda m: m.group(0)[0], text)


class RealtimeASR:
    """Relay PCM16 16 kHz mono chunks to the realtime endpoint and yield transcripts.

    VERIFY: auth header, session config message, audio framing (binary vs base64 JSON),
    and the event names for interim/final/end-of-turn. Parsing is tolerant on purpose.
    """

    def __init__(self, s: Settings | None = None, language: str = "ko"):
        self.s = s or get_settings()
        self.language = language
        self.ws = None
        self.t_last_audio = 0.0

    async def connect(self) -> None:
        import websockets

        self.ws = await websockets.connect(
            self.s.asr_realtime_url,
            additional_headers={"Authorization": f"Bearer {self.s.model_api_key}"},
            open_timeout=self.s.model_timeout_s,
        )
        await self.ws.send(json.dumps({"type": "session.update", "model": self.s.asr_model,
                                       "language": self.language, "audio_format": "pcm16",
                                       "sample_rate": 16000}))

    async def send_audio(self, chunk: bytes) -> None:
        self.t_last_audio = time.perf_counter()
        await self.ws.send(chunk)

    async def events(self) -> AsyncIterator[Transcript]:
        async for raw in self.ws:
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = str(msg.get("type") or msg.get("event") or "")
            text = _extract_text(msg)
            final = bool(msg.get("is_final") or msg.get("final") or "final" in kind or "end" in kind
                         or "completed" in kind)
            if "error" in kind:
                yield Transcript(text="", final=True, latency_ms=0, uncertain=True, error=str(msg)[:200])
                continue
            if text or final:
                ms = (time.perf_counter() - self.t_last_audio) * 1000 if final else 0
                yield Transcript(text=text, final=final, latency_ms=ms, uncertain=_low_confidence(msg))

    async def close(self) -> None:
        if self.ws is not None:
            try:
                await asyncio.wait_for(self.ws.close(), timeout=2)
            except Exception:
                pass
