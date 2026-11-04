# Meta API notes (verified behaviour only)

Record each verified fact with the date and how it was checked. Until a row says
VERIFIED, the code treats it as an assumption.

| Item | Status | Assumption in code | Where |
|---|---|---|---|
| Chat Completions via OpenAI SDK at `https://api.meta.ai/v1` | NOT YET TESTED (no key yet) | `AsyncOpenAI(base_url=..., api_key=MODEL_API_KEY)` | `api/app/providers/llm.py` |
| Structured output | NOT YET TESTED | `response_format={"type":"json_schema","json_schema":{name, schema, strict:false}}`; output parsed tolerantly and validated by Pydantic | `llm.py` |
| `reasoning_effort` on chat completions | NOT YET TESTED | sent as `reasoning_effort="low"`; set `REASONING_EFFORT=` (empty) to stop sending it | `config.py` |
| Prompt caching | NOT YET TESTED | static prefix first (rules, glossary, schema, card); no explicit cache parameter | `pipeline/prompts.py` |
| Image input | NOT YET TESTED | OpenAI `image_url` with a base64 data URL | `pipeline/documents.py` |
| ASR file endpoint `POST /v1/asr/transcribe` | NOT YET TESTED | multipart `file`, `model`, `language=ko`, `keywords`; reads `text`/`transcript`/`segments` | `providers/asr.py` |
| ASR realtime `wss://api.meta.ai/v1/asr/realtime` | NOT YET TESTED | bearer header, `session.update` JSON, binary PCM16 16 kHz, tolerant event parsing. Not wired into the UI yet (UI uses push-to-talk + file endpoint) | `providers/asr.py` |
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
