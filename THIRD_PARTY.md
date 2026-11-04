# Third-party code, models and assets

Every outside dependency, model and asset, with its license. Versions are pinned in
`api/requirements.txt` and `web/package-lock.json`.

## Meta models

| Model | Use | Terms |
|---|---|---|
| Muse Spark (`muse-spark-1.3`) via Meta Model API | Responder, ask-back, gloss, relay, verifier check, card translation, prescription/insurance reading; router option | Meta Model API terms (**VERIFY** data-use / retention terms; see docs/api-notes.md) |
| Muse Voice Transcribe (`muse-voice-transcribe-1.0`) | Korean speech-to-text | Meta Model API terms |
| Muse Glimmer (open weights) | Local 4-bit router (llama.cpp) and Modal baseline | Apache 2.0 per third-party articles (**VERIFY** on Meta's page / Hugging Face) |

## Python (backend)

| Package | License |
|---|---|
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| Pydantic | MIT |
| openai (OpenAI Python SDK, used as client for the Meta API) | Apache-2.0 |
| PyYAML | MIT |
| httpx | BSD-3-Clause |
| websockets | BSD-3-Clause |
| python-multipart | Apache-2.0 |
| pypdf | BSD-3-Clause |
| pytest | MIT |
| pytest-asyncio | Apache-2.0 |
| Pillow (dev only: renders MOCK images) | MIT-CMU (HPND) |

## JavaScript (web)

| Package | License |
|---|---|
| Next.js | MIT |
| React, React DOM | MIT |
| TypeScript, @types/* | Apache-2.0 / MIT |

## Infrastructure (optional, not deployed yet)

| Tool | License |
|---|---|
| Modal client | Apache-2.0 |
| vLLM (Modal image) | Apache-2.0 |
| llama.cpp (`llama-server`, local) | MIT |

## Fonts and assets

- MOCK prescription images in `data/mock/prescriptions/*.png` were rendered by
  `data/mock/render_mock_docs.py` using the macOS system font Apple SD Gothic Neo.
  **Open item:** before submission, re-render with an OFL font (e.g. Noto Sans KR,
  SIL OFL 1.1) by setting `MOCK_FONT=/path/to/NotoSansKR.ttf make mock-docs`, so the
  committed images use a font that is clearly licensed for redistribution.
- App icon (`web/public/icon.svg`): original, made for this project.
- All case cards, utterances, role-plays, prescriptions, receipts and insurer texts in
  `data/mock/` are invented for this project and labelled MOCK. No scraped or copied text.
