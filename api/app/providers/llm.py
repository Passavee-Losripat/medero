"""LLM providers behind one interface.

- OpenAICompatProvider: the official OpenAI SDK pointed at the Meta Model API,
  a local llama.cpp server (Glimmer 4-bit), or a Glimmer endpoint on Modal.
- FakeProvider: deterministic, no network. Used by tests and by the UI when no
  key is set. Its outputs are labelled FAKE and are never reported as results.

Every call has a timeout, a retry limit and a logged latency (CLAUDE.md section 11).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..config import Settings, get_settings

log = logging.getLogger("medero.llm")

Content = str | list[dict[str, Any]]


@dataclass
class LLMResult:
    data: dict | None
    latency_ms: float
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    fake: bool = False


@dataclass
class UsageMeter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, r: LLMResult) -> None:
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        self.by_model[r.model] = self.by_model.get(r.model, 0) + 1

    def est_cost_usd(self, s: Settings) -> float | None:
        if s.spark_price_in_per_m is None or s.spark_price_out_per_m is None:
            return None
        return (self.input_tokens * s.spark_price_in_per_m + self.output_tokens * s.spark_price_out_per_m) / 1e6


METER = UsageMeter()


class LLMProvider(Protocol):
    name: str
    model: str

    async def json(self, *, task: str, system: str, user: Content, schema: dict,
                   timeout_s: float | None = None, effort: str | None = None) -> LLMResult: ...


class OpenAICompatProvider:
    def __init__(self, *, name: str, base_url: str, api_key: str, model: str,
                 settings: Settings | None = None, send_effort: bool = True, extra_body: dict | None = None,
                 timeout_s: float | None = None, local: bool = False):
        from openai import AsyncOpenAI

        self.name = name
        self.model = model
        self.settings = settings or get_settings()
        self.send_effort = send_effort
        self.extra_body = extra_body
        self.default_timeout = timeout_s
        self.local = local  # runs on infrastructure we control; never a third-party API
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "none", max_retries=0)

    async def json(self, *, task: str, system: str, user: Content, schema: dict,
                   timeout_s: float | None = None, effort: str | None = None) -> LLMResult:
        timeout = max(timeout_s or 0, self.default_timeout or 0) or self.settings.model_timeout_s
        effort = effort if effort is not None else self.settings.reasoning_effort
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": task, "schema": schema, "strict": False}},
            "temperature": 0,
        }
        if effort and self.send_effort:
            kwargs["reasoning_effort"] = effort
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        last_err = "unknown"
        for attempt in range(self.settings.model_max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = await asyncio.wait_for(self.client.chat.completions.create(**kwargs), timeout=timeout)
                ms = (time.perf_counter() - t0) * 1000
                text = resp.choices[0].message.content or ""
                usage = getattr(resp, "usage", None)
                result = LLMResult(
                    data=_parse_json(text), latency_ms=ms, model=self.model,
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                )
                if result.data is None:
                    result.error = "invalid_json"
                METER.add(result)
                log.info("llm task=%s provider=%s model=%s ms=%.0f attempt=%d err=%s",
                         task, self.name, self.model, ms, attempt, result.error)
                if result.data is not None:
                    return result
                last_err = "invalid_json"
            except asyncio.TimeoutError:
                last_err = "timeout"
                log.warning("llm task=%s provider=%s timeout after %.1fs", task, self.name, timeout)
            except Exception as e:  # network / API error: logged, then retried or reported
                last_err = f"{type(e).__name__}: {e}"[:300]
                log.warning("llm task=%s provider=%s error=%s", task, self.name, last_err)
        return LLMResult(data=None, latency_ms=0, model=self.model, error=last_err)


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    try:
        v = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            v = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return v if isinstance(v, dict) else None


FakeHandler = Callable[[str, str, Content], dict | None]


class FakeProvider:
    """Deterministic offline provider. Outputs are not real model results."""

    def __init__(self, handler: FakeHandler | None = None, name: str = "fake", model: str = "fake",
                 delay_ms: float = 0):
        from .fake import default_handler

        self.name = name
        self.model = model
        self.handler = handler or default_handler
        self.delay_ms = delay_ms

    async def json(self, *, task: str, system: str, user: Content, schema: dict,
                   timeout_s: float | None = None, effort: str | None = None) -> LLMResult:
        t0 = time.perf_counter()
        if self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)
        data = self.handler(task, system, user)
        r = LLMResult(data=data, latency_ms=(time.perf_counter() - t0) * 1000, model=self.model, fake=True,
                      error=None if data is not None else "fake_none")
        METER.add(r)
        return r


def spark_provider(s: Settings | None = None) -> LLMProvider:
    s = s or get_settings()
    if s.use_fake:
        return FakeProvider(name="fake-spark", model="fake-spark")
    return OpenAICompatProvider(name="spark", base_url=s.model_api_base, api_key=s.model_api_key,
                                model=s.spark_model, settings=s)


def router_provider(s: Settings | None = None, which: str | None = None) -> LLMProvider | None:
    """Provider for the turn router. None means the offline rules router."""
    s = s or get_settings()
    which = which or s.router_provider
    if which == "rules":
        return None
    if which in ("local", "modal"):
        return glimmer_provider(s, which)
    return spark_provider(s)


def glimmer_provider(s: Settings | None = None, where: str = "local") -> LLMProvider:
    """Muse Glimmer 4-bit via llama.cpp: on this machine ("local") or our own Modal endpoint ("modal")."""
    s = s or get_settings()
    kw = {"extra_body": {"chat_template_kwargs": {"reasoning_strength": s.local_reasoning}},
          "send_effort": False, "settings": s, "timeout_s": s.local_timeout_s, "local": True}
    if where == "modal":
        return OpenAICompatProvider(name="modal-glimmer", base_url=s.modal_llm_base, api_key=s.modal_llm_key,
                                    model=s.modal_llm_model, **kw)
    return OpenAICompatProvider(name="local-glimmer", base_url=s.local_llm_base, api_key="local",
                                model=s.local_llm_model, **kw)


def doc_provider(s: Settings | None = None) -> LLMProvider:
    """Provider for photos that may carry identifiers (guardrail 10)."""
    s = s or get_settings()
    if s.doc_provider in ("local", "modal"):
        return glimmer_provider(s, s.doc_provider)
    return spark_provider(s)
