"""Turn router: classify a finished clinician turn into a TurnClass.

Two implementations share one post-processing step:
- rules_route: offline keyword baseline (no model). Used when ROUTER_PROVIDER=rules
  and as a benchmark baseline.
- model_route: Glimmer (local / Modal) or Spark via the same prompt.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from ..providers.llm import LLMProvider
from ..schemas import TURN_CLASSES, CaseCard
from . import prompts


@dataclass
class RouteResult:
    turn_class: str
    fact_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: float = 0.0
    provider: str = "rules"
    api_call: bool = False
    error: str | None = None


def fact_label(fact_id: str) -> str:
    base = {
        "cc": "main complaint / why they came", "allergy": "allergies", "meds": "current medications",
        "sym_onset": "when it started", "sym_duration": "how long", "sym_site": "where / which side",
        "sym_severity": "how bad / pain level",
    }
    if fact_id in base:
        return base[fact_id]
    if fact_id.startswith("sym_"):
        return "other symptom"
    if fact_id.startswith("tried_"):
        return "something already tried (medicine, drops, rest)"
    if fact_id.startswith("hx_"):
        return "past medical history"
    if fact_id.startswith("conf_"):
        return "fact the patient confirmed during this visit"
    return fact_id


# Keyword cues for the rules baseline. Korean needs native-speaker review.
_DECISION = ["할까요", "하시겠", "드릴까요", "원하세", "괜찮으시면", "동의", "선택", "주사 맞", "검사 받",
             "검사를 받", "결제", "수납", "카드로", "현금", "처방해 드릴", "어느 쪽", "어떤 걸로", "받으시겠"]
_PROCEDURAL = ["앉으세요", "앉아", "기다려", "기다리", "위를 보", "아래를 보", "눈을 감", "눈을 떠",
               "들어오세요", "나가셔서", "약국", "다음 분", "누우세요", "입을 벌", "이쪽으로", "잠깐만요",
               "보여 주세요", "보여주세요", "턱을"]
_QUESTION = re.compile(r"(\?|요\?|까\?|세요$|나요|어요$|가요|있어요|있으세요|없으세요|했어요|하셨어요|드셨|셨어요|니까)")
_FACT_CUES: dict[str, list[str]] = {
    "allergy": ["알레르기", "알러지"],
    "meds": ["드시는 약", "먹는 약", "복용", "약 드시", "드시고 계신 약"],
    "sym_onset": ["언제부터", "언제", "시작"],
    "sym_duration": ["며칠", "얼마나 됐", "얼마나 되", "기간"],
    "sym_site": ["어디", "어느 쪽", "양쪽", "한쪽"],
    "sym_severity": ["얼마나 아프", "많이 아프", "통증", "몇 점"],
    "cc": ["어떻게 오셨", "어디가 불편", "무슨 일", "어디가 아프"],
    "tried_": ["써 보셨", "드셔 보셨", "넣어 보셨", "해 보셨", "사용해"],
    "hx_": ["전에도", "병력", "이전에", "수술"],
}


def rules_route(utterance: str, card: CaseCard) -> RouteResult:
    t0 = time.perf_counter()
    u = utterance.strip()
    ids: list[str] = []
    if len(re.sub(r"\s", "", u)) < 2:
        cls = "unclear"
    elif any(k in u for k in _DECISION):
        cls = "needs_decision"
    else:
        for fid, cues in _FACT_CUES.items():
            if any(c in u for c in cues):
                ids += [f.id for f in card.all_facts() if f.id == fid or (fid.endswith("_") and f.id.startswith(fid))]
        if ids:
            cls = "on_card"
        elif any(k in u for k in _PROCEDURAL) and not u.endswith("?"):
            cls = "procedural"
        elif _QUESTION.search(u):
            cls = "needs_fact"
        else:
            cls = "procedural"
    r = RouteResult(turn_class=cls, fact_ids=ids, confidence=0.5, provider="rules",
                    latency_ms=(time.perf_counter() - t0) * 1000)
    return finalize(r, card)


async def model_route(utterance: str, card: CaseCard, provider: LLMProvider) -> RouteResult:
    ids = [f.id for f in card.all_facts()]
    res = await provider.json(
        task="route_turn", system=prompts.ROUTER_SYSTEM,
        user=prompts.router_user(utterance, ids, {i: fact_label(i) for i in ids}),
        schema=prompts.ROUTER_SCHEMA,
    )
    is_api = provider.name in {"spark"}
    if res.data is None or res.data.get("turn_class") not in TURN_CLASSES:
        # Router failure is treated as unclear: the safe path asks rather than answers.
        return RouteResult(turn_class="unclear", latency_ms=res.latency_ms, provider=provider.name,
                           api_call=is_api, error=res.error or "bad_class")
    r = RouteResult(
        turn_class=res.data["turn_class"],
        fact_ids=[str(x) for x in res.data.get("fact_ids") or []],
        confidence=float(res.data.get("confidence") or 0.0),
        latency_ms=res.latency_ms, provider=provider.name, api_call=is_api,
    )
    return finalize(r, card)


def finalize(r: RouteResult, card: CaseCard) -> RouteResult:
    """on_card only if at least one cited fact is speakable; otherwise the patient must be asked."""
    if r.turn_class == "on_card":
        speakable = {f.id for f in card.speakable()}
        r.fact_ids = [i for i in r.fact_ids if i in speakable]
        if not r.fact_ids:
            r.turn_class = "needs_fact"
    else:
        r.fact_ids = []
    return r


async def route(utterance: str, card: CaseCard, provider: LLMProvider | None) -> RouteResult:
    if provider is None:
        return rules_route(utterance, card)
    return await model_route(utterance, card, provider)
