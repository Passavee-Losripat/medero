"""Visit orchestrator: one clinician turn in, a list of client events out.

Flow per turn (CLAUDE.md section 6): emergency check -> route -> respond / ask-back / gloss
-> verify -> events. Any model failure falls back to asking the patient.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .. import fixed_text as fx
from ..providers.llm import LLMProvider
from ..safety import detect_emergency
from ..schemas import AskBack, CaseCard, Fact, ReplyPlan, Statement, Turn, VisitRecord
from . import prompts
from .router import route
from .verifier import verify

Event = dict[str, Any]


@dataclass
class PendingAsk:
    id: str
    turn_id: str
    question_ko: str
    ask: AskBack


@dataclass
class VisitSession:
    id: str
    card: CaseCard
    spark: LLMProvider
    router: LLMProvider | None
    verifier_model: bool = True
    consent: bool | None = None
    emergency: str | None = None
    record: VisitRecord = field(default_factory=VisitRecord)
    pending: dict[str, PendingAsk] = field(default_factory=dict)
    blocked_log: list[dict] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)
    _n: int = 0

    # ---------- helpers ----------
    def _next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def _lang(self) -> str:
        return self.card.patient_language

    def _recent(self) -> list[str]:
        return [f"{t.speaker}: {t.korean_text}" for t in self.record.turns[-6:]]

    def _evidence(self, ids: list[str]) -> list[dict]:
        out = []
        for i in ids:
            f = self.card.fact(i)
            if f:
                out.append({"id": f.id, "value": f.value, "value_ko": f.value_ko,
                            "answers_question": f.answers_question})
        return out

    def approved_facts_ko(self) -> list[dict]:
        return [{"id": f.id, "value": f.value, "value_ko": f.value_ko} for f in self.card.speakable()]

    def _emergency_event(self, term: str, where: str) -> Event:
        self.emergency = term
        return {"type": "emergency", "where": where, "card": fx.EMERGENCY_CARD}

    # ---------- consent (guardrail 5) ----------
    def disclosure(self) -> Event:
        return {"type": "disclosure", "text_ko": fx.DISCLOSURE_KO}

    def set_consent(self, accepted: bool) -> Event:
        self.consent = accepted
        if accepted:
            return {"type": "consent", "accepted": True}
        return {"type": "consent", "accepted": False, "text_ko": fx.DECLINED_KO,
                "text_patient": fx.patient_text("declined", self._lang())}

    # ---------- clinician turn ----------
    async def clinician_turn(self, text_ko: str, *, uncertain: bool = False, asr_ms: float | None = None,
                             start_ms: int | None = None, end_ms: int | None = None) -> list[Event]:
        t_start = time.perf_counter()
        if self.emergency:
            return [{"type": "emergency", "where": "stopped", "card": fx.EMERGENCY_CARD}]
        if self.consent is not True:
            return [{"type": "error", "code": "consent_needed",
                     "text_patient": fx.patient_text("consent_needed", self._lang())}]
        turn = Turn(id=self._next_id("t"), speaker="clinician", korean_text=text_ko.strip(),
                    start_ms=start_ms, end_ms=end_ms, uncertain=uncertain)
        self.record.turns.append(turn)
        events: list[Event] = [{"type": "transcript", "turn_id": turn.id, "text_ko": turn.korean_text,
                                "final": True, "uncertain": uncertain}]
        if uncertain:
            events.append({"type": "notice", "text_patient": fx.patient_text("transcript_uncertain", self._lang())})

        term = detect_emergency(text_ko)
        if term:
            events.append(self._emergency_event(term, "visit"))
            return events

        r = await route(turn.korean_text, self.card, self.router)
        lat = {"transcribe": round(asr_ms, 1) if asr_ms is not None else None, "route": round(r.latency_ms, 1)}
        spark_calls = 1 if r.api_call else 0

        plan, gloss, err, respond_ms = await self._plan_for(r.turn_class, r.fact_ids, turn)
        spark_calls += 1
        lat["respond"] = round(respond_ms, 1)

        if plan is None:  # model failure -> ask the patient, show approved facts in Korean
            events.append({"type": "fallback", "reason": err, "note_ko": fx.FALLBACK_NOTE_KO,
                           "text_patient": fx.patient_text("model_timeout", self._lang()),
                           "facts": self.approved_facts_ko()})
            plan = self._generic_askback("needs_fact")

        blocked = None
        t_v = time.perf_counter()
        v = await verify(plan, self.card, self.spark if self.verifier_model else None)
        lat["verify"] = round(v.latency_ms if v.model_checked else (time.perf_counter() - t_v) * 1000, 1)
        if v.model_checked:
            spark_calls += 1
        if not v.ok:
            blocked = {"reasons": v.reasons, "attempted_reply_ko": plan.reply_ko, "evidence": plan.evidence}
            self.blocked_log.append({"turn_id": turn.id, "class": plan.turn_class, **blocked})
            plan = self._blocked_to_askback(plan, gloss)

        if gloss:
            turn.patient_lang_text = gloss
            self.record.doctor_said.append(Statement(text_patient_lang=gloss, source_turn_id=turn.id))
        if plan.reply_ko:
            self.record.turns.append(Turn(id=self._next_id("a"), speaker="agent", korean_text=plan.reply_ko,
                                          patient_lang_text=plan.reply_patient_lang))

        ask_event = None
        if plan.ask_patient:
            pa = PendingAsk(id=self._next_id("q"), turn_id=turn.id, question_ko=turn.korean_text,
                            ask=plan.ask_patient)
            self.pending[pa.id] = pa
            ask_event = {"id": pa.id, **plan.ask_patient.model_dump()}

        lat["total"] = round((time.perf_counter() - t_start) * 1000 + (asr_ms or 0), 1)
        self.metrics.append({"turn_id": turn.id, "class": plan.turn_class, "router": r.provider,
                             "spark_calls": spark_calls, "blocked": blocked is not None, **lat})
        events.append({
            "type": "turn_result", "turn_id": turn.id, "turn_class": plan.turn_class,
            "router": r.provider, "router_confidence": r.confidence,
            "clinician_said_patient_lang": gloss, "reply_ko": plan.reply_ko,
            "reply_patient_lang": plan.reply_patient_lang, "evidence": self._evidence(plan.evidence),
            "ask_back": ask_event, "blocked": blocked, "confidence": plan.confidence,
            "latency_ms": lat, "spark_calls": spark_calls,
        })
        return events

    async def _plan_for(self, cls: str, fact_ids: list[str], turn: Turn
                        ) -> tuple[ReplyPlan | None, str, str | None, float]:
        card, user = self.card, prompts.turn_user(turn.korean_text, self._recent()[:-1])
        if cls == "on_card":
            res = await self.spark.json(task="respond", system=prompts.respond_system(card), user=user,
                                        schema=prompts.RESPOND_SCHEMA)
            if res.data is None:
                return None, "", res.error, res.latency_ms
            d = res.data
            try:
                plan = ReplyPlan(turn_class="on_card", reply_ko=d.get("reply_ko") or None,
                                 reply_patient_lang=str(d.get("reply_patient_lang") or ""),
                                 evidence=[str(x) for x in d.get("evidence") or []],
                                 confidence=_conf(d.get("confidence")))
            except Exception as e:
                return None, "", f"schema:{e}"[:200], res.latency_ms
            if plan.reply_ko is None:  # model could not answer from the facts -> ask the patient
                plan = self._generic_askback("needs_fact", str(d.get("clinician_said_patient_lang") or ""))
            return plan, str(d.get("clinician_said_patient_lang") or ""), None, res.latency_ms

        if cls in ("needs_fact", "needs_decision"):
            kind = "decision" if cls == "needs_decision" else "fact"
            res = await self.spark.json(task="ask_back", system=prompts.askback_system(card, kind), user=user,
                                        schema=prompts.ASKBACK_SCHEMA)
            if res.data is None:
                return None, "", res.error, res.latency_ms
            d = res.data
            ask = AskBack(question_patient_lang=str(d.get("question_patient_lang") or
                                                    fx.patient_text("doctor_asked_generic", self._lang())),
                          kind=kind, options=[str(o) for o in (d.get("options") or [])][:4])
            plan = ReplyPlan(turn_class=cls, reply_ko=fx.HOLDING_PHRASE_KO,
                             reply_patient_lang=fx.patient_text("holding", self._lang()),
                             ask_patient=ask, confidence=_conf(d.get("confidence")))
            return plan, str(d.get("clinician_said_patient_lang") or ""), None, res.latency_ms

        # procedural / unclear: gloss only
        res = await self.spark.json(task="gloss", system=prompts.gloss_system(card), user=user,
                                    schema=prompts.GLOSS_SCHEMA)
        gloss = str((res.data or {}).get("clinician_said_patient_lang") or "")
        if cls == "unclear":
            plan = ReplyPlan(turn_class="unclear", reply_ko=fx.REPEAT_KO,
                             reply_patient_lang=fx.patient_text("repeat_requested", self._lang()),
                             confidence=_conf((res.data or {}).get("confidence")))
        else:
            plan = ReplyPlan(turn_class="procedural", reply_ko=None, reply_patient_lang="",
                             confidence=_conf((res.data or {}).get("confidence")))
        if res.data is None:
            return plan, "", None, res.latency_ms  # gloss failure is not fatal; no reply is made
        return plan, gloss, None, res.latency_ms

    def _generic_askback(self, cls: str, question: str = "") -> ReplyPlan:
        kind = "decision" if cls == "needs_decision" else "fact"
        return ReplyPlan(
            turn_class=cls if cls in ("needs_fact", "needs_decision") else "needs_fact",
            reply_ko=fx.HOLDING_PHRASE_KO, reply_patient_lang=fx.patient_text("holding", self._lang()),
            ask_patient=AskBack(question_patient_lang=question or fx.patient_text("doctor_asked_generic", self._lang()),
                                kind=kind, options=[]),
            confidence=0.0)

    def _blocked_to_askback(self, plan: ReplyPlan, gloss: str) -> ReplyPlan:
        cls = plan.turn_class if plan.turn_class in ("needs_fact", "needs_decision") else "needs_fact"
        if plan.ask_patient:
            return ReplyPlan(turn_class=cls, reply_ko=fx.HOLDING_PHRASE_KO,
                             reply_patient_lang=fx.patient_text("holding", self._lang()),
                             ask_patient=plan.ask_patient, confidence=0.0)
        return self._generic_askback(cls, gloss)

    # ---------- patient answers an ask-back ----------
    async def patient_answer(self, ask_id: str, answer: str) -> list[Event]:
        if self.emergency:
            return [{"type": "emergency", "where": "stopped", "card": fx.EMERGENCY_CARD}]
        pa = self.pending.pop(ask_id, None)
        if pa is None:
            return [{"type": "error", "code": "unknown_ask_id"}]
        return await self._relay(answer, pa.question_ko, pa.ask.question_patient_lang, ask_id, pa.turn_id)

    async def patient_say(self, text: str, asr_ms: float | None = None) -> list[Event]:
        """Patient speaks freely (hands-free). Answers the latest open question if there is one,
        otherwise relays the patient's own words to the clinician. Nothing is added to them."""
        if self.emergency:
            return [{"type": "emergency", "where": "stopped", "card": fx.EMERGENCY_CARD}]
        if self.consent is not True:
            return [{"type": "error", "code": "consent_needed",
                     "text_patient": fx.patient_text("consent_needed", self._lang())}]
        if self.pending:
            ask_id = list(self.pending)[-1]
            pa = self.pending.pop(ask_id)
            return await self._relay(text, pa.question_ko, pa.ask.question_patient_lang, ask_id, pa.turn_id,
                                     asr_ms=asr_ms)
        last_ko = next((t.korean_text for t in reversed(self.record.turns) if t.speaker == "clinician"), "")
        return await self._relay(text, last_ko, "", None, None, asr_ms=asr_ms)

    async def _relay(self, answer: str, question_ko: str, question_patient: str, ask_id: str | None,
                     turn_id: str | None, asr_ms: float | None = None) -> list[Event]:
        term = detect_emergency(answer)
        if term:
            return [self._emergency_event(term, "patient_answer")]
        t0 = time.perf_counter()
        fid = self._next_id("conf_")
        fact = Fact(id=fid, value=answer.strip(), source="patient_confirmed_in_visit", approved=True,
                    answers_question=(question_ko or question_patient or None))
        self.card.history.append(fact)  # stored with the card so later turns can cite it
        self.card.may_answer.append(fid)
        self.record.turns.append(Turn(id=self._next_id("p"), speaker="patient", korean_text="",
                                      patient_lang_text=answer.strip()))

        res = await self.spark.json(task="relay", system=prompts.relay_system(self.card),
                                    user=prompts.relay_user(question_ko, question_patient, answer),
                                    schema=prompts.RELAY_SCHEMA)
        reply_ko, reply_pl, blocked = None, "", None
        if res.data is not None:
            fact.value_ko = str(res.data.get("fact_value_ko") or "") or None
            plan = ReplyPlan(turn_class="on_card", reply_ko=str(res.data.get("reply_ko") or "") or None,
                             reply_patient_lang=str(res.data.get("reply_patient_lang") or ""),
                             evidence=[fid], confidence=_conf(res.data.get("confidence")))
            v = await verify(plan, self.card, self.spark if self.verifier_model else None)
            if v.ok:
                reply_ko, reply_pl = plan.reply_ko, plan.reply_patient_lang
            else:
                blocked = {"reasons": v.reasons, "attempted_reply_ko": plan.reply_ko, "evidence": [fid]}
                self.blocked_log.append({"turn_id": turn_id, "class": "relay", **blocked})
        if reply_ko is None:
            # Show the patient's own words to staff rather than an unverified translation.
            fact.value_ko = None
            reply_ko = f"{fx.PATIENT_SAYS_KO} {answer.strip()}"
            reply_pl = answer.strip()
        self.record.turns.append(Turn(id=self._next_id("a"), speaker="agent", korean_text=reply_ko,
                                      patient_lang_text=reply_pl))
        return [{"type": "relay_result", "ask_id": ask_id, "fact_id": fid, "reply_ko": reply_ko,
                 "reply_patient_lang": reply_pl, "blocked": blocked, "error": res.error,
                 "patient_text": answer.strip(),
                 "latency_ms": {"transcribe": round(asr_ms, 1) if asr_ms is not None else None,
                                "respond": round(res.latency_ms, 1),
                                "total": round((time.perf_counter() - t0) * 1000, 1)}}]

    # ---------- summary ----------
    def summary(self) -> Event:
        return {"type": "summary", "record": self.record.model_dump(),
                "notice_patient": fx.patient_text("summary_notice", self._lang()),
                "blocked_count": len(self.blocked_log), "metrics": self.metrics}


def _conf(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def new_session(card: CaseCard, spark: LLMProvider, router: LLMProvider | None, verifier_model: bool = True
                ) -> VisitSession:
    return VisitSession(id=uuid.uuid4().hex[:12], card=card, spark=spark, router=router,
                        verifier_model=verifier_model)
