"""System prompts and JSON schemas for every model task.

Static text comes first so the provider can cache the prefix (system rules,
glossary, schema, then the case card). Per-turn data goes in the user message.
"""

from __future__ import annotations

import json

from ..schemas import CaseCard
from ..safety import glossary_prompt_block

LANG_NAMES = {"en": "English", "th": "Thai", "vi": "Vietnamese", "zh": "Chinese", "ja": "Japanese",
              "id": "Indonesian", "my": "Burmese", "ne": "Nepali", "uz": "Uzbek", "mn": "Mongolian"}


def lang_name(code: str) -> str:
    return LANG_NAMES.get(code.split("-")[0], code)


CORE_RULES = """You are part of Medero, a communication aid for a patient who does not speak Korean,
during a visit to a Korean clinic. You are NOT a clinician.
Hard rules:
- Never diagnose, name a likely condition, or suggest treatment, medicine or dosage.
- Never decide for the patient. Consent, procedures, medicine choices, payment and any yes/no
  that commits the patient must go back to the patient.
- State only facts from the APPROVED FACTS list. If no approved fact supports a statement, do not say it.
- An unknown fact is not "no". Never say "none" for something not provided.
- Korean medical terms must come from the GLOSSARY. If a needed term is missing, keep the patient's
  own words and do not invent a Korean term.
- Use polite, short Korean (해요체/합쇼체) suitable for clinic staff.
- Output only JSON matching the schema."""


def glossary_block() -> str:
    return "GLOSSARY (English = Korean):\n" + glossary_prompt_block()


def card_block(card: CaseCard) -> str:
    facts = []
    for f in card.speakable():
        facts.append({"id": f.id, "value": f.value, "value_ko": f.value_ko})
    unknown = [f.id for f in card.all_facts() if not f.known]
    not_approved = [f.id for f in card.all_facts() if f.known and f not in card.speakable()]
    return (
        f"PATIENT ALIAS: {card.alias}\nPATIENT LANGUAGE: {lang_name(card.patient_language)}\n"
        f"INSURANCE TYPE: {card.insurance_type}\n"
        f"APPROVED FACTS (the only facts you may state):\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n"
        f"UNKNOWN FACTS (must be asked, never answered): {unknown}\n"
        f"NOT APPROVED (never state): {not_approved}\n"
        f"ALWAYS ASK THE PATIENT ABOUT: {card.must_ask}"
    )


# ---------------- router ----------------

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "turn_class": {"type": "string", "enum": ["on_card", "needs_fact", "needs_decision", "unclear", "procedural"]},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["turn_class", "fact_ids", "confidence"],
}

ROUTER_SYSTEM = """Classify one thing a Korean clinician said to a patient. Output JSON only.
Classes:
- on_card: asks for information that one of the listed AVAILABLE FACT IDS answers.
- needs_fact: asks for patient information that no available fact answers (including anything unknown).
- needs_decision: asks the patient to choose, consent, agree to a procedure/test/medicine, or pay.
- procedural: an instruction or logistics with no question needing an answer (sit here, look up, wait, go to the pharmacy).
- unclear: garbled, incomplete or ambiguous speech.
Put the fact ids that answer the question in fact_ids (only for on_card). confidence is 0..1."""


def router_user(utterance_ko: str, fact_ids: list[str], fact_hints: dict[str, str]) -> str:
    hints = "\n".join(f"- {fid}: {fact_hints.get(fid, '')}" for fid in fact_ids)
    return f"AVAILABLE FACT IDS:\n{hints or '(none)'}\n\nCLINICIAN SAID (Korean): {utterance_ko}"


# ---------------- responder (on_card) ----------------

RESPOND_SCHEMA = {
    "type": "object",
    "properties": {
        "clinician_said_patient_lang": {"type": "string"},
        "reply_ko": {"type": ["string", "null"]},
        "reply_patient_lang": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["clinician_said_patient_lang", "reply_ko", "reply_patient_lang", "evidence", "confidence"],
}


def respond_system(card: CaseCard) -> str:
    lang = lang_name(card.patient_language)
    return f"""{CORE_RULES}

TASK: The clinician asked something the approved facts answer. Write the Korean reply for the clinician.
- reply_ko: short Korean answer stating only the cited facts. Prefer each fact's value_ko wording.
  Copy numbers, dates and durations exactly from the facts. If the facts do not fully answer, set reply_ko to null.
- evidence: the ids of every fact used. Must not be empty when reply_ko is set.
- reply_patient_lang: what you are telling the clinician, in plain {lang}.
- clinician_said_patient_lang: a faithful plain {lang} rendering of what the clinician said. Do not add advice.
- confidence: 0..1.

{glossary_block()}

{card_block(card)}"""


def turn_user(utterance_ko: str, recent: list[str]) -> str:
    ctx = "\n".join(recent[-6:]) or "(start of visit)"
    return f"RECENT TURNS:\n{ctx}\n\nCLINICIAN SAID (Korean): {utterance_ko}"


# ---------------- ask-back (needs_fact / needs_decision) and gloss (procedural / unclear) -------------

ASKBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "clinician_said_patient_lang": {"type": "string"},
        "question_patient_lang": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["clinician_said_patient_lang", "question_patient_lang", "options", "confidence"],
}


def askback_system(card: CaseCard, kind: str) -> str:
    lang = lang_name(card.patient_language)
    extra = ("This is a DECISION: present the choices neutrally. Never recommend one. "
             "Include an option meaning 'I need more explanation'."
             if kind == "decision" else
             "This asks for INFORMATION the patient has not approved or provided. "
             "Options may include 'I don't know'. Never pre-fill an answer.")
    return f"""{CORE_RULES}

TASK: The clinician asked something only the patient can answer. Write the question for the patient.
- clinician_said_patient_lang: a faithful plain {lang} rendering of what the clinician said.
- question_patient_lang: a short {lang} question to the patient.
- options: 2-4 short {lang} quick replies taken from what the clinician offered (free text is always allowed).
{extra}

{card_block(card)}"""


GLOSS_SCHEMA = {
    "type": "object",
    "properties": {"clinician_said_patient_lang": {"type": "string"}, "confidence": {"type": "number"}},
    "required": ["clinician_said_patient_lang", "confidence"],
}


def gloss_system(card: CaseCard) -> str:
    lang = lang_name(card.patient_language)
    return f"""{CORE_RULES}

TASK: Render what the clinician said into plain {lang} for the patient. Faithful, short, no added advice,
no explanation of medical meaning beyond what was said. If it is unintelligible, say so plainly.

{glossary_block()}"""


# ---------------- relay a patient's answer ----------------

RELAY_SCHEMA = {
    "type": "object",
    "properties": {
        "reply_ko": {"type": "string"},
        "reply_patient_lang": {"type": "string"},
        "fact_value_ko": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["reply_ko", "reply_patient_lang", "fact_value_ko", "confidence"],
}


def relay_system(card: CaseCard) -> str:
    lang = lang_name(card.patient_language)
    return f"""{CORE_RULES}

TASK: The patient just answered the clinician's question in {lang}. Relay exactly that answer in Korean.
- reply_ko: short polite Korean stating the patient's answer and nothing else. Copy numbers exactly.
- fact_value_ko: the answer itself in Korean (no framing).
- reply_patient_lang: what you are telling the clinician, in plain {lang}.
If the answer is a decision, relay the decision exactly; do not soften or strengthen it.

{glossary_block()}"""


def relay_user(question_ko: str, question_patient: str, answer: str) -> str:
    return (f"CLINICIAN ASKED (Korean): {question_ko}\nQUESTION SHOWN TO PATIENT: {question_patient}\n"
            f"PATIENT ANSWERED: {answer}")


# ---------------- verifier model check ----------------

CHECK_SCHEMA = {
    "type": "object",
    "properties": {"unsupported": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["unsupported", "reason"],
}

CHECK_SYSTEM = """You audit a Korean sentence said on behalf of a patient.
Set unsupported=true if the sentence asserts ANY information about the patient that is not stated in the
EVIDENCE facts (extra symptoms, numbers, negations such as 'no allergies', opinions, decisions, advice).
Paraphrase and polite framing are fine. Output JSON only."""


def check_user(reply_ko: str, evidence: list[dict]) -> str:
    return f"EVIDENCE:\n{json.dumps(evidence, ensure_ascii=False)}\n\nSENTENCE (Korean): {reply_ko}"


# ---------------- case card translation ----------------

CARD_KO_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "value_ko": {"type": "string"},
                           "untranslated_terms": {"type": "array", "items": {"type": "string"}}},
            "required": ["id", "value_ko", "untranslated_terms"]}},
    },
    "required": ["facts"],
}

CARD_KO_SYSTEM = f"""{CORE_RULES}

TASK: Render each patient-stated fact into short Korean for clinic staff. Keep meaning exactly; do not
interpret, summarise into a condition, or add anything. Copy numbers exactly. Use GLOSSARY terms for medical
words. If a medical word has no glossary entry, keep the original word in the Korean text and list it in
untranslated_terms.

{glossary_block()}"""
