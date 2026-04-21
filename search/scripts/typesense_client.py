"""Typesense client singleton for THRN search scripts.

Reads connection settings from the same .env file used by the ingestion
pipeline.  All search scripts should obtain the client via ``get_client()``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env before anything else so TYPESENSE_* vars are available.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_file = _REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


_load_env()

# ---------------------------------------------------------------------------
# Build the singleton client
# ---------------------------------------------------------------------------

import typesense  # noqa: E402  (after env load)

_client: typesense.Client | None = None


def get_client() -> typesense.Client:
    """Return the module-level Typesense client singleton."""
    global _client
    if _client is None:
        host = os.environ.get("TYPESENSE_HOST", "localhost")
        port = int(os.environ.get("TYPESENSE_PORT", "8108"))
        protocol = os.environ.get("TYPESENSE_PROTOCOL", "http")
        api_key = os.environ.get("TYPESENSE_ADMIN_API_KEY", "change-me-locally")

        _client = typesense.Client(
            {
                "nodes": [
                    {
                        "host": host,
                        "port": str(port),
                        "protocol": protocol,
                    }
                ],
                "api_key": api_key,
                "connection_timeout_seconds": 10,
            }
        )
    return _client
