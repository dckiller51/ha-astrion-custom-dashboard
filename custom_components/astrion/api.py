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


class AstrionActivityNotFound(AstrionApiError):
    """Raised when /activities/start gets an unknown id, or /activities/stop an unknown room."""


@dataclass
class AstrionPage:
    """One dashboard page, as reported by /pages or /current-page."""

    index: int
    name: str


@dataclass
class AstrionVersion:
    """The installed app's own version, as reported by /version."""

    version: str
    version_code: int


@dataclass
class AstrionActivity:
    """One trackable Activity, as reported by /activities.

    Mirrors Astrion's own `TrackedActivity` — a composed Activity defined in
    the dashboard builder, or a lightweight `"track": true` tile/hotkey
    (which may or may not be backed by an actual Harmony Activity). Astrion
    treats both uniformly, so this integration does too.
    """

    id: str
    name: str
    room: str
    icon: str | None = None


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

    async def async_get_version(self) -> AstrionVersion:
        """Return the installed app's own version."""
        data = await self._request("GET", "/version")
        if not isinstance(data, dict):
            raise AstrionApiError(f"Unexpected /version response: {data!r}")
        return AstrionVersion(version=data["version"], version_code=data["versionCode"])

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

    async def async_get_activities(self) -> list[AstrionActivity]:
        """Return every trackable Activity, in Astrion's own declaration order."""
        data = await self._request("GET", "/activities")
        if not isinstance(data, list):
            raise AstrionApiError(f"Unexpected /activities response: {data!r}")
        return [
            AstrionActivity(
                id=item["id"],
                name=item["name"],
                room=item["room"],
                icon=item.get("icon"),
            )
            for item in data
        ]

    async def async_get_active_activities(self) -> dict[str, AstrionActivity | None]:
        """Return the Activity currently active in each room (None if off)."""
        data = await self._request("GET", "/activities/active")
        if not isinstance(data, dict):
            raise AstrionApiError(f"Unexpected /activities/active response: {data!r}")
        result: dict[str, AstrionActivity | None] = {}
        for room, value in data.items():
            if value is None:
                result[room] = None
            else:
                result[room] = AstrionActivity(
                    id=value["id"], name=value["name"], room=room
                )
        return result

    async def async_start_activity(self, activity_id: str) -> None:
        """Start an Activity by id — the remote-control counterpart of tapping its tile."""
        await self._request("POST", "/activities/start", data={"id": activity_id})

    async def async_stop_activity(self, room: str) -> None:
        """Stop whichever Activity is active in `room`, without starting another.

        For a Harmony-backed Activity, Astrion sends PowerOff to that
        Activity's own hub only — Harmony has no per-Activity stop command,
        a hub always runs exactly one Activity, so this is the narrowest
        possible "stop" and never touches a different room's hub, unlike a
        blanket "turn everything off" button.
        """
        await self._request("POST", "/activities/stop", data={"room": room})

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
                if response.status == 404 and path in (
                    "/activities/start",
                    "/activities/stop",
                ):
                    payload = await response.json(content_type=None)
                    raise AstrionActivityNotFound(
                        payload.get("error", "unknown activity or room")
                    )
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
