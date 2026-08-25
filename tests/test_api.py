"""Unit tests for AstrionClient.

Pure asyncio/aiohttp-mock tests — no Home Assistant test harness needed,
so these run under any Python/HA version, unlike the config_flow tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.astrion.api import (
    AstrionActivity,
    AstrionActivityNotFound,
    AstrionApiError,
    AstrionClient,
    AstrionPage,
    AstrionPageNotFound,
    AstrionVersion,
)


def _fake_session(status: int, payload: Any) -> MagicMock:
    """Build a ClientSession mock whose .request() yields one canned response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=payload)
    response.text = AsyncMock(return_value=str(payload))

    @asynccontextmanager
    async def _request(*_args: Any, **_kwargs: Any) -> AsyncIterator[MagicMock]:
        yield response

    session = MagicMock()
    session.request = _request
    return session


@pytest.mark.asyncio
async def test_async_get_pages() -> None:
    """async_get_pages parses the /pages array into AstrionPage objects."""
    session = _fake_session(
        200, [{"index": 0, "name": "Lights"}, {"index": 1, "name": "Main"}]
    )
    client = AstrionClient(session, "10.0.0.5")

    pages = await client.async_get_pages()

    assert pages == [
        AstrionPage(index=0, name="Lights"),
        AstrionPage(index=1, name="Main"),
    ]


@pytest.mark.asyncio
async def test_async_get_current_page() -> None:
    """async_get_current_page parses the /current-page object."""
    session = _fake_session(200, {"index": 1, "name": "Main"})
    client = AstrionClient(session, "10.0.0.5")

    page = await client.async_get_current_page()

    assert page == AstrionPage(index=1, name="Main")


@pytest.mark.asyncio
async def test_async_get_current_page_unknown() -> None:
    """A device that hasn't rendered a page yet reports name=None -> None."""
    session = _fake_session(200, {"index": None, "name": None})
    client = AstrionClient(session, "10.0.0.5")

    assert await client.async_get_current_page() is None


@pytest.mark.asyncio
async def test_async_set_page_success() -> None:
    """async_set_page returns the page the device actually switched to."""
    session = _fake_session(200, {"status": "ok", "index": 2, "name": "Media"})
    client = AstrionClient(session, "10.0.0.5")

    page = await client.async_set_page("media")

    assert page == AstrionPage(index=2, name="Media")


@pytest.mark.asyncio
async def test_async_set_page_not_found() -> None:
    """An unknown page name raises AstrionPageNotFound, not a generic error."""
    session = _fake_session(404, {"error": "no page named 'Nope'"})
    client = AstrionClient(session, "10.0.0.5")

    with pytest.raises(AstrionPageNotFound, match="Nope"):
        await client.async_set_page("Nope")


@pytest.mark.asyncio
async def test_async_get_pages_server_error() -> None:
    """A 5xx response raises the generic AstrionApiError."""
    session = _fake_session(500, "boom")
    client = AstrionClient(session, "10.0.0.5")

    with pytest.raises(AstrionApiError):
        await client.async_get_pages()


@pytest.mark.asyncio
async def test_async_get_activities() -> None:
    """async_get_activities parses the /activities array into AstrionActivity objects."""
    session = _fake_session(
        200,
        [
            {
                "id": "watch_appletv",
                "name": "Watch Apple TV",
                "room": "Salon",
                "icon": None,
            },
            {
                "id": "listen_spotify",
                "name": "Listen Spotify",
                "room": "Cuisine",
                "icon": "mdi:music",
            },
        ],
    )
    client = AstrionClient(session, "10.0.0.5")

    activities = await client.async_get_activities()

    assert activities == [
        AstrionActivity(
            id="watch_appletv", name="Watch Apple TV", room="Salon", icon=None
        ),
        AstrionActivity(
            id="listen_spotify", name="Listen Spotify", room="Cuisine", icon="mdi:music"
        ),
    ]


@pytest.mark.asyncio
async def test_async_get_active_activities() -> None:
    """async_get_active_activities parses per-room state, including a room that's off."""
    session = _fake_session(
        200,
        {
            "Salon": {"id": "watch_appletv", "name": "Watch Apple TV"},
            "Cuisine": None,
        },
    )
    client = AstrionClient(session, "10.0.0.5")

    active = await client.async_get_active_activities()

    assert active["Salon"] == AstrionActivity(
        id="watch_appletv", name="Watch Apple TV", room="Salon"
    )
    assert active["Cuisine"] is None


@pytest.mark.asyncio
async def test_async_stop_activity_unknown_room() -> None:
    """An unknown room raises AstrionActivityNotFound, not a generic error."""
    session = _fake_session(404, {"error": "no such room 'Nope'"})
    client = AstrionClient(session, "10.0.0.5")

    with pytest.raises(AstrionActivityNotFound, match="Nope"):
        await client.async_stop_activity("Nope")


@pytest.mark.asyncio
async def test_async_start_activity_unknown_id() -> None:
    """An unknown activity id raises AstrionActivityNotFound, not a generic error."""
    session = _fake_session(404, {"error": "no activity with id 'nope'"})
    client = AstrionClient(session, "10.0.0.5")

    with pytest.raises(AstrionActivityNotFound, match="nope"):
        await client.async_start_activity("nope")


@pytest.mark.asyncio
async def test_async_get_version() -> None:
    """async_get_version parses /version into an AstrionVersion."""
    session = _fake_session(200, {"version": "0.9.0", "versionCode": 9})
    client = AstrionClient(session, "10.0.0.5")

    version = await client.async_get_version()

    assert version == AstrionVersion(version="0.9.0", version_code=9)


@pytest.mark.asyncio
async def test_async_ring_posts_form_fields() -> None:
    """async_ring forwards volume/sound/duration as POST form fields."""
    session = _fake_session(200, {"status": "ringing"})
    client = AstrionClient(session, "10.0.0.5")

    # Doesn't raise — the happy path just needs to reach the device.
    await client.async_ring(volume=50, sound="alarm", duration=10)


@pytest.mark.asyncio
async def test_async_ring_unknown_sound() -> None:
    """An unknown `sound` value the device rejects raises AstrionApiError."""
    session = _fake_session(400, {"error": "unknown sound 'nope'"})
    client = AstrionClient(session, "10.0.0.5")

    with pytest.raises(AstrionApiError):
        await client.async_ring(volume=50, sound="nope", duration=10)
