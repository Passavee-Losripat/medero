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
