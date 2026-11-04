import json
from pathlib import Path

import pytest

from app import fixed_text as fx
from app.pipeline import intake
from app.pipeline.router import rules_route
from app.pipeline.verifier import check_rules, numbers_in_korean
from app.pipeline.visit import new_session
from app.providers.llm import FakeProvider
from app.safety import detect_emergency, unglossed_korean
from app.schemas import AskBack, IntakeAnswers, ReplyPlan

DEMO = json.loads((Path(__file__).resolve().parents[2] / "data/mock/demo_case.json").read_text())


def demo_card(approve_all=True):
    a = IntakeAnswers(**{k: v for k, v in DEMO.items() if not k.startswith("_")})
    card = intake.build_card(a)
    if approve_all:
        intake.approve(card, [f.id for f in card.all_facts()])
    return card


# ---------- intake / card ----------

def test_unknown_allergy_is_none_not_no():
    card = demo_card()
    assert card.allergies.value is None
    assert not card.allergies.approved, "unknown facts can never be approved"
    assert "allergy" not in card.may_answer


def test_blank_is_unknown():
    a = IntakeAnswers(chief_complaint="cough", allergies="   ", medications="")
    card = intake.build_card(a)
    assert card.allergies.value is None and card.medications.value is None


def test_identifiers_scrubbed():
    assert "[removed]" in intake.scrub("my number is 990101-5123456")
    assert "[removed]" in intake.scrub("call +82 10 1234 5678")


def test_intake_emergency():
    a = IntakeAnswers(chief_complaint="I have chest pain and trouble breathing")
    assert intake.intake_emergency(a)


# ---------- safety ----------

@pytest.mark.parametrize("text", ["가슴 통증이 있어요", "숨을 못 쉬겠어요", "หายใจไม่ออก", "she passed out"])
def test_emergency_detected(text):
    assert detect_emergency(text)


def test_no_false_emergency():
    assert detect_emergency("눈이 빨갛고 가려워요") is None


def test_unglossed_flags_unknown_terms():
    assert "결막염" in unglossed_korean("결막염 안약")
    assert unglossed_korean("진료비 세부내역서") == []


# ---------- router (rules baseline) ----------

@pytest.mark.parametrize("utt,cls", [
    ("언제부터 그랬어요?", "on_card"),
    ("알레르기 있으세요?", "needs_fact"),      # allergy unknown -> must ask
    ("안약 처방해 드릴까요?", "needs_decision"),
    ("여기 앉으세요.", "procedural"),
    ("음", "unclear"),
])
def test_rules_router(utt, cls):
    assert rules_route(utt, demo_card()).turn_class == cls


# ---------- verifier ----------

def test_verifier_blocks_missing_evidence():
    plan = ReplyPlan(turn_class="on_card", reply_ko="3일 전부터요.", evidence=[])
    assert not check_rules(plan, demo_card()).ok


def test_verifier_blocks_unknown_fact():
    plan = ReplyPlan(turn_class="on_card", reply_ko="알레르기 없어요.", evidence=["allergy"])
    v = check_rules(plan, demo_card())
    assert not v.ok and any("rule2" in r for r in v.reasons)


def test_verifier_blocks_unsupported_number():
    plan = ReplyPlan(turn_class="on_card", reply_ko="5일 됐어요.", evidence=["sym_duration"])
    v = check_rules(plan, demo_card())
    assert not v.ok and any("rule3" in r for r in v.reasons)


def test_verifier_allows_supported_number():
    plan = ReplyPlan(turn_class="on_card", reply_ko="사흘 됐어요.", evidence=["sym_duration"])
    assert check_rules(plan, demo_card()).ok


def test_verifier_rule4():
    ask = AskBack(question_patient_lang="?", kind="decision", options=[])
    bad = ReplyPlan(turn_class="needs_decision", reply_ko="네, 할게요.", ask_patient=ask)
    assert not check_rules(bad, demo_card()).ok
    good = ReplyPlan(turn_class="needs_decision", reply_ko=fx.HOLDING_PHRASE_KO, ask_patient=ask)
    assert check_rules(good, demo_card()).ok
    no_ask = ReplyPlan(turn_class="needs_fact", reply_ko=fx.HOLDING_PHRASE_KO)
    assert not check_rules(no_ask, demo_card()).ok


def test_korean_numbers():
    assert numbers_in_korean("일주일 전부터, 하루 세 번") == {"7", "1", "3"}
    assert numbers_in_korean("구분해 주세요") == set()


# ---------- visit flow (fake provider) ----------

async def _session():
    card = demo_card()
    sess = new_session(card, FakeProvider(), None)
    sess.set_consent(True)
    return sess


async def test_visit_requires_consent():
    sess = new_session(demo_card(), FakeProvider(), None)
    ev = await sess.clinician_turn("언제부터 그랬어요?")
    assert ev[0]["code"] == "consent_needed"


async def test_visit_on_card_reply_has_evidence():
    sess = await _session()
    ev = await sess.clinician_turn("언제부터 그랬어요?")
    res = [e for e in ev if e["type"] == "turn_result"][0]
    assert res["turn_class"] == "on_card"
    assert res["reply_ko"] and res["evidence"]
    assert set(res["latency_ms"]) >= {"route", "respond", "verify", "total"}


async def test_visit_unknown_allergy_asks_patient_then_relays():
    sess = await _session()
    ev = await sess.clinician_turn("알레르기 있으세요?")
    res = [e for e in ev if e["type"] == "turn_result"][0]
    assert res["turn_class"] == "needs_fact"
    assert res["reply_ko"] == fx.HOLDING_PHRASE_KO
    ask = res["ask_back"]
    assert ask and ask["kind"] == "fact"
    out = await sess.patient_answer(ask["id"], "I don't know")
    assert out[0]["type"] == "relay_result" and out[0]["reply_ko"]
    f = sess.card.fact(out[0]["fact_id"])
    assert f.source == "patient_confirmed_in_visit" and f.approved


async def test_visit_decision_goes_to_patient():
    sess = await _session()
    ev = await sess.clinician_turn("안약 처방해 드릴까요?")
    res = [e for e in ev if e["type"] == "turn_result"][0]
    assert res["turn_class"] == "needs_decision"
    assert res["ask_back"]["kind"] == "decision"
    assert res["reply_ko"] == fx.HOLDING_PHRASE_KO


async def test_visit_emergency_stops():
    sess = await _session()
    ev = await sess.clinician_turn("가슴 통증 있으세요? 숨을 못 쉬세요?")
    assert any(e["type"] == "emergency" for e in ev)
    ev2 = await sess.clinician_turn("언제부터요?")
    assert ev2[0]["type"] == "emergency"


async def test_responder_hallucination_is_blocked():
    def liar(task, system, user):
        if task == "respond":
            return {"clinician_said_patient_lang": "x", "reply_ko": "알레르기는 없고 5일 됐어요.",
                    "reply_patient_lang": "x", "evidence": ["sym_duration"], "confidence": 0.9}
        from app.providers.fake import default_handler
        return default_handler(task, system, user)

    sess = new_session(demo_card(), FakeProvider(handler=liar), None)
    sess.set_consent(True)
    ev = await sess.clinician_turn("며칠 됐어요?")
    res = [e for e in ev if e["type"] == "turn_result"][0]
    assert res["blocked"] and res["reply_ko"] == fx.HOLDING_PHRASE_KO and res["ask_back"]
    assert len(sess.blocked_log) == 1


async def test_model_failure_falls_back_to_patient():
    sess = new_session(demo_card(), FakeProvider(handler=lambda *a: None), None)
    sess.set_consent(True)
    ev = await sess.clinician_turn("언제부터 그랬어요?")
    assert any(e["type"] == "fallback" for e in ev)
    res = [e for e in ev if e["type"] == "turn_result"][0]
    assert res["ask_back"] and res["reply_ko"] == fx.HOLDING_PHRASE_KO


async def test_summary_only_doctor_speech():
    sess = await _session()
    await sess.clinician_turn("언제부터 그랬어요?")
    await sess.clinician_turn("여기 앉으세요.")
    s = sess.summary()
    ids = {t["id"] for t in s["record"]["turns"] if t["speaker"] == "clinician"}
    assert s["record"]["doctor_said"] and all(st["source_turn_id"] in ids for st in s["record"]["doctor_said"])


async def test_patient_say_relays_own_words_and_answers_open_question():
    sess = await _session()
    out = await sess.patient_say("My eyes hurt more at night")
    assert out[0]["type"] == "relay_result" and out[0]["patient_text"] == "My eyes hurt more at night"
    ev = await sess.clinician_turn("알레르기 있으세요?")
    assert sess.pending
    out = await sess.patient_say("I don't know")
    assert out[0]["type"] == "relay_result" and not sess.pending


async def test_patient_say_emergency():
    sess = await _session()
    out = await sess.patient_say("I can't breathe")
    assert out[0]["type"] == "emergency"


def test_is_korean():
    from app.main import is_korean
    assert is_korean("언제부터 그랬어요?") and not is_korean("I don't know") and not is_korean("ไม่ทราบค่ะ")


async def test_confirmed_fact_keeps_question():
    sess = await _session()
    ev = await sess.clinician_turn("알레르기 있으세요?")
    ask = [e for e in ev if e["type"] == "turn_result"][0]["ask_back"]
    out = await sess.patient_answer(ask["id"], "none")
    f = sess.card.fact(out[0]["fact_id"])
    assert f.answers_question == "알레르기 있으세요?"
