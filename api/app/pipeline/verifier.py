"""Verifier (CLAUDE.md section 5): deterministic rules first, optional model check second."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..fixed_text import HOLDING_PHRASE_KO, REPEAT_KO
from ..providers.llm import LLMProvider
from ..schemas import CaseCard, ReplyPlan
from . import prompts

FIXED_PHRASES = {HOLDING_PHRASE_KO, REPEAT_KO}


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    model_checked: bool = False
    latency_ms: float = 0.0


_KO_NUM = {"하루": "1", "이틀": "2", "사흘": "3", "나흘": "4", "닷새": "5", "엿새": "6", "이레": "7",
           "열흘": "10", "보름": "15", "일주일": "7", "한 달": "1", "한달": "1",
           "한 번": "1", "두 번": "2", "세 번": "3", "네 번": "4", "한번": "1", "두번": "2", "세번": "3",
           "일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "육": "6", "칠": "7", "팔": "8", "구": "9", "십": "10"}
_KO_SINO_UNIT = re.compile(r"(?<![가-힣])((일|이|삼|사|오|육|칠|팔|구|십)\s?(일|주|개월|년|회|시간|분|도)(?=[\s,.?!~]|$|간|째|동안|전|에|이|은|정도))")
_KO_NATIVE = re.compile(r"(하루|이틀|사흘|나흘|닷새|엿새|이레|열흘|보름|일주일|한 ?달|[한두세네] ?번)")
_EN_NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
           "eight": "8", "nine": "9", "ten": "10", "a week": "7", "week": "7", "once": "1", "twice": "2",
           "a day": "1", "yesterday": "1", "a month": "1",
           "หนึ่ง": "1", "สอง": "2", "สาม": "3", "สี่": "4", "ห้า": "5", "หก": "6", "เจ็ด": "7", "สัปดาห์": "7"}
_DIGITS = re.compile(r"\d+(?:\.\d+)?")


def numbers_in_korean(text: str) -> set[str]:
    nums = set(_DIGITS.findall(text))
    for m in _KO_NATIVE.findall(text):
        nums.add(_KO_NUM.get(m.replace(" ", ""), _KO_NUM.get(m, "")))
    for m in _KO_SINO_UNIT.finditer(_KO_NATIVE.sub(" ", text)):
        nums.add(_KO_NUM[m.group(2)])
    nums.discard("")
    return nums


def numbers_in_fact(text: str) -> set[str]:
    nums = set(_DIGITS.findall(text or ""))
    low = (text or "").lower()
    for word, d in _EN_NUM.items():
        if word in low:
            nums.add(d)
    return nums | numbers_in_korean(text or "")


def check_rules(plan: ReplyPlan, card: CaseCard) -> Verdict:
    reasons: list[str] = []
    reply = (plan.reply_ko or "").strip()
    fixed = reply in FIXED_PHRASES

    # Rule 4: needs_fact / needs_decision never produce a reply, only the holding phrase.
    if plan.turn_class in ("needs_fact", "needs_decision"):
        if reply and reply != HOLDING_PHRASE_KO:
            reasons.append("rule4_reply_on_ask_turn")
        if plan.ask_patient is None:
            reasons.append("rule4_missing_ask_back")
        return Verdict(ok=not reasons, reasons=reasons)

    if not reply or fixed:
        return Verdict(ok=True)

    # Rule 1: a reply about the patient cites evidence.
    if not plan.evidence:
        reasons.append("rule1_no_evidence")

    # Rule 2: every evidence id exists, is approved, may be answered, and is known.
    speakable = {f.id: f for f in card.speakable()}
    cited = []
    for fid in plan.evidence:
        f = card.fact(fid)
        if f is None:
            reasons.append(f"rule2_unknown_id:{fid}")
        elif fid not in speakable:
            reasons.append(f"rule2_not_speakable:{fid}")
        else:
            cited.append(f)

    # Rule 3: numbers, dosages, dates and durations must appear in the cited facts.
    allowed = set()
    for f in cited:
        allowed |= numbers_in_fact(f.value or "") | numbers_in_fact(f.value_ko or "")
    for n in numbers_in_korean(reply):
        if n not in allowed:
            reasons.append(f"rule3_number_not_in_evidence:{n}")

    return Verdict(ok=not reasons, reasons=reasons)


async def check_model(plan: ReplyPlan, card: CaseCard, provider: LLMProvider) -> Verdict:
    """Rule 5: ask Spark whether the reply asserts anything beyond the evidence. Failure blocks."""
    ev = []
    for fid in plan.evidence:
        f = card.fact(fid)
        if f:
            ev.append({"id": f.id, "value": f.value, "value_ko": f.value_ko})
    res = await provider.json(task="verify_reply", system=prompts.CHECK_SYSTEM,
                              user=prompts.check_user(plan.reply_ko or "", ev),
                              schema=prompts.CHECK_SCHEMA)
    if res.data is None:
        return Verdict(ok=False, reasons=[f"rule5_check_failed:{res.error}"], model_checked=True,
                       latency_ms=res.latency_ms)
    if res.data.get("unsupported"):
        return Verdict(ok=False, reasons=[f"rule5_unsupported:{res.data.get('reason', '')[:120]}"],
                       model_checked=True, latency_ms=res.latency_ms)
    return Verdict(ok=True, model_checked=True, latency_ms=res.latency_ms)


async def verify(plan: ReplyPlan, card: CaseCard, provider: LLMProvider | None) -> Verdict:
    v = check_rules(plan, card)
    if not v.ok or provider is None:
        return v
    reply = (plan.reply_ko or "").strip()
    if not reply or reply in FIXED_PHRASES:
        return v
    return await check_model(plan, card, provider)
