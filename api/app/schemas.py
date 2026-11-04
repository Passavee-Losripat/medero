"""Data contracts for Medero (CLAUDE.md section 5).

Every model output is parsed into one of these. If parsing fails, the caller
falls back to asking the patient.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FactSource = Literal["patient_stated", "patient_confirmed_in_visit"]
InsuranceType = Literal["nhis", "school_group", "travel", "private", "none", "unknown"]
MustAsk = Literal["new_fact", "decision", "consent", "payment"]
TurnClass = Literal["on_card", "needs_fact", "needs_decision", "unclear", "procedural"]
TURN_CLASSES: tuple[str, ...] = ("on_card", "needs_fact", "needs_decision", "unclear", "procedural")

# Words that must never stand in for an unknown value (guardrail 4).
_NONE_WORDS = {"none", "no", "nothing", "n/a", "na", "nil", "없음", "없어요", "-"}


class Fact(BaseModel):
    id: str
    value: str | None = None  # None = unknown, never "none"
    source: FactSource = "patient_stated"
    approved: bool = False
    # Korean rendering made once at card approval (glossary terms only); used for the
    # fallback screen and as the only Korean the responder may build on. See docs/decisions.md.
    value_ko: str | None = None

    @property
    def known(self) -> bool:
        return self.value is not None and self.value.strip() != ""


class CaseCard(BaseModel):
    patient_language: str
    alias: str
    chief_complaint: Fact
    symptoms: list[Fact] = Field(default_factory=list)
    tried: list[Fact] = Field(default_factory=list)
    history: list[Fact] = Field(default_factory=list)
    allergies: Fact
    medications: Fact
    insurance_type: InsuranceType = "unknown"
    may_answer: list[str] = Field(default_factory=list)
    must_ask: list[MustAsk] = Field(default_factory=lambda: ["new_fact", "decision", "consent", "payment"])

    def all_facts(self) -> list[Fact]:
        return [self.chief_complaint, *self.symptoms, *self.tried, *self.history, self.allergies, self.medications]

    def fact(self, fact_id: str) -> Fact | None:
        for f in self.all_facts():
            if f.id == fact_id:
                return f
        return None

    def speakable(self) -> list[Fact]:
        """Facts the agent may state: approved, known, and listed in may_answer."""
        allowed = set(self.may_answer)
        return [f for f in self.all_facts() if f.approved and f.known and f.id in allowed]

    @model_validator(mode="after")
    def _check_ids(self) -> "CaseCard":
        ids = [f.id for f in self.all_facts()]
        if len(ids) != len(set(ids)):
            raise ValueError("fact ids must be unique")
        unknown = set(self.may_answer) - set(ids)
        if unknown:
            raise ValueError(f"may_answer lists unknown fact ids: {sorted(unknown)}")
        return self


class AskBack(BaseModel):
    question_patient_lang: str
    kind: Literal["fact", "decision"]
    options: list[str] = Field(default_factory=list)


class ReplyPlan(BaseModel):
    turn_class: TurnClass
    reply_ko: str | None = None
    reply_patient_lang: str = ""
    evidence: list[str] = Field(default_factory=list)
    ask_patient: AskBack | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Turn(BaseModel):
    id: str
    speaker: Literal["clinician", "agent", "patient"]
    korean_text: str
    patient_lang_text: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    uncertain: bool = False


class Statement(BaseModel):
    text_patient_lang: str
    source_turn_id: str


class VisitRecord(BaseModel):
    turns: list[Turn] = Field(default_factory=list)
    doctor_said: list[Statement] = Field(default_factory=list)
    patient_confirmed: bool = False


class PrescriptionItem(BaseModel):
    drug_name_ko: str
    dose: str | None = None
    times_per_day: str | None = None
    days: str | None = None
    instructions_ko: str | None = None
    gloss_patient_lang: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confirm_with_pharmacist: Literal[True] = True


class PrescriptionReading(BaseModel):
    items: list[PrescriptionItem] = Field(default_factory=list)
    untranslated_terms: list[str] = Field(default_factory=list)
    low_confidence: bool = False
    notice_patient_lang: str = ""


class CapturedDoc(BaseModel):
    type: str
    date: str | None = None
    amount: str | None = None
    disease_code: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ClaimPack(BaseModel):
    insurer_name: str | None = None
    required_docs: list[str] = Field(default_factory=list)
    captured: list[CapturedDoc] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    draft_message: str = ""


# ---- Intake input (what the patient types; turned into a CaseCard) ----


class IntakeAnswers(BaseModel):
    patient_language: str = "en"
    alias: str = "Patient"
    chief_complaint: str
    onset: str | None = None
    duration: str | None = None
    site: str | None = None
    severity: str | None = None
    other_symptoms: list[str] = Field(default_factory=list)
    tried: list[str] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    allergies: str | None = None  # None/empty = unknown
    medications: str | None = None
    insurance_type: InsuranceType = "unknown"

    @field_validator("allergies", "medications", "onset", "duration", "site", "severity")
    @classmethod
    def _blank_is_unknown(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return v.strip()


def is_none_word(value: str | None) -> bool:
    return value is not None and value.strip().lower() in _NONE_WORDS
