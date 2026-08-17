"""Minimal client for Astrion's on-device ConfigServer (port 8080).

Talks to the three routes added by the Astrion "remote page control" patch:
GET /pages, GET /current-page, POST /set-page. No auth — same trusted-LAN
assumption Astrion itself makes, see Configserver.kt's own doc comment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=5)


class AstrionApiError(Exception):
    """Raised when the Astrion device can't be reached or returns an error."""


class AstrionPageNotFound(AstrionApiError):
    """Raised when /set-page is asked for a page name the device doesn't have."""


@dataclass
class AstrionPage:
    """One dashboard page, as reported by /pages or /current-page."""

    index: int
    name: str


class AstrionClient:
    """Thin async wrapper around Astrion's local HTTP config server."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, port: int = 8080
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def async_get_pages(self) -> list[AstrionPage]:
        """Return the dashboard's pages, in pager order."""
        data = await self._request("GET", "/pages")
        if not isinstance(data, list):
            raise AstrionApiError(f"Unexpected /pages response: {data!r}")
        return [AstrionPage(index=item["index"], name=item["name"]) for item in data]

    async def async_get_current_page(self) -> AstrionPage | None:
        """Return the page currently visible on the device, if known."""
        data = await self._request("GET", "/current-page")
        if not isinstance(data, dict) or data.get("name") is None:
            return None
        return AstrionPage(index=data["index"], name=data["name"])

    async def async_set_page(self, page: str) -> AstrionPage:
        """Ask the device to jump to the page named `page` (case-insensitive)."""
        data = await self._request("POST", "/set-page", data={"page": page})
        if not isinstance(data, dict) or "name" not in data:
            raise AstrionApiError(f"Unexpected /set-page response: {data!r}")
        return AstrionPage(index=data["index"], name=data["name"])

    async def _request(
        self, method: str, path: str, data: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method, url, data=data, timeout=DEFAULT_TIMEOUT
            ) as response:
                if response.status == 404 and path == "/set-page":
                    payload = await response.json(content_type=None)
                    raise AstrionPageNotFound(payload.get("error", "unknown page"))
                if response.status >= 400:
                    text = await response.text()
                    raise AstrionApiError(
                        f"{method} {path} failed ({response.status}): {text}"
                    )
                return await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise AstrionApiError(f"Could not reach Astrion at {url}: {err}") from err
        except TimeoutError as err:
            raise AstrionApiError(f"Timed out reaching Astrion at {url}") from err
