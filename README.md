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

- **Muse Spark** (`muse-spark-1.3`, Meta Model API): writes replies from approved facts, phrases
  ask-backs, renders clinician speech for the patient, relays patient answers, checks replies
  (verifier), translates the case card, and reads prescription labels and insurance documents.
- **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`): Korean speech to text for clinician turns.
- **Muse Glimmer** (open weights, 4-bit via llama.cpp locally, or on Modal): turn router. The
  benchmark compares it against Spark on accuracy, latency and API calls.

## How it works

```
Phone (Next.js PWA) ──WebSocket──> FastAPI
  clinician audio ─> Voice Transcribe ─> Router (Glimmer | Spark | rules)
                                      ─> Responder (Spark, structured output)
                                      ─> Verifier (rules + Spark check)
                                      ─> reply in Korean, or ask the patient
```

The verifier blocks any reply whose facts, numbers or durations are not in an approved fact.
Decisions (procedures, medicines, payment) always become an ask-back to the patient.

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

Local Glimmer router: run `llama-server` with a 4-bit GGUF (`make glimmer GLIMMER_GGUF=...`), then
set `ROUTER_PROVIDER=local`. Microphone access needs HTTPS outside localhost.

## Results

Measured numbers only, from `eval/results/latest.md` (also shown at `/results` in the app).
Not yet run with real models: **[pending API key]**.

## Privacy

No raw audio is stored. Sessions live in memory and can be deleted (`DELETE /sessions/{id}`). The
patient uses an alias; ID-number, phone and email patterns are removed before any model call.

## AI-assisted development

This project was built with AI coding assistance (Claude Code). All design decisions, guardrails
and scope come from the developer; the code was reviewed and tested by the developer.

## License and third parties

See `THIRD_PARTY.md`.
