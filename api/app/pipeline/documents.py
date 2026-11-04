"""Prescription label reader and insurance claim pack (P1).

Both read what is printed and nothing more: no judgement of a prescription,
no prediction of coverage (guardrails 7 and 8).
"""

from __future__ import annotations

import base64
import io
from datetime import date

from .. import fixed_text as fx
from ..providers.llm import LLMProvider
from ..safety import glossary, unglossed_korean
from ..schemas import CapturedDoc, ClaimPack, PrescriptionItem, PrescriptionReading
from .prompts import CORE_RULES, glossary_block, lang_name


def image_part(data: bytes, mime: str) -> dict:
    # VERIFY: Meta image input shape. This is the OpenAI chat-completions image_url form.
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


# ---------------- prescription ----------------

RX_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "drug_name_ko": {"type": "string"}, "dose": {"type": ["string", "null"]},
                "times_per_day": {"type": ["string", "null"]}, "days": {"type": ["string", "null"]},
                "instructions_ko": {"type": ["string", "null"]}, "gloss_patient_lang": {"type": "string"},
                "confidence": {"type": "number"}},
            "required": ["drug_name_ko", "dose", "times_per_day", "days", "instructions_ko",
                         "gloss_patient_lang", "confidence"]}},
        "untranslated_terms": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["items", "untranslated_terms"],
}


def rx_system(lang: str) -> str:
    return f"""{CORE_RULES}

TASK: Read a Korean prescription or medicine-bag label photo. Copy each printed medicine line exactly.
- drug_name_ko, dose, times_per_day, days, instructions_ko: copy the printed Korean text exactly; null if not printed.
- gloss_patient_lang: a plain {lang_name(lang)} translation of ONLY the printed text for that line.
  Never say whether it is correct, what it treats, or what the patient should take. No advice.
- confidence: 0..1 for how clearly you could read that line. Use a low value if blurry or cut off.
- untranslated_terms: printed words you could not translate with the glossary.

{glossary_block()}"""


async def read_prescription(data: bytes, mime: str, lang: str, provider: LLMProvider) -> PrescriptionReading:
    res = await provider.json(task="read_prescription", system=rx_system(lang),
                              user=[{"type": "text", "text": "Read this label."}, image_part(data, mime)],
                              schema=RX_SCHEMA, timeout_s=30, effort="low")
    notice = fx.patient_text("pharmacist", lang)
    if res.data is None:
        return PrescriptionReading(items=[], low_confidence=True,
                                   notice_patient_lang=f"{fx.patient_text('low_confidence', lang)} {notice}")
    items, flagged = [], set(str(t) for t in res.data.get("untranslated_terms") or [])
    for raw in res.data.get("items") or []:
        try:
            item = PrescriptionItem(**{k: raw.get(k) for k in PrescriptionItem.model_fields
                                       if k != "confirm_with_pharmacist"})
        except Exception:
            continue
        flagged |= set(unglossed_korean(item.instructions_ko or ""))
        items.append(item)
    low = not items or any(i.confidence < 0.7 for i in items)
    text = notice if not low else f"{fx.patient_text('low_confidence', lang)} {notice}"
    return PrescriptionReading(items=items, untranslated_terms=sorted(flagged), low_confidence=low,
                               notice_patient_lang=text)


# ---------------- insurance ----------------

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {"insurer_name": {"type": ["string", "null"]},
                   "required_docs": {"type": "array", "items": {"type": "string"}}},
    "required": ["insurer_name", "required_docs"],
}

CHECKLIST_SYSTEM = """You extract the list of documents an insurer asks for, from the insurer's own page or PDF.
List each required document as a short English noun phrase, exactly as the insurer asks (keep conditions such as
'card slips not accepted'). Do not add documents the text does not ask for. Do not judge coverage or eligibility.
Output JSON only."""

CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {"type": {"type": "string"}, "date": {"type": ["string", "null"]},
                   "amount": {"type": ["string", "null"]}, "disease_code": {"type": ["string", "null"]},
                   "confidence": {"type": "number"}},
    "required": ["type", "date", "amount", "disease_code", "confidence"],
}


def capture_system() -> str:
    names = "\n".join(f"- {t['en']} ({t['ko']})" for t in glossary() if t["kind"] == "doc")
    return f"""Identify a Korean clinic or pharmacy document photo and copy printed fields.
- type: one of these names if it matches, else a short English description (e.g. 'card payment slip'):
{names}
- date, amount, disease_code: copy exactly as printed; null if not printed. Do not infer.
- confidence: 0..1. Output JSON only."""


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)[:20000]


async def parse_checklist(provider: LLMProvider, *, text: str | None = None, data: bytes | None = None,
                          mime: str | None = None) -> tuple[str | None, list[str], str | None]:
    if data is not None and mime == "application/pdf":
        text = pdf_text(data)
        data = None
    user: object = f"INSURER TEXT:\n{text}" if data is None else [
        {"type": "text", "text": "Insurer checklist image:"}, image_part(data, mime or "image/png")]
    res = await provider.json(task="parse_checklist", system=CHECKLIST_SYSTEM, user=user,
                              schema=CHECKLIST_SCHEMA, timeout_s=30, effort="low")
    if res.data is None:
        return None, [], res.error
    return res.data.get("insurer_name"), [str(d) for d in res.data.get("required_docs") or []], None


async def capture_doc(data: bytes, mime: str, provider: LLMProvider) -> CapturedDoc:
    res = await provider.json(task="capture_doc", system=capture_system(),
                              user=[{"type": "text", "text": "Document photo:"}, image_part(data, mime)],
                              schema=CAPTURE_SCHEMA, timeout_s=30, effort="low")
    if res.data is None:
        return CapturedDoc(type="unreadable", confidence=0.0)
    try:
        return CapturedDoc(**res.data)
    except Exception:
        return CapturedDoc(type="unreadable", confidence=0.0)


# Synonyms map free-form names to a glossary key, so matching is deterministic.
_DOC_SYNONYMS: dict[str, list[str]] = {
    "itemized_statement": ["itemized", "detailed expense", "세부내역", "detailed statement", "breakdown"],
    "receipt": ["medical fee receipt", "treatment receipt", "진료비 영수증", "hospital receipt", "clinic receipt"],
    "pharmacy_receipt": ["pharmacy receipt", "약제비", "medicine receipt", "drug receipt"],
    "disease_code": ["disease code", "diagnosis code", "질병코드", "상병코드", "disease name"],
    "diagnosis_certificate": ["medical certificate", "진단서", "diagnosis certificate"],
    "medical_opinion": ["doctor's note", "소견서", "medical opinion"],
    "prescription_slip": ["prescription", "처방전"],
    "alien_registration": ["alien registration", "외국인등록", "arc", "residence card"],
    "bankbook_copy": ["bankbook", "통장", "bank account"],
    "claim_form": ["claim form", "청구서", "application form"],
    "passport": ["passport", "여권"],
}


def doc_key(name: str) -> str | None:
    n = name.lower()
    # a captured card payment slip is never a pharmacy receipt (some insurers reject them)
    if "slip" in n and "card" in n and not any(w in n for w in ("receipt", "영수증")):
        return "card_slip"
    # check longer synonyms first so "pharmacy receipt" wins over "receipt"
    pairs = sorted(((s, k) for k, ss in _DOC_SYNONYMS.items() for s in ss), key=lambda p: -len(p[0]))
    for s, k in pairs:
        if s in n:
            return k
    return None


def compute_missing(required: list[str], captured: list[CapturedDoc], have: list[str]) -> list[str]:
    got: set[str] = set()
    for c in captured:
        k = doc_key(c.type)
        if k:
            got.add(k)
        if c.disease_code:
            got.add("disease_code")
    for h in have:
        k = doc_key(h)
        got.add(k or h.lower())
    missing = []
    for r in required:
        # "A or B" is satisfied by either alternative
        alts = [r] + [a.strip() for a in r.split(" or ")] if " or " in r and "disease" not in r else [r]
        if any((doc_key(a) and doc_key(a) in got) or a.lower() in got for a in alts):
            continue
        missing.append(r)
    return missing


def draft_message(pack: ClaimPack) -> str:
    """Fixed template, not generated: lists documents only, makes no coverage claim."""
    lines = [f"Subject: Medical expense claim – {date.today().isoformat()}", "",
             f"Hello{(' ' + pack.insurer_name) if pack.insurer_name else ''},", "",
             "I would like to submit a claim for a clinic visit in Korea. Name: [your full name]. "
             "Policy number: [your policy number].", "",
             "Attached documents:"]
    for c in pack.captured:
        bits = [c.type] + [x for x in (c.date, c.amount, c.disease_code and f"code {c.disease_code}") if x]
        lines.append(f"- {' · '.join(bits)}")
    if pack.missing:
        lines += ["", "Still to send:"] + [f"- {m}" for m in pack.missing]
    lines += ["", "Please let me know if anything else is needed.", "", "Thank you."]
    return "\n".join(lines)


def build_pack(insurer: str | None, required: list[str], captured: list[CapturedDoc],
               have: list[str]) -> ClaimPack:
    pack = ClaimPack(insurer_name=insurer, required_docs=required, captured=captured,
                     missing=compute_missing(required, captured, have))
    pack.draft_message = draft_message(pack)  # the patient fills in identifiers; never sent by Medero
    return pack
