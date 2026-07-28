"""Application configuration.

Secrets come from the environment (a local ``.env`` during development, or
GitHub Actions secrets in CI). Non-secret behavior comes from ``config.yaml``.
Nothing sensitive is ever read from the YAML file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:  # optional dependency, only needed for local development
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is a convenience, not required
    load_dotenv = None  # type: ignore[assignment]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Config:
    """Resolved configuration for a single run."""

    # --- AI provider ---
    provider: str = "openai"  # "openai" | "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # --- Email / SMTP ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    email_to: str = ""
    email_from: str = ""

    # --- Logging ---
    log_level: str = "INFO"

    # --- Storage ---
    profile_file: Path = Path("data/candidate_profile.json")
    history_file: Path = Path("data/history.json")

    # --- Search behavior ---
    sources: list[str] = field(
        default_factory=lambda: ["remotive", "weworkremotely", "jobicy"]
    )
    # Per-company ATS boards (only used when the matching source is enabled).
    greenhouse_boards: list[str] = field(default_factory=list)
    lever_companies: list[str] = field(default_factory=list)
    ashby_companies: list[str] = field(default_factory=list)
    # The Muse (key is optional — it only raises rate limits).
    themuse_api_key: str = ""
    themuse_max_pages: int = 3
    # Findwork (requires an API token).
    findwork_api_key: str = ""
    findwork_max_pages: int = 2
    local_top_n: int = 25
    email_max: int = 15
    min_score: int = 0
    recommended_only: bool = False
    remote_regions_priority: list[str] = field(
        default_factory=lambda: ["Worldwide", "Europe", "EMEA"]
    )
    request_timeout: int = 30
    max_jobs_per_source: int = 300

    @property
    def resolved_email_from(self) -> str:
        return self.email_from or self.smtp_username

    @classmethod
    def load(
        cls,
        config_path: str | Path = "config.yaml",
        env_path: str | Path = ".env",
    ) -> Config:
        """Build a Config from ``config.yaml`` (behavior) + environment (secrets)."""
        if load_dotenv is not None:
            env_file = Path(env_path)
            if env_file.exists():
                load_dotenv(env_file)

        data: dict[str, Any] = {}
        cfg_file = Path(config_path)
        if cfg_file.exists():
            loaded = yaml.safe_load(cfg_file.read_text()) or {}
            if isinstance(loaded, dict):
                data = loaded

        cfg = cls()

        # Behavior from YAML (with defaults preserved when absent).
        cfg.provider = str(data.get("provider", cfg.provider))
        cfg.profile_file = Path(data.get("profile_file", cfg.profile_file))
        cfg.history_file = Path(data.get("history_file", cfg.history_file))
        cfg.sources = list(data.get("sources", cfg.sources))
        cfg.greenhouse_boards = list(data.get("greenhouse_boards", cfg.greenhouse_boards))
        cfg.lever_companies = list(data.get("lever_companies", cfg.lever_companies))
        cfg.ashby_companies = list(data.get("ashby_companies", cfg.ashby_companies))
        cfg.themuse_max_pages = int(data.get("themuse_max_pages", cfg.themuse_max_pages))
        cfg.findwork_max_pages = int(data.get("findwork_max_pages", cfg.findwork_max_pages))
        cfg.local_top_n = int(data.get("local_top_n", cfg.local_top_n))
        cfg.email_max = int(data.get("email_max", cfg.email_max))
        cfg.min_score = int(data.get("min_score", cfg.min_score))
        cfg.recommended_only = bool(data.get("recommended_only", cfg.recommended_only))
        cfg.remote_regions_priority = list(
            data.get("remote_regions_priority", cfg.remote_regions_priority)
        )
        cfg.request_timeout = int(data.get("request_timeout", cfg.request_timeout))
        cfg.max_jobs_per_source = int(
            data.get("max_jobs_per_source", cfg.max_jobs_per_source)
        )
        cfg.openai_model = str(data.get("openai_model", cfg.openai_model))
        cfg.anthropic_model = str(data.get("anthropic_model", cfg.anthropic_model))

        # Secrets strictly from the environment.
        cfg.openai_api_key = _env("OPENAI_API_KEY")
        cfg.openai_model = _env("OPENAI_MODEL") or cfg.openai_model
        cfg.anthropic_api_key = _env("ANTHROPIC_API_KEY")
        cfg.anthropic_model = _env("ANTHROPIC_MODEL") or cfg.anthropic_model
        cfg.provider = _env("AI_PROVIDER") or cfg.provider
        cfg.themuse_api_key = _env("THEMUSE_API_KEY")
        cfg.findwork_api_key = _env("FINDWORK_API_KEY")

        cfg.smtp_host = _env("SMTP_HOST") or cfg.smtp_host
        cfg.smtp_port = _env_int("SMTP_PORT", cfg.smtp_port)
        cfg.smtp_username = _env("SMTP_USERNAME")
        cfg.smtp_password = _env("SMTP_PASSWORD")
        cfg.email_to = _env("EMAIL_TO")
        cfg.email_from = _env("EMAIL_FROM")

        cfg.log_level = _env("LOG_LEVEL") or cfg.log_level

        return cfg
