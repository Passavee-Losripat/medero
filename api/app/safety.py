"""Deterministic guardrails: emergency signals and glossary lookup.

Emergency detection is keyword-based on purpose: it must work without a model
and must err on the side of stopping. Lists need native-speaker review.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

EMERGENCY_TERMS: dict[str, list[str]] = {
    "en": [
        "chest pain", "can't breathe", "cannot breathe", "trouble breathing", "difficulty breathing",
        "short of breath", "severe bleeding", "bleeding heavily", "won't stop bleeding",
        "unconscious", "passed out", "fainted", "loss of consciousness", "seizure",
        "stroke", "face drooping", "suicid", "kill myself", "overdose", "anaphyla",
        "throat closing", "choking",
    ],
    "th": [
        "เจ็บหน้าอก", "แน่นหน้าอก", "หายใจไม่ออก", "หายใจลำบาก", "เลือดออกมาก", "เลือดไม่หยุด",
        "หมดสติ", "เป็นลม", "ชัก", "ฆ่าตัวตาย", "กินยาเกินขนาด",
    ],
    "ko": [
        "가슴 통증", "흉통", "숨을 못", "호흡 곤란", "호흡곤란", "숨이 차", "출혈이 심", "피가 멈추지",
        "의식을 잃", "의식이 없", "실신", "기절", "경련", "발작", "자살",
    ],
}


def detect_emergency(text: str) -> str | None:
    """Return the matched term if text contains an emergency signal."""
    if not text:
        return None
    lowered = text.lower()
    for terms in EMERGENCY_TERMS.values():
        for term in terms:
            if term in lowered:
                return term
    return None


GLOSSARY_PATH = Path(__file__).with_name("glossary_ko.yaml")


@lru_cache(maxsize=1)
def glossary() -> list[dict]:
    data = yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8"))
    return data["terms"]


def glossary_ko_terms() -> set[str]:
    return {t["ko"] for t in glossary()}


def glossary_prompt_block() -> str:
    """Compact glossary for the cached prompt prefix."""
    return "\n".join(f"{t['en']} = {t['ko']}" for t in glossary())


def lookup_ko(english: str) -> str | None:
    e = english.strip().lower()
    for t in glossary():
        if t["en"].lower() == e or t["key"] == e:
            return t["ko"]
    return None


_HANGUL_WORD = re.compile(r"[가-힣]{2,}")
_RX_KNOWN_FILLER = {"복용", "하세요", "드세요", "주세요", "넣으세요", "바르세요", "투약", "처방", "회", "일", "분", "알"}


def unglossed_korean(text: str, allowed: set[str] | None = None) -> list[str]:
    """Korean words in text that are not glossary terms (used to flag, never to block)."""
    allowed = allowed or set()
    terms = glossary_ko_terms() | allowed
    found = []
    for w in _HANGUL_WORD.findall(text or ""):
        if any(w in t or t in w for t in terms) or w in _RX_KNOWN_FILLER:
            continue
        found.append(w)
    return sorted(set(found))
