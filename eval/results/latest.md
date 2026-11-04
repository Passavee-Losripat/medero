# Medero evaluation results

Generated 2026-11-04T13:20:59+00:00 · models: muse-spark-1.3

> All data is **MOCK** (invented cases and utterances, written by the developer). Korean utterances await native-speaker review. Numbers below are measured, not estimated.

## Router accuracy

| Router | n | Accuracy | p50 ms | p95 ms | API calls |
|---|---|---|---|---|---|
| rules | 45 | 75.6% | 0.0 | 0.0 | 0 |
| spark | 45 | 93.3% | 2331.3 | 7997.3 | 45 |

**rules per class:** needs_decision 40%, needs_fact 100%, on_card 81%, procedural 100%, unclear 0%
Confusions: needs_decision->needs_fact ×6, on_card->needs_fact ×3, unclear->needs_fact ×1, unclear->procedural ×1

**spark per class:** needs_decision 100%, needs_fact 90%, on_card 88%, procedural 100%, unclear 100%
Confusions: needs_fact->on_card ×1, on_card->needs_fact ×2

## Full visits (role-plays)

### Router: rules

- Visits: 3
- Decision escalation (needs_decision -> ask-back): **3/3**
- Spoken replies (excluding fixed phrases): 12
- Independent Spark audit flagged as unsupported: **0** of 12
- Replies blocked by the verifier (became ask-backs): 0
- Meta API calls per visit (mean): 7.67

| Stage | p50 ms | p95 ms |
|---|---|---|
| route | 0.1 | 0.1 |
| respond | 4549.7 | 8633.2 |
| verify | 0.0 | 0.2 |
| total | 4550.6 | 8634.0 |

## Prescription fields

- 30 fields on 3 MOCK slips, exact-match accuracy 100.0%

## Claim completeness (deterministic matcher)

- `missing` matched the known gaps in **4/4** MOCK receipt sets

## Not measured here

- Transcription quality: spot-check recorded role-plays by hand (see docs/api-notes.md).
