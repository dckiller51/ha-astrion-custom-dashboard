"""Tests for several remotes in one home (Astrion 1.2.7+, integration 2026.10.0).

Identity from /info, migration of "host:port" entries, following a new IP,
reconfigure / replacement, and the webhook's battery and button pushes.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.astrion import _async_follow_new_address
from custom_components.astrion.api import AstrionInfo, AstrionPage
from custom_components.astrion.const import (
    CONF_ENTITY_PREFIX,
    DOMAIN,
    EVENT_ASTRION,
    NAME,
    UPDATE_INTERVAL_PUSH_SECONDS,
)

from .test_config_flow import VALID_INPUT, _mock_reachable_device

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

PAGES = [AstrionPage(index=0, name="Main")]
LIVING = AstrionInfo(id="astrion-0123456789abcdef", name="Living room", model="HA100")


async def _add_via_flow(hass: HomeAssistant, info: AstrionInfo | None) -> Any:
    with _mock_reachable_device(PAGES, info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_INPUT
        )
        await hass.async_block_till_done()
    return result


async def test_flow_uses_remote_identity(hass: HomeAssistant) -> None:
    """With /info, the entry is keyed and named after the remote."""
    result = await _add_via_flow(hass, LIVING)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == LIVING.id
    assert entry.data[CONF_ENTITY_PREFIX] == LIVING.id


async def test_flow_without_info_keeps_host_port(hass: HomeAssistant) -> None:
    """An app older than 1.2.7 is still keyed on host:port, as before."""
    result = await _add_via_flow(hass, None)

    assert result["title"] == NAME
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "10.0.0.5:8080"
    assert entry.data[CONF_ENTITY_PREFIX] == "10.0.0.5:8080"


async def test_readding_moved_remote_updates_its_address(hass: HomeAssistant) -> None:
    """Adding a known remote again from its new IP just moves the existing entry."""
    await _add_via_flow(hass, LIVING)
    with _mock_reachable_device(PAGES, LIVING):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "10.0.0.9", CONF_PORT: 8080}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == "10.0.0.9"


async def test_legacy_entry_migrates_and_adopts_identity(hass: HomeAssistant) -> None:
    """A host:port entry keeps its entities while switching to the remote's id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        unique_id="10.0.0.5:8080",
        data={**VALID_INPUT, CONF_WEBHOOK_ID: "hook"},
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    with _mock_reachable_device(PAGES, LIVING):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data[CONF_ENTITY_PREFIX] == "10.0.0.5:8080"
    assert entry.unique_id == LIVING.id
    assert entry.title == "Living room"
    unique_ids = {
        e.unique_id
        for e in er.async_get(hass).entities.values()
        if e.config_entry_id == entry.entry_id
    }
    assert "10.0.0.5:8080-battery-level" in unique_ids
    assert "10.0.0.5:8080-last-seen" in unique_ids


async def test_reconfigure_to_replacement_remote(hass: HomeAssistant) -> None:
    """Reconfigure points the entry at a new remote without touching its entities."""
    await _add_via_flow(hass, LIVING)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    replacement = AstrionInfo(id="astrion-fedcba9876543210", name="Living room")

    with _mock_reachable_device(PAGES, replacement):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "10.0.0.20", CONF_PORT: 8080}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == replacement.id
    assert entry.data[CONF_HOST] == "10.0.0.20"
    assert entry.data[CONF_ENTITY_PREFIX] == LIVING.id


async def test_webhook_battery_and_button(
    hass: HomeAssistant, hass_client_no_auth: Any
) -> None:
    """Battery pushes update the sensor; button pushes fire astrion_event."""
    assert await async_setup_component(hass, "webhook", {})
    await _add_via_flow(hass, LIVING)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data.coordinator
    client = await hass_client_no_auth()
    url = f"/api/webhook/{entry.data[CONF_WEBHOOK_ID]}"
    remote = {"id": LIVING.id, "name": "Salon"}

    resp = await client.post(
        url, json={"type": "battery", "level": 42, "charging": True, "remote": remote}
    )
    assert resp.status == 200
    await hass.async_block_till_done()
    assert coordinator.data.battery.level == 42
    assert coordinator.data.battery.charging is True
    assert coordinator.update_interval == timedelta(
        seconds=UPDATE_INTERVAL_PUSH_SECONDS
    )
    assert coordinator.last_seen is not None
    device = dr.async_get(hass).async_get_device_by_identifier(
        config_entry_id=entry.entry_id, identifier=(DOMAIN, coordinator.unique_id)
    )
    assert device is not None
    assert device.name == "Salon"

    events: list[Event] = []
    hass.bus.async_listen(EVENT_ASTRION, events.append)
    await client.post(
        url,
        json={
            "type": "button",
            "event": "movie_scene",
            "key": "RED_BUTTON",
            "long": True,
            "page": "Main",
            "remote": remote,
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["device_id"] == device.id
    assert events[0].data["event"] == "movie_scene"
    assert events[0].data["long"] is True
    assert events[0].data["remote_name"] == "Salon"


async def test_info_with_webhook_slows_polling_from_start(hass: HomeAssistant) -> None:
    """A 1.2.7+ remote that reports a webhook set is polled every 5 minutes at once."""
    await _add_via_flow(hass, AstrionInfo(id=LIVING.id, name=LIVING.name, webhook=True))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data.coordinator
    assert coordinator.push_confirmed
    assert coordinator.update_interval == timedelta(
        seconds=UPDATE_INTERVAL_PUSH_SECONDS
    )


async def test_follow_new_address_checks_identity(hass: HomeAssistant) -> None:
    """A push from a new private IP moves the entry only if /info there matches."""
    await _add_via_flow(hass, LIVING)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    other = AstrionInfo(id="astrion-somebody-else", name="Bedroom")
    with patch(
        "custom_components.astrion.api.AstrionClient.async_get_info",
        AsyncMock(return_value=other),
    ):
        await _async_follow_new_address(hass, entry, "10.0.0.33")
    assert entry.data[CONF_HOST] == "10.0.0.5"

    await _async_follow_new_address(hass, entry, "127.0.0.1")
    assert entry.data[CONF_HOST] == "10.0.0.5"

    with _mock_reachable_device(PAGES, LIVING):
        await _async_follow_new_address(hass, entry, "10.0.0.33")
        await hass.async_block_till_done()
    assert entry.data[CONF_HOST] == "10.0.0.33"
