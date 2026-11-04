# Medero

**A medical companion for people who don't speak the local language.** Medero speaks to a Korean
clinic for the patient, using only facts the patient approved on a "case card". It sends decisions
and unknowns back to the patient, then helps read the prescription label and get insurance
documents together.

> Medero is a communication and navigation tool. **It does not diagnose, suggest treatment, or give
> medical advice.** In an emergency it shows a fixed card: call **119** (ambulance, interpretation
> available) or **1339** (medical information).

Built solo for the **Meta Global AI Developer Hackathon** (Indie Developer track, "Build for Your World").

## Meta models used

| Model | Where it runs | What it does in Medero |
|---|---|---|
| **Muse Spark** `muse-spark-1.3` | Meta Model API | Writes Korean replies from approved facts, phrases questions back to the patient, translates the doctor's words for the patient, relays the patient's answers, translates the case card, reads the insurer's checklist |
| **Muse Voice Transcribe** `muse-voice-transcribe-1.0` | Meta Model API | Hands-free Korean speech to text in the visit |
| **Muse Glimmer 30B** (open weights, 4-bit GGUF + vision encoder) | **Our own GPU on Modal** (or this Mac) via llama.cpp | Reads photos that carry the patient's name and ID number (prescription forms, receipts), so they never go to a third-party API. Also benchmarked as the turn router |

The split is deliberate: conversation turns go to Spark carrying only an alias and approved facts; documents that
identify the patient are read by an open-weight model on infrastructure we run. In production the same model
can run on-device.

## How it works

```
Phone (Next.js PWA) ──WebSocket──> FastAPI
  doctor speech ─> Voice Transcribe ─> Router (rules | Spark | Glimmer)
                                    ─> Responder (Spark, structured output, approved facts only)
                                    ─> Verifier (deterministic rules 1–4 + fidelity checks)
                                    ─> Korean reply (shown + spoken), or a question card for the patient
  photo of a document ─> Glimmer on our GPU (or Spark after the patient covers name/ID on the phone)
```

### How Medero keeps the model from saying things that aren't true

No model can be guaranteed never to err, so Medero never trusts one alone where it matters:

1. **Korean said to the doctor** may only state approved facts. A deterministic verifier blocks a reply that
   cites no fact, cites an unapproved or unknown fact, has a number not in the fact, or says "no / not" when no
   cited fact does. A blocked reply becomes a question to the patient. Decisions are never answered by Medero.
2. **Every translation is compared with its source** (`api/app/pipeline/fidelity.py`) on numbers and negation,
   the two errors that change meaning in a clinic ("5 days" → "3일", "not allergic" → "알레르기 있음").
   Korean for the doctor that drifts is blocked and the patient's own words are shown instead; text for the
   patient that drifts carries a warning, with the doctor's original Korean or the printed label kept on screen.
3. **Fixed text, not generated text,** for everything safety-critical: the AI disclosure, the emergency card
   (119 / 1339), prescription notes ("valid for N days", "confirm with the pharmacist"), the disease-code request.
4. **Medical terms only from the glossary**; anything else is shown untranslated and flagged.

What this cannot catch: a wrong word with the same numbers and no negation (e.g. "drops" for "ointment").
That is why the original Korean always stays visible and every medicine line says "confirm with the pharmacist".

## Features

- **Prepare:** health basics once (unknown stays unknown, never "none"), "how are you feeling?" → a case card the
  patient approves fact by fact.
- **Visit:** AI disclosure and permission first; hands-free listening (Korean = doctor, anything else = patient);
  answers from the card; question cards for decisions and new facts; Korean replies spoken aloud; large-text mode;
  "under the hood" panel with turn class, evidence and latency; emergency words stop everything.
- **After:** what the doctor said, a checklist, and a "before you leave" Korean request for the disease code and
  itemized bill when the patient will claim from their own insurer.
- **Prescription:** reads the Korean clinic form (처방전) and pharmacy labels as printed: dose, times a day, days,
  instructions, (비급여) not-covered, 대체 불가, validity days, blank disease-code box, cut-off names, handwriting.
- **Insurance:** reads the insurer's own checklist (page or PDF), checks what is missing, drafts a message the
  patient sends themselves. Never predicts coverage.
- **Find:** the patient's words → the department sign to look for (fixed keyword table, e.g. "eye" → 안과) →
  a Naver / Kakao / Google Maps search. No ranking or recommendation.

## Built during the hackathon

Everything in this repo: backend pipeline, guardrails, verifier, web app, MOCK data, eval harness,
Modal server definition. See `docs/PROVENANCE.md` and the git history.

## What is mocked

- All patients, clinics, prescriptions, receipts and insurers in `data/mock/` are **invented and
  labelled MOCK**. Drug names on MOCK labels are made up.
- Without `MODEL_API_KEY`, a deterministic **fake provider** stands in for the models. Its outputs
  are tagged `[FAKE]` and are never reported as results.
- Korean (and Thai) text awaits native-speaker review: `docs/korean-review.md`.

## Run it

```bash
make setup                 # Python venv + web deps
cp .env.example .env       # add MODEL_API_KEY (or leave empty for FAKE mode)
cp web/.env.local.example web/.env.local
make dev                   # API on :8000, web on :3000
make test                  # backend tests + typecheck
make eval                  # writes eval/results/latest.md (needs a key for model sections)
make eval-offline          # rules baseline + claim matcher only
```

Glimmer: `bash scripts/modal_setup.sh` deploys it on Modal (weights `meta-models/Muse-Glimmer-30B-GGUF`,
Apache-2.0); `make glimmer` runs it on a Mac with llama.cpp >= b10353. Then set `DOC_PROVIDER=modal|local`
and/or `ROUTER_PROVIDER=modal|local`. Phone testing over HTTPS on the LAN: `make phone` (see `docs/TEST_SCRIPT.md`).

## Results

Measured on 2026-11-05 with `muse-spark-1.3` (reasoning effort `minimal`) and Muse Glimmer 30B 4-bit (llama.cpp,
reasoning strength `low`) on one L40S GPU on Modal. All data is MOCK and written by the developer; Korean awaits
native-speaker review. Full table: `eval/results/latest.md` (also `/results` in the app). Self-hosted latencies are
measured after the model has loaded (cold start excluded and reported separately).

**Turn router, 45 labelled Korean doctor utterances**

| Router | Accuracy | p50 / p95 | Meta API calls |
|---|---|---|---|
| Offline rules | 75.6% | 0 ms | 0 |
| Muse Spark (API) | 91.1% (93.3% on an earlier run) | 2.3 s / 6.2 s | 45 |
| **Muse Glimmer 4-bit (our GPU)** | **91.1%** | 3.5 s / 7.1 s | **0** |

Glimmer matches Spark's accuracy on this set with zero API calls (they disagree on 2 of 45). Every rules-router
error sends the turn to the patient, the safe direction. The live app ships the rules router by default (instant,
free) and can switch with `ROUTER_PROVIDER`.

**Visits and safety (3 MOCK role-plays, rules router)**

| What | Result |
|---|---|
| Decisions sent back to the patient | 3 / 3 |
| Spoken replies flagged by an independent Spark audit | 0 / 11 |
| Replies blocked by the verifier (became questions to the patient) | 1 |
| Doctor's words translated for the patient / flagged by the number-negation check | 17 / 1 |
| Doctor turn to Korean reply, p50 / p95 (text input) | 4.4 s / 7.7 s (above the 2.5 s target) |

**Documents (exact field match, MOCK; re-measured after re-rendering the images with OFL fonts)**

| Set | Spark (API) | Glimmer (our GPU) |
|---|---|---|
| Medicine-bag labels, clean (30 fields) | 100% | 96.7% |
| Medicine-bag labels, simulated phone photo (30) | 100% | 80.0% |
| Clinic prescription forms 처방전, phone photo (48) | 97.9%, form checks 12/12 | 97.9%, form checks 12/12 |
| Reader latency p50 | 8.4 s | 34.2 s |
| Insurer checklist from a MOCK PDF | 7 / 7 documents | — |
| Missing insurance documents, 4 MOCK sets | 4 / 4 | — |

The honest trade-off: Glimmer keeps identifying photos off third-party APIs but is slower and less exact on
labels than Spark, which is why every reading shows the printed Korean next to the translation, flags low
confidence, and says "confirm with the pharmacist". If Glimmer is not available, the phone covers the name/ID
area and Spark reads the covered photo.

## Privacy

No raw audio is stored. Sessions live in memory and can be deleted (`DELETE /sessions/{id}`). The
patient uses an alias; ID-number, phone and email patterns are removed before any model call. Photos that
identify the patient are read by Glimmer on our own GPU; if a cloud reader is used instead, the phone first
covers the name/ID area (solid fill on the device, adjustable by the patient), so those pixels are never uploaded.

## AI-assisted development

Medero was built with **Claude Code** (Anthropic) as an AI coding assistant: it wrote much of the code, tests,
mock data and docs under the developer's direction. The product idea, the guardrails, the scope and every
decision are the developer's, written down in `CLAUDE.md` before coding started and kept as the source of
truth throughout. The logo was made with ChatGPT (see `THIRD_PARTY.md`). No Anthropic or OpenAI model is part
of Medero's runtime; the app runs on Meta models only.

## License and third parties

See `THIRD_PARTY.md`.
