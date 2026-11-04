"""Settings from environment variables (.env is loaded by the Makefile / uvicorn --env-file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float | None) -> float | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return float(v)


@dataclass
class Settings:
    model_api_key: str = field(default_factory=lambda: os.getenv("MODEL_API_KEY", ""))
    model_api_base: str = field(default_factory=lambda: os.getenv("MODEL_API_BASE", "https://api.meta.ai/v1"))
    spark_model: str = field(default_factory=lambda: os.getenv("SPARK_MODEL", "muse-spark-1.3"))
    # VERIFY: whether the Meta API accepts reasoning_effort on chat completions. Empty = do not send.
    reasoning_effort: str = field(default_factory=lambda: os.getenv("REASONING_EFFORT", "low"))
    asr_model: str = field(default_factory=lambda: os.getenv("ASR_MODEL", "muse-voice-transcribe-1.0"))
    asr_realtime_url: str = field(
        default_factory=lambda: os.getenv("ASR_REALTIME_URL", "wss://api.meta.ai/v1/asr/realtime"))

    router_provider: str = field(default_factory=lambda: os.getenv("ROUTER_PROVIDER", "spark"))
    local_llm_base: str = field(default_factory=lambda: os.getenv("LOCAL_LLM_BASE", "http://127.0.0.1:8080/v1"))
    local_llm_model: str = field(default_factory=lambda: os.getenv("LOCAL_LLM_MODEL", "muse-glimmer-q4"))
    modal_llm_base: str = field(default_factory=lambda: os.getenv("MODAL_LLM_BASE", ""))
    modal_llm_key: str = field(default_factory=lambda: os.getenv("MODAL_LLM_KEY", ""))
    modal_llm_model: str = field(default_factory=lambda: os.getenv("MODAL_LLM_MODEL", "muse-glimmer"))

    llm_fake: bool = field(default_factory=lambda: _bool("LLM_FAKE", False))
    model_timeout_s: float = field(default_factory=lambda: _float("MODEL_TIMEOUT_S", 8.0) or 8.0)
    model_max_retries: int = field(default_factory=lambda: int(os.getenv("MODEL_MAX_RETRIES", "1")))
    verifier_model_check: bool = field(default_factory=lambda: _bool("VERIFIER_MODEL_CHECK", True))

    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    demo_rate_limit_per_min: int = field(default_factory=lambda: int(os.getenv("DEMO_RATE_LIMIT_PER_MIN", "30")))
    demo_daily_call_cap: int = field(default_factory=lambda: int(os.getenv("DEMO_DAILY_CALL_CAP", "1500")))
    demo_daily_spend_cap_usd: float = field(default_factory=lambda: _float("DEMO_DAILY_SPEND_CAP_USD", 5.0) or 5.0)
    # VERIFY: Spark prices per million tokens. Unset = spend is not estimated (call cap still applies).
    spark_price_in_per_m: float | None = field(default_factory=lambda: _float("SPARK_PRICE_IN_PER_M", None))
    spark_price_out_per_m: float | None = field(default_factory=lambda: _float("SPARK_PRICE_OUT_PER_M", None))

    web_origin: str = field(default_factory=lambda: os.getenv("WEB_ORIGIN", "http://localhost:3000"))

    @property
    def use_fake(self) -> bool:
        return self.llm_fake or not self.model_api_key


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
