"""Configuration from the environment (ADR-0020 §7). Every variable is prefixed `VERST_`;
`infra/api/.env.example` lists them. No secret default works in production: `env=prod` refuses to start
without `VERST_RATE_KEY_SECRET` and an https `VERST_PUBLIC_BASE_URL`."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-not-a-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERST_", extra="ignore", frozen=True)

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql://verst_api@localhost:5432/verst"
    db_pool_max: int = Field(8, ge=1, le=64)
    migrate_on_start: bool = True

    # Routing (ADR-0017 §5, ADR-0020 §4): "graphhopper" needs VERST_GRAPHHOPPER_URL; "road_model" is the
    # engine's calibrated road model (trips may carry approxDistances = synthetic).
    routing: Literal["graphhopper", "road_model"] = "road_model"
    graphhopper_url: str | None = None
    graphhopper_timeout_s: float = Field(6.0, gt=0, le=30)
    synthetic_fallback: bool = False  # GraphHopper down → road model (flagged) instead of 503 UPSTREAM

    # CEO 29.10 (trips abroad, server only): the catalogues abroad (`<dir>/<cc>/catalogue_*.json.gz`; unset =
    # backend/planner/abroad next to the engine; missing or empty = Russia only) and the Bank of Russia rates
    # file of tools/ci/fetch_rates.py (unset = money abroad in the local currency only).
    abroad_dir: str | None = None
    rates_file: str | None = None

    clock: str = "system"  # "system" | "golden" | ISO datetime with offset (tests and demos)
    plan_timeout_s: float = Field(25.0, gt=0, le=120)
    sse_heartbeat_s: float = Field(5.0, gt=0, le=60)

    # Rate limits (ADR-0020 §6): per device unless noted, fixed windows.
    rate_plan_per_hour: int = Field(30, ge=1)
    rate_route_per_hour: int = Field(60, ge=1)
    rate_save_per_hour: int = Field(20, ge=1)
    rate_feedback_per_day: int = Field(10, ge=1)
    rate_default_per_hour: int = Field(600, ge=1)
    rate_register_per_hour_ip: int = Field(20, ge=1)
    rate_public_per_hour_ip: int = Field(300, ge=1)
    rate_key_secret: str = DEV_SECRET  # HMAC key for client IPs in rate-limit keys (never stored in clear)

    max_saved_trips: int = Field(50, ge=1)
    max_body_bytes: int = Field(2_000_000, ge=10_000)
    feedback_text_days: int = Field(180, ge=1)  # R-07 (в): free text is cleared after this many days

    public_base_url: str = "http://localhost:8000"  # share links: {public_base_url}/s/{slug}
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.routing == "graphhopper" and not self.graphhopper_url:
            raise ValueError("VERST_ROUTING=graphhopper needs VERST_GRAPHHOPPER_URL")
        if self.env == "prod":
            if self.rate_key_secret == DEV_SECRET or len(self.rate_key_secret) < 32:
                raise ValueError(
                    "VERST_RATE_KEY_SECRET: set a random value of at least 32 characters in prod"
                )
            if not self.public_base_url.startswith("https://"):
                raise ValueError("VERST_PUBLIC_BASE_URL must be https:// in prod")
            if self.clock != "system":
                raise ValueError("VERST_CLOCK must be 'system' in prod")
        return self
