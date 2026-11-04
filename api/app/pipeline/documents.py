"""Prescription label reader and insurance claim pack (P1).

Both read what is printed and nothing more: no judgement of a prescription,
no prediction of coverage (guardrails 7 and 8).
"""

from __future__ import annotations

import base64
import io
import re
from datetime import date

from .. import fixed_text as fx
from ..providers.llm import LLMProvider
from ..safety import glossary, unglossed_korean
from ..schemas import CapturedDoc, ClaimPack, PrescriptionItem, PrescriptionReading
from .intake import scrub
from .prompts import CORE_RULES, glossary_block, lang_name

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def image_part(data: bytes, mime: str) -> dict:
    # VERIFY: Meta image input shape. This is the OpenAI chat-completions image_url form.
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


# ---------------- prescription ----------------

RX_ITEM_FIELDS = ["drug_name_ko", "dose", "times_per_day", "days", "instructions_ko", "substitution_ko",
                  "not_covered", "handwritten_note", "truncated", "gloss_patient_lang", "confidence"]
_S, _SN = {"type": "string"}, {"type": ["string", "null"]}
RX_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_kind": {"type": "string", "enum": ["prescription_form", "medicine_bag", "other"]},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "drug_name_ko": _S, "dose": _SN, "times_per_day": _SN, "days": _SN, "instructions_ko": _SN,
                "substitution_ko": _SN, "not_covered": {"type": "boolean"}, "handwritten_note": _SN,
                "truncated": {"type": "boolean"}, "gloss_patient_lang": _S, "confidence": {"type": "number"}},
            "required": RX_ITEM_FIELDS}},
        "issued_date": _SN,
        "valid_days": _SN,
        "disease_code": _SN,
        "disease_code_box": {"type": "string", "enum": ["filled", "blank", "not_found"]},
        "untranslated_terms": {"type": "array", "items": _S},
    },
    "required": ["doc_kind", "items", "issued_date", "valid_days", "disease_code", "disease_code_box",
                 "untranslated_terms"],
}


def rx_system(lang: str) -> str:
    return f"""{CORE_RULES}

TASK: Read a photo of a Korean clinic prescription form (처방전) or a pharmacy medicine-bag label (약봉투).
Copy what is printed. Never guess text you cannot see.
- doc_kind: prescription_form for the clinic form with a medicine table; medicine_bag for a pharmacy label.
- items: one per medicine line. Copy the printed Korean exactly; null if not printed.
  On a prescription_form the columns are 1회 투약량 -> dose, 1일 투여횟수 -> times_per_day,
  총 투약일수 -> days, 대체가능 -> substitution_ko, 용법 -> instructions_ko. Copy bare numbers as printed.
  drug_name_ko: the name without a leading "(비급여)"; set not_covered=true if "(비급여)" is printed on the line.
  truncated=true if the name is visibly cut off by the column. handwritten_note: any pen note for that line, else null.
- gloss_patient_lang: a plain {lang_name(lang)} translation of ONLY the printed text for that line.
  Never say whether it is correct, what it treats, or what the patient should take. No advice.
- confidence: 0..1 for how clearly you could read that line. Low if blurry, cut off or handwritten.
- issued_date: 교부일자 as YYYY-MM-DD, else null. valid_days: the number in 사용기간 교부일로부터 (N)일간, else null.
- disease_code: the 질병분류기호 exactly as printed, else null. disease_code_box: filled / blank / not_found.
- NEVER output the patient's name, resident registration number, insurance number, or the doctor's name.
- untranslated_terms: printed words you could not translate with the glossary.

{glossary_block()}"""


def _item_flags(item: PrescriptionItem, lang: str) -> list[str]:
    t = lambda k: fx.patient_text(k, lang)  # noqa: E731
    flags = []
    if item.not_covered:
        flags.append(t("rx_not_covered"))
    if (item.substitution_ko or "").replace(" ", "") == "불가":
        flags.append(t("rx_no_sub"))
    if item.handwritten_note:
        flags.append(t("rx_handwritten").format(note=item.handwritten_note))
    if item.truncated:
        flags.append(t("rx_truncated"))
    return flags


async def read_prescription(data: bytes, mime: str, lang: str, provider: LLMProvider) -> PrescriptionReading:
    res = await provider.json(task="read_prescription", system=rx_system(lang),
                              user=[{"type": "text", "text": "Read this document."}, image_part(data, mime)],
                              schema=RX_SCHEMA, timeout_s=30)
    notice = fx.patient_text("pharmacist", lang)
    if res.data is None:
        return PrescriptionReading(items=[], low_confidence=True,
                                   notice_patient_lang=f"{fx.patient_text('low_confidence', lang)} {notice}")
    d = res.data
    items, flagged = [], set(str(t) for t in d.get("untranslated_terms") or [])
    for raw in d.get("items") or []:
        try:
            item = PrescriptionItem(**{k: raw.get(k) for k in RX_ITEM_FIELDS if raw.get(k) is not None})
        except Exception:
            continue
        # guardrail 10: identifiers never reach the screen even if the model copies them
        item.gloss_patient_lang = scrub(item.gloss_patient_lang) or ""
        item.handwritten_note = scrub(item.handwritten_note)
        if item.handwritten_note or item.truncated:
            item.confidence = min(item.confidence, 0.6)
        item.flags_patient_lang = _item_flags(item, lang)
        flagged |= set(unglossed_korean(item.instructions_ko or ""))
        items.append(item)
    kind = d.get("doc_kind") if d.get("doc_kind") in ("prescription_form", "medicine_bag") else "other"
    valid = str(d.get("valid_days") or "").strip()
    valid = valid if valid.isdigit() else None
    issued = d.get("issued_date") if _DATE.fullmatch(str(d.get("issued_date") or "")) else None
    code = (str(d.get("disease_code") or "").strip() or None)
    box = d.get("disease_code_box")
    blank = None if box == "not_found" else (box == "blank" and not code)

    notes, request = [], None
    if kind == "prescription_form":
        t = lambda k: fx.patient_text(k, lang)  # noqa: E731
        if valid:
            notes.append(t("rx_valid").format(days=valid, date=f" ({issued})" if issued else ""))
        notes.append(t("rx_keeps"))
        if code:
            notes.append(t("rx_code").format(code=code))
        elif blank:
            notes.append(t("rx_no_code"))
            request = fx.DISEASE_CODE_REQUEST_KO
    low = not items or any(i.confidence < 0.7 for i in items)
    text = notice if not low else f"{fx.patient_text('low_confidence', lang)} {notice}"
    return PrescriptionReading(doc_kind=kind, items=items, untranslated_terms=sorted(flagged), low_confidence=low,
                               notice_patient_lang=text, issued_date=issued, valid_days=valid, disease_code=code,
                               disease_code_blank=blank, notes_patient_lang=notes, request_ko=request)


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
                              schema=CHECKLIST_SCHEMA, timeout_s=30)
    if res.data is None:
        return None, [], res.error
    return res.data.get("insurer_name"), [str(d) for d in res.data.get("required_docs") or []], None


async def capture_doc(data: bytes, mime: str, provider: LLMProvider) -> CapturedDoc:
    res = await provider.json(task="capture_doc", system=capture_system(),
                              user=[{"type": "text", "text": "Document photo:"}, image_part(data, mime)],
                              schema=CAPTURE_SCHEMA, timeout_s=30)
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
