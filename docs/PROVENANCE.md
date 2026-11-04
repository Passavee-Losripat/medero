# Provenance

What was built when, what is mocked, what is third-party. All work below was created
during the Meta Global AI Developer Hackathon building period (Oct 27 – Nov 4, 2026 KST).
Git history is the detailed record; first commit: 2026-11-04 KST.

## Built during the hackathon

| Date (KST) | Work |
|---|---|
| 2026-11-04 | Repo scaffold, design rules |
| 2026-11-04 | Backend: schemas, glossary, fixed guardrail text, emergency detection, router (rules + model), verifier, visit pipeline, intake, prescription reader, insurance claim pack, FastAPI app with WebSocket visit and DEMO_MODE limits, fake provider, tests |
| 2026-11-04 | MOCK data: 10 cases, 45 labelled utterances, 3 role-plays, prescriptions, insurer checklists, receipt sets; eval harness |
| 2026-11-04 | Web PWA: intake, case card, visit, prescription, insurance, results |
| 2026-11-04 | Modal Glimmer server definition (not deployed); docs |

## Mocked

- All patients, clinics, prescriptions, receipts and insurers (`data/mock/`, labelled MOCK).
- `FakeProvider` (`api/app/providers/fake.py`): deterministic stand-in used when no API key is
  set. Its outputs are tagged `[FAKE]` and are never reported as results.

## Not yet verified against the real API (see docs/api-notes.md)

Realtime / file transcription formats, image input shape, `reasoning_effort` support,
structured-output behaviour, pricing.

## Third-party

See `THIRD_PARTY.md`.
