"""Intake answers -> CaseCard, approval, and one-time Korean rendering of approved facts."""

from __future__ import annotations

import json
import re

from ..providers.llm import LLMProvider
from ..safety import detect_emergency
from ..schemas import CaseCard, Fact, IntakeAnswers
from . import prompts

# Guardrail 10: identifiers never reach a model.
_ID_PATTERNS = [
    re.compile(r"\b\d{6}-?[1-8]\d{6}\b"),          # Korean resident / alien registration number shape
    re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),           # passport-like
    re.compile(r"\+?\d[\d\s-]{8,}\d"),              # phone-like
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),         # email
]


def scrub(text: str | None) -> str | None:
    if text is None:
        return None
    for p in _ID_PATTERNS:
        text = p.sub("[removed]", text)
    return text


def build_card(a: IntakeAnswers) -> CaseCard:
    def fact(fid: str, value: str | None) -> Fact:
        v = scrub(value.strip()) if value and value.strip() else None
        return Fact(id=fid, value=v, source="patient_stated", approved=False)

    symptoms = [fact("sym_onset", a.onset), fact("sym_duration", a.duration),
                fact("sym_site", a.site), fact("sym_severity", a.severity)]
    symptoms += [fact(f"sym_{i + 1}", s) for i, s in enumerate(x for x in a.other_symptoms if x.strip())]
    return CaseCard(
        patient_language=a.patient_language,
        alias=(scrub(a.alias) or "Patient")[:40],
        chief_complaint=fact("cc", a.chief_complaint),
        symptoms=symptoms,
        tried=[fact(f"tried_{i + 1}", t) for i, t in enumerate(x for x in a.tried if x.strip())],
        history=[fact(f"hx_{i + 1}", h) for i, h in enumerate(x for x in a.history if x.strip())],
        allergies=fact("allergy", a.allergies),
        medications=fact("meds", a.medications),
        insurance_type=a.insurance_type,
        may_answer=[],
    )


def intake_emergency(a: IntakeAnswers) -> str | None:
    blob = " ".join(filter(None, [a.chief_complaint, a.onset, a.duration, a.site, a.severity,
                                  *a.other_symptoms, *a.tried, *a.history]))
    return detect_emergency(blob)


def approve(card: CaseCard, approved_ids: list[str]) -> CaseCard:
    """Patient approves which known facts the agent may state. Unknown facts can never be approved."""
    chosen = set(approved_ids)
    for f in card.all_facts():
        f.approved = f.id in chosen and f.known
    card.may_answer = [f.id for f in card.all_facts() if f.approved]
    return card


async def render_korean(card: CaseCard, provider: LLMProvider) -> tuple[CaseCard, list[str], str | None]:
    """Fill value_ko for approved facts. Returns (card, untranslated_terms, error)."""
    facts = [{"id": f.id, "value": f.value} for f in card.all_facts() if f.approved and f.known]
    if not facts:
        return card, [], None
    res = await provider.json(task="card_ko", system=prompts.CARD_KO_SYSTEM,
                              user="FACTS:\n" + json.dumps(facts, ensure_ascii=False),
                              schema=prompts.CARD_KO_SCHEMA)
    if res.data is None:
        return card, [], res.error or "card_ko_failed"
    untranslated: list[str] = []
    for item in res.data.get("facts", []):
        f = card.fact(str(item.get("id")))
        if f and f.approved and item.get("value_ko"):
            f.value_ko = str(item["value_ko"])
            untranslated += [str(t) for t in item.get("untranslated_terms") or []]
    return card, sorted(set(untranslated)), None
