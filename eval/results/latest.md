# Medero evaluation results

Generated 2026-11-04T15:59:58+00:00 · models: muse-spark-1.3

> All data is **MOCK** (invented cases and utterances, written by the developer). Korean utterances await native-speaker review. Numbers below are measured, not estimated.

## Router accuracy

| Router | n | Accuracy | p50 ms | p95 ms | API calls |
|---|---|---|---|---|---|
| rules | 45 | 75.6% | 0.0 | 0.0 | 0 |
| spark | 45 | 91.1% | 2290.4 | 6150.4 | 45 |
| modal | 45 | 91.1% | 3458.7 | 7084.8 | 0 |

**rules per class:** needs_decision 40%, needs_fact 100%, on_card 81%, procedural 100%, unclear 0%
Confusions: needs_decision->needs_fact ×6, on_card->needs_fact ×3, unclear->needs_fact ×1, unclear->procedural ×1

**spark per class:** needs_decision 100%, needs_fact 80%, on_card 88%, procedural 100%, unclear 100%
Confusions: needs_fact->on_card ×2, on_card->needs_fact ×2

**modal per class:** needs_decision 100%, needs_fact 80%, on_card 88%, procedural 100%, unclear 100%
Confusions: needs_fact->on_card ×2, on_card->needs_fact ×2

## Full visits (role-plays)

### Router: rules

- Visits: 3
- Decision escalation (needs_decision -> ask-back): **3/3**
- Spoken replies (excluding fixed phrases): 11
- Independent Spark audit flagged as unsupported: **0** of 11
- Replies blocked by the verifier (became ask-backs): 1
- Doctor's words translated for the patient: 17, flagged by the number/negation check: 1
- Meta API calls per visit (mean): 7.67

| Stage | p50 ms | p95 ms |
|---|---|---|
| route | 0.0 | 0.1 |
| respond | 4429.0 | 7687.8 |
| verify | 0.0 | 0.2 |
| total | 4430.0 | 7688.2 |

## Prescription fields (exact match, MOCK)

**Reader: spark (muse-spark-1.3)** · latency p50 8829.2 ms

| Set | Docs | Fields | Accuracy | Form checks |
|---|---|---|---|---|
| Medicine-bag labels, clean | 3 | 30 | 100.0% | — |
| Medicine-bag labels, simulated phone photo | 3 | 30 | 100.0% | — |
| Clinic prescription forms (처방전), simulated phone photo | 2 | 48 | 97.9% | 12/12 |

**Reader: modal-glimmer (muse-glimmer-30B)** · latency p50 37042.4 ms

| Set | Docs | Fields | Accuracy | Form checks |
|---|---|---|---|---|
| Medicine-bag labels, clean | 3 | 30 | 83.3% | — |
| Medicine-bag labels, simulated phone photo | 3 | 30 | 90.0% | — |
| Clinic prescription forms (처방전), simulated phone photo | 2 | 48 | 97.9% | 10/12 |

Form checks: document kind, valid-for days, issue date, disease code, disease-code request shown only when the box is blank, handwritten note detected.

## Claim completeness (deterministic matcher)

- `missing` matched the known gaps in **4/4** MOCK receipt sets

## Not measured here

- Transcription quality: spot-check recorded role-plays by hand (see docs/api-notes.md).
