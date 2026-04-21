"""Configuration — loads .env from the repo root via python-dotenv.

All environment variables consumed by the ingestion pipeline are
accessed through this module. Import Config (singleton) rather than
reading os.environ directly in other modules.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Locate repo root: we are at  ingestion/src/thrn_ingest/config.py
# Repo root is three parents up.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent  # th-research-navigator/


def _find_env_file() -> Path | None:
    """Walk up from repo root looking for .env."""
    candidate = _REPO_ROOT / ".env"
    if candidate.exists():
        return candidate
    return None


_env_path = _find_env_file()
if _env_path:
    load_dotenv(_env_path, override=False)
else:
    load_dotenv(override=False)  # still honours shell env if no file


class _Config:
    """Typed accessors for all env vars consumed by the ingestion pipeline."""

    # -- OpenAlex ----------------------------------------------------------
    @property
    def openalex_base_url(self) -> str:
        return os.environ.get("OPENALEX_BASE_URL", "https://api.openalex.org")

    @property
    def openalex_contact_email(self) -> str:
        val = os.environ.get("OPENALEX_CONTACT_EMAIL", "")
        if not val:
            raise RuntimeError(
                "OPENALEX_CONTACT_EMAIL is required (polite-pool). "
                "Set it in your .env file."
            )
        return val

    # -- PostgreSQL --------------------------------------------------------
    @property
    def database_url(self) -> str:
        # Prefer the convenience DSN, fall back to component parts.
        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            return dsn
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "thrn")
        user = os.environ.get("POSTGRES_USER", "thrn")
        pw = os.environ.get("POSTGRES_PASSWORD", "change-me-locally")
        return f"postgresql://{user}:{pw}@{host}:{port}/{db}"

    @property
    def db_min_connections(self) -> int:
        return int(os.environ.get("DB_MIN_CONNECTIONS", "1"))

    @property
    def db_max_connections(self) -> int:
        return int(os.environ.get("DB_MAX_CONNECTIONS", "5"))

    # -- Typesense ---------------------------------------------------------
    @property
    def typesense_host(self) -> str:
        return os.environ.get("TYPESENSE_HOST", "localhost")

    @property
    def typesense_port(self) -> int:
        return int(os.environ.get("TYPESENSE_PORT", "8108"))

    @property
    def typesense_protocol(self) -> str:
        return os.environ.get("TYPESENSE_PROTOCOL", "http")

    @property
    def typesense_admin_api_key(self) -> str:
        return os.environ.get("TYPESENSE_ADMIN_API_KEY", "change-me-locally")

    # -- Paths -------------------------------------------------------------
    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def data_seed_dir(self) -> Path:
        return _REPO_ROOT / "data" / "seed"

    @property
    def data_raw_dir(self) -> Path:
        return _REPO_ROOT / "data" / "raw"

    @property
    def journal_whitelist_csv(self) -> Path:
        return self.data_seed_dir / "journal_whitelist.csv"

    # -- Logging -----------------------------------------------------------
    @property
    def log_level(self) -> str:
        return os.environ.get("LOG_LEVEL", "info").upper()

    # -- Search reindex scripts path ---------------------------------------
    @property
    def search_scripts_dir(self) -> Path:
        return _REPO_ROOT / "search" / "scripts"


# Public singleton
Config = _Config()
