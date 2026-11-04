"""Deterministic stand-ins for model tasks, so the app and tests run with no API key.

These are NOT model results. Every string they produce is tagged [FAKE] so it can
never be mistaken for real output in the UI, eval or demo.
"""

from __future__ import annotations

import json
import re
from typing import Any

TAG = "[FAKE]"


def _json_after(label: str, text: str) -> Any:
    i = text.find(label)
    if i < 0:
        return None
    start = text.find("[", i) if text.find("[", i) >= 0 else text.find("{", i)
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except Exception:
        return None


def _clinician(user: Any) -> str:
    text = user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)
    m = re.search(r"CLINICIAN SAID \(Korean\): (.*)", text)
    return m.group(1).strip() if m else ""


def default_handler(task: str, system: str, user: Any) -> dict | None:
    if task == "route_turn":
        from ..pipeline.router import _FACT_CUES, _DECISION, _PROCEDURAL  # reuse baseline cues

        u = _clinician(user)
        ids = re.findall(r"^- (\S+):", user, flags=re.M) if isinstance(user, str) else []
        if any(k in u for k in _DECISION):
            return {"turn_class": "needs_decision", "fact_ids": [], "confidence": 0.5}
        hit = [i for fid, cues in _FACT_CUES.items() if any(c in u for c in cues)
               for i in ids if i == fid or (fid.endswith("_") and i.startswith(fid))]
        if hit:
            return {"turn_class": "on_card", "fact_ids": hit, "confidence": 0.5}
        if any(k in u for k in _PROCEDURAL):
            return {"turn_class": "procedural", "fact_ids": [], "confidence": 0.5}
        return {"turn_class": "needs_fact" if u else "unclear", "fact_ids": [], "confidence": 0.5}

    if task == "respond":
        facts = _json_after("APPROVED FACTS", system) or []
        u = _clinician(user)
        from ..pipeline.router import _FACT_CUES

        wanted = [f for f in facts if any(
            (f["id"] == fid or (fid.endswith("_") and f["id"].startswith(fid))) and any(c in u for c in cues)
            for fid, cues in _FACT_CUES.items())]
        if not wanted:
            return {"clinician_said_patient_lang": f"{TAG} {u}", "reply_ko": None, "reply_patient_lang": "",
                    "evidence": [], "confidence": 0.3}
        ko = ", ".join(f.get("value_ko") or f["value"] for f in wanted)
        return {"clinician_said_patient_lang": f"{TAG} The doctor asked: {u}",
                "reply_ko": f"{TAG} {ko}", "reply_patient_lang": f"{TAG} " + ", ".join(f["value"] for f in wanted),
                "evidence": [f["id"] for f in wanted], "confidence": 0.5}

    if task == "ask_back":
        u = _clinician(user)
        decision = "DECISION" in system
        return {"clinician_said_patient_lang": f"{TAG} The doctor said: {u}",
                "question_patient_lang": f"{TAG} The doctor is asking you: {u}",
                "options": ["Yes", "No", "I need more explanation"] if decision else ["I don't know"],
                "confidence": 0.5}

    if task == "gloss":
        return {"clinician_said_patient_lang": f"{TAG} The doctor said: {_clinician(user)}", "confidence": 0.5}

    if task == "relay":
        m = re.search(r"PATIENT ANSWERED: (.*)", user if isinstance(user, str) else "")
        ans = m.group(1).strip() if m else ""
        return {"reply_ko": f"{TAG} 환자 답변: {ans}", "reply_patient_lang": f"{TAG} {ans}",
                "fact_value_ko": f"{TAG} {ans}", "confidence": 0.5}

    if task == "verify_reply":
        return {"unsupported": False, "reason": f"{TAG} not checked"}

    if task == "card_ko":
        facts = _json_after("FACTS:", user if isinstance(user, str) else "") or []
        return {"facts": [{"id": f["id"], "value_ko": f"{TAG} {f['value']}", "untranslated_terms": []}
                          for f in facts]}

    if task == "read_prescription":
        return {"doc_kind": "prescription_form",
                "items": [{"drug_name_ko": f"{TAG} 약 이름", "dose": "1", "times_per_day": "3",
                           "days": "3", "instructions_ko": "식후30분", "substitution_ko": "불가",
                           "not_covered": False, "handwritten_note": None, "truncated": False,
                           "gloss_patient_lang": f"{TAG} Label text would be translated here.",
                           "confidence": 0.3}],
                "issued_date": "2026-10-31", "valid_days": "3", "disease_code": None,
                "disease_code_box": "blank", "untranslated_terms": []}

    if task == "parse_checklist":
        return {"insurer_name": f"{TAG} Mock insurer", "required_docs": [
            "claim form", "medical fee receipt", "itemized expense statement", "pharmacy receipt"]}

    if task == "capture_doc":
        return {"type": "medical fee receipt", "date": None, "amount": None, "disease_code": None,
                "confidence": 0.3}

    if task == "match_docs":
        return {"matches": []}

    if task == "claim_draft":
        return {"draft_message": f"{TAG} Draft claim message would be written here."}

    return None
