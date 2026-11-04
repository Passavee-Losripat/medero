# Korean (and Thai) phrases awaiting native-speaker review

Nothing here has been reviewed yet. Mark each item ✅ with reviewer and date.

## Fixed Korean shown or spoken to clinicians (`api/app/fixed_text.py`)

- [ ] Disclosure: 안녕하세요. 저는 한국어를 못하는 환자를 돕는 AI 도우미입니다. 환자가 승인한 정보만 전달하고, 결정은 환자에게 직접 묻습니다. 도와드려도 될까요?
- [ ] Declined: 알겠습니다. 환자에게 직접 말씀해 주세요. 천천히, 쉬운 말로 부탁드립니다.
- [ ] Holding phrase: 잠시만요, 환자에게 확인하고 있습니다.
- [ ] Repeat request: 죄송합니다. 다시 한 번 천천히 말씀해 주시겠어요?
- [ ] Fallback note: 잠시 연결이 지연되고 있습니다. 아래는 환자가 승인한 정보입니다.
- [ ] Patient answer prefix: 환자 답변:
- [ ] Emergency card: 응급 상황입니다 / 이 환자는 응급 증상을 말했습니다. 바로 도와주세요. / 구급차 (통역 가능) / 의료 정보 상담
- [ ] Consent buttons (web): 네, 괜찮아요 / 아니요

## Glossary (`api/app/glossary_ko.yaml`)

- [ ] All 60 entries (each has `reviewed: false`). Desk document terms from CLAUDE.md section 7 first.

## Router cues and emergency keywords

- [ ] Korean cue lists in `api/app/pipeline/router.py` and `api/app/safety.py`.

## MOCK data

- [ ] 45 utterances in `data/mock/utterances.jsonl` and their labels.
- [ ] Role-plays in `data/mock/roleplays/`.
- [ ] MOCK prescription label text in `data/mock/prescriptions/slips.json`.

## Thai (patient side)

- [ ] `web/lib/i18n.ts` (th), `fixed_text.py` PATIENT_TEXT["th"], emergency card Thai, Thai MOCK cases.
