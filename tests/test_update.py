"""Tests for AstrionUpdateCoordinator — the GitHub-release-checking half of update.py.

Uses the HA test harness (hass + aioclient_mock), unlike
test_api.py, because AstrionUpdateCoordinator is a DataUpdateCoordinator and
talks to GitHub through Home Assistant's own shared aiohttp client session
rather than a session we control directly.
"""

from __future__ import annotations

import pytest

from custom_components.astrion.const import APK_RELEASES_API_URL
from custom_components.astrion.update import (
    AstrionLatestRelease,
    AstrionUpdateCoordinator,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_latest_release_strips_v_prefix(hass, aioclient_mock) -> None:
    """A "v0.9.1" GitHub tag compares cleanly against /version's unprefixed value."""
    release_url = (
        "https://github.com/dckiller51/astrion-custom-dashboard/releases/tag/v0.9.1"
    )
    aioclient_mock.get(
        APK_RELEASES_API_URL,
        json={"tag_name": "v0.9.1", "html_url": release_url},
    )
    coordinator = AstrionUpdateCoordinator(hass)

    await coordinator.async_refresh()

    assert coordinator.data == AstrionLatestRelease(
        version="0.9.1", release_url=release_url
    )


async def test_latest_release_without_v_prefix(hass, aioclient_mock) -> None:
    """A bare "0.9.1" tag (no "v") is used as-is, not mangled by the strip."""
    release_url = (
        "https://github.com/dckiller51/astrion-custom-dashboard/releases/tag/0.9.1"
    )
    aioclient_mock.get(
        APK_RELEASES_API_URL,
        json={"tag_name": "0.9.1", "html_url": release_url},
    )
    coordinator = AstrionUpdateCoordinator(hass)

    await coordinator.async_refresh()

    assert coordinator.data == AstrionLatestRelease(
        version="0.9.1", release_url=release_url
    )


async def test_latest_release_soft_fails_on_http_error(hass, aioclient_mock) -> None:
    """A GitHub outage doesn't raise — just no data this cycle, tried again next interval."""
    aioclient_mock.get(APK_RELEASES_API_URL, status=503)
    coordinator = AstrionUpdateCoordinator(hass)

    await coordinator.async_refresh()

    assert coordinator.data is None
    # Soft-fail, not a failed refresh: _async_update_data never raises for
    # an HTTP error, it returns None — see the coordinator's own doc
    # comment for why that distinction matters here specifically.
    assert coordinator.last_update_success is True


async def test_latest_release_soft_fails_on_malformed_payload(
    hass, aioclient_mock
) -> None:
    """A 200 response missing tag_name/html_url is treated the same as an outage."""
    aioclient_mock.get(APK_RELEASES_API_URL, json={"unexpected": "shape"})
    coordinator = AstrionUpdateCoordinator(hass)

    await coordinator.async_refresh()

    assert coordinator.data is None
    assert coordinator.last_update_success is True
