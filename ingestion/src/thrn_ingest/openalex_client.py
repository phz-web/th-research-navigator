"""OpenAlex HTTP client with polite-pool support, retry logic, and cursor pagination.

Every outgoing request:
- Sends ``mailto={OPENALEX_CONTACT_EMAIL}`` as a query parameter (polite pool).
- Identifies the caller via a custom ``User-Agent`` header.
- Retries transient 429 and 5xx responses with exponential back-off (tenacity).

The cursor pagination helper yields one page of results at a time. Pass
``cursor="*"`` to start from the beginning; the function drives subsequent
cursor tokens from ``meta.next_cursor`` until exhausted or ``max_pages`` reached.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any

import requests
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from thrn_ingest.config import Config

logger = logging.getLogger(__name__)

_APP_USER_AGENT = (
    "TourismHospitalityResearchNavigator/0.1 "
    "(https://github.com/thrn; contact via OPENALEX_CONTACT_EMAIL)"
)

# Seconds to wait when a 429 comes back without a Retry-After header.
_DEFAULT_BACKOFF_429 = 5.0


def _is_transient(exc: BaseException) -> bool:
    """Return True for errors that should trigger a retry."""
    if isinstance(exc, requests.HTTPError):
        code = exc.response.status_code if exc.response is not None else 0
        return code == 429 or code >= 500
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    return False


class OpenAlexClient:
    """Thin wrapper around requests.Session that enforces polite-pool requirements."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _APP_USER_AGENT})
        self._base_url = Config.openalex_base_url.rstrip("/")
        self._email = Config.openalex_contact_email

    # ------------------------------------------------------------------
    # Low-level GET
    # ------------------------------------------------------------------

    def _build_params(self, extra: dict[str, Any]) -> dict[str, Any]:
        params = {"mailto": self._email}
        params.update(extra)
        return params

    @retry(
        retry=retry_if_exception(_is_transient),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        resp = self._session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", _DEFAULT_BACKOFF_429))
            logger.warning(
                "Rate limited (429); backing off",
                extra={"retry_after": retry_after, "url": url},
            )
            time.sleep(retry_after)
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        """GET *path* with polite-pool params appended."""
        return self._get(path, self._build_params(params))

    # ------------------------------------------------------------------
    # Cursor pagination
    # ------------------------------------------------------------------

    def paginate(
        self,
        path: str,
        extra_params: dict[str, Any] | None = None,
        per_page: int = 200,
        max_pages: int | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield successive pages from a cursor-paginated OpenAlex endpoint.

        Each yielded value is the raw JSON dict for one page (i.e. has ``results``
        and ``meta`` keys).  Stops when ``meta.next_cursor`` is None/empty or
        ``max_pages`` is reached.

        Args:
            path:        API path, e.g. ``/works``.
            extra_params: Additional query parameters (filter, select, …).
            per_page:    Results per page (max 200 for OpenAlex).
            max_pages:   Safety cap; None = no cap.
        """
        params: dict[str, Any] = dict(extra_params or {})
        params["per-page"] = per_page
        params["cursor"] = "*"

        page_num = 0
        while True:
            data = self.get(path, **params)
            yield data

            page_num += 1
            if max_pages is not None and page_num >= max_pages:
                logger.info(
                    "Pagination stopped: max_pages reached",
                    extra={"path": path, "page_num": page_num},
                )
                break

            meta = data.get("meta", {})
            next_cursor = meta.get("next_cursor")
            if not next_cursor:
                break

            params["cursor"] = next_cursor
            total = meta.get("count", "?")
            logger.info(
                "Fetched page",
                extra={
                    "path": path,
                    "page": page_num,
                    "results": len(data.get("results", [])),
                    "total": total,
                    "next_cursor": next_cursor[:20] if next_cursor else None,
                },
            )

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def get_source_by_issn(self, issn: str) -> list[dict[str, Any]]:
        """Return OpenAlex sources matching a given ISSN."""
        data = self.get("/sources", filter=f"issn:{issn}")
        return data.get("results", [])

    def search_sources_by_name(self, name: str) -> list[dict[str, Any]]:
        """Return OpenAlex sources matching a journal name search."""
        data = self.get("/sources", search=name, filter="type:journal")
        return data.get("results", [])

    def close(self) -> None:
        self._session.close()


# Module-level singleton (instantiated on first import after config is ready)
_client: OpenAlexClient | None = None


def get_client() -> OpenAlexClient:
    """Return the module-level OpenAlexClient singleton."""
    global _client
    if _client is None:
        _client = OpenAlexClient()
    return _client
