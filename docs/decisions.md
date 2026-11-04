# Design decisions

Short log. Newest last.

- **2026-11-04 – Fake provider for offline work.** No API key yet, so every model task has a
  deterministic stand-in (`providers/fake.py`). Outputs are tagged `[FAKE]`; eval skips model
  sections when fake. Reason: build and test the whole flow before the key arrives.
- **2026-11-04 – `Fact.value_ko` added to the contract.** Approved facts are rendered to Korean
  once, at card approval, using glossary terms. The fallback screen (model timeout) needs Korean
  facts, and the responder builds on this wording. Optional field; does not change other contracts.
- **2026-11-04 – Unknown facts cannot be approved.** `approve()` ignores ids whose value is null.
  An explicit "I have none" in intake is stored as the patient's own words ("no known allergies").
- **2026-11-04 – Router failure = `unclear`.** If the router errors or returns a bad class, the turn
  is treated as unclear (ask to repeat), never as on-card.
- **2026-11-04 – Deterministic summary.** `doctor_said` is built from the per-turn renderings of
  clinician speech only, each with its source turn id. No extra generation step.
- **2026-11-04 – Claim draft is a fixed template**, not generated: lists documents and missing items,
  with placeholders for name and policy number. Never sent automatically.
- **2026-11-04 – Missing-document matching is deterministic** (synonym map to glossary keys). Card
  payment slips never count as a pharmacy receipt.
- **2026-11-04 – Push-to-talk first, realtime later.** The UI records one clinician turn and sends it
  to the file transcription endpoint. The realtime adapter exists but is not wired to the UI until its
  message format is verified.
- **2026-11-04 – Dependencies.** `pypdf` (read insurer PDFs locally instead of relying on unverified
  file upload), `python-multipart` (FastAPI uploads), `websockets` (realtime ASR client), `Pillow`
  (dev only, renders MOCK images), `pytest-asyncio` (async tests).
- **2026-11-04 – Patient UI languages: English and Thai.** Thai strings need native review.
- **2026-11-04 – `Fact.answers_question`.** Facts confirmed in the visit store the clinician question they
  answer. Reason: the eval audit flagged a correct relay of "ไม่มีค่ะ" (none) as unsupported because the
  stored fact had no subject. The audit and the responder now see the question with the answer.
- **2026-11-05 – Clinic prescription form (처방전) support.** Layout studied from the developer's own form
  (the photo is not in the repo and was never sent to a model). MOCK forms reproduce the layout with invented
  data. Patient notes (valid-for days, pharmacy keeps the copy, disease-code box blank) are fixed text built
  from printed fields; nothing is inferred.
- **2026-11-05 – Disease-code reminder.** For travel / private / school cover (and unknown), the after-visit
  screen and the prescription reader show a fixed Korean request the patient may choose to show staff. It is
  never sent and does not predict coverage. Reason: a blank 질병분류기호 box is a common reason a claim
  later needs extra paperwork.
- **2026-11-05 – Korean speech output via the browser's Web Speech API.** Muse has no TTS. The phone's
  built-in ko-KR voice is on-device, free, needs no new dependency, and stores no audio. On-screen large Korean
  text stays the primary output; speech is a toggle. Hands-free listening pauses while speaking.
- **2026-11-05 – Translation fidelity checks (`pipeline/fidelity.py`).** Deterministic comparison of source
  and translation on numerals and negation ("not / 없 / ไม่"), the errors that change meaning in a clinic.
  Blocking for Korean said to the doctor: a patient relay that drifts falls back to the patient's own words;
  a case-card Korean that drifts is discarded; a reply with a "no/not" that no cited fact contains is
  blocked (verifier rule 3b). Flagging for text shown to the patient: the doctor's translated words and the
  prescription gloss get a warning, and the original Korean / printed numbers stay on screen. Time words
  (yesterday, a week, 하루) are deliberately not counted as numbers to avoid false alarms.
