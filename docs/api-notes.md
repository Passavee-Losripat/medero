# Meta API notes (verified behaviour only)

Record each verified fact with the date and how it was checked. Until a row says
VERIFIED, the code treats it as an assumption.

| Item | Status | Assumption in code | Where |
|---|---|---|---|
| `GET /v1/models` with bearer key | **VERIFIED 2026-11-04** (curl). Key has: `muse-spark-1.3`, `muse-spark-1.2`, `muse-spark-1.1`, `muse-spark-1.3-contributor`, `muse-spark-1.2-contributor`, `muse-voice-transcribe-1.0`, `muse-image-1.0`, `sam-3.1`. Medero uses `muse-spark-1.3` (not `-contributor`; its data-use terms are unchecked) | `.env` `SPARK_MODEL` |
| Chat Completions via OpenAI SDK at `https://api.meta.ai/v1` | **VERIFIED 2026-11-04** (live call, `muse-spark-1.3`) | `AsyncOpenAI(base_url=..., api_key=MODEL_API_KEY)` | `api/app/providers/llm.py` |
| Structured output | **VERIFIED 2026-11-04**: `response_format` json_schema returns valid JSON matching the schema | as before | `llm.py` |
| `reasoning_effort` | **VERIFIED 2026-11-04**: accepted values minimal, low, medium, high, xhigh, max; `none` returns 400 for Spark. Omitted = model decides (measured 23 s, 1.7k reasoning tokens on a tiny classify task). Median of 3 short relay calls: 1.3 minimal 2.5 s, 1.3 low 3.5 s, 1.2 minimal 1.7 s, 1.1 low 1.7 s; one 1.2-low output was nonsense. Medero uses 1.3 + minimal | `config.py` |
| Prompt caching | NOT YET TESTED | static prefix first (rules, glossary, schema, card); no explicit cache parameter | `pipeline/prompts.py` |
| Image input | NOT YET TESTED | OpenAI `image_url` with a base64 data URL | `pipeline/documents.py` |
| ASR file endpoint `POST /v1/asr/transcribe` | **VERIFIED 2026-11-04** (docs + live call): multipart parts `request` (JSON: `model`, `audioEncoding:"WAV"` required, `mode` PUSH_TO_TALK/ENDPOINTING/DIARIZATION, `keywords[]`, `languageBias[]` by name e.g. "Korean") and `audio` (mono 16-bit PCM WAV, 16 or 24 kHz). Response `{sessionId, transcript, audioDurationMs, turns[]}`; no confidence or language field. Auto-detected Korean and English on synthetic macOS-voice clips; ~1.3–1.8 s for a 2 s clip; trailing punctuation noise (`??!`) observed | `providers/asr.py` |
| ASR realtime `wss://api.meta.ai/v1/asr/realtime` | DOCS READ 2026-11-04, not tested: first JSON frame within 10 s with key in `authorization.accessToken`; ack has `sessionId`; binary PCM16 16/24 kHz; events speechStart/transcript/speechEnd/speechComplete; finish with `{"type":"endStream"}`. Adapter not yet aligned; UI uses VAD + file endpoint | `providers/asr.py` |
| Spark pricing / rate limits | UNKNOWN | spend estimated only if `SPARK_PRICE_*` set; call cap always applies | `config.py` |
| Contributor-mode data use | UNKNOWN | do not use Contributor-mode models for health-like data | – |
| Muse Glimmer HF id, license, Korean quality | UNKNOWN | `LOCAL_LLM_MODEL`, `GLIMMER_MODEL_ID` are placeholders | `infra/modal_glimmer.py` |

## First-run checklist (when the key arrives)

1. `curl` one chat completion; confirm model id and response shape.
2. One structured-output call with the router schema; confirm it returns valid JSON.
3. Same with `reasoning_effort=low`; if rejected, set `REASONING_EFFORT=`.
4. One image call with `data/mock/prescriptions/rx01.png`.
5. One file transcription of a short Korean recording; check field names.
6. Record results here with the date.


## Consequences for design (2026-11-04)

- One Spark call per turn at most on the live path; router defaults to the offline rules router, Spark/Glimmer routers are benchmarked separately.
- Verifier model check (a second Spark call) is off on the live path by default (`VERIFIER_MODEL_CHECK=0`); deterministic rules always run.
- Model timeout raised to 15 s.
