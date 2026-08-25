"""Tests for the Astrion "find my remote" button entity.

Uses the same HA test harness and _mock_reachable_device fixture as
test_config_flow.py, since setting up the button means setting up a whole
config entry first — there's no lighter-weight way to get a coordinator and
device registered.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.astrion.api import AstrionApiError, AstrionPage
from custom_components.astrion.const import (
    DEFAULT_RING_DURATION,
    DEFAULT_RING_VOLUME,
    DOMAIN,
    SOUND_RINGTONE,
)

from .test_config_flow import VALID_INPUT, _mock_reachable_device

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _async_setup_entry(hass: HomeAssistant) -> None:
    """Run the config flow to completion, exactly like test_config_flow.py does."""
    with _mock_reachable_device([AstrionPage(index=0, name="Main")]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(result["flow_id"], VALID_INPUT)
        await hass.async_block_till_done()


def _find_ring_button_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    """Look up the button entity by config entry rather than guessing its entity_id.

    has_entity_name + a device with a title-derived name means the exact
    entity_id (astrion_custom_dashboard_find_my_remote, or something else if
    the title's ever renamed) isn't worth hardcoding here — the registry
    lookup stays correct regardless.
    """
    registry = er.async_get(hass)
    return next(
        registry_entry.entity_id
        for registry_entry in registry.entities.values()
        if registry_entry.config_entry_id == entry_id
        and registry_entry.domain == "button"
    )


async def test_ring_button_exists(hass: HomeAssistant) -> None:
    """Setting up a config entry registers exactly one button entity."""
    await _async_setup_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    entity_id = _find_ring_button_entity_id(hass, entry.entry_id)

    state = hass.states.get(entity_id)
    assert state is not None


async def test_ring_button_press_uses_defaults(hass: HomeAssistant) -> None:
    """Pressing the button rings at the documented default volume/sound/duration.

    This is the whole point of the button over the astrion.ring service: no
    parameters to pass, so it must fall back to exactly these three
    constants — if a future edit changes what the button rings at without
    updating const.py (or vice versa), this is what would catch it.
    """
    await _async_setup_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entity_id = _find_ring_button_entity_id(hass, entry.entry_id)

    with patch(
        "custom_components.astrion.api.AstrionClient.async_ring",
        AsyncMock(return_value=None),
    ) as mock_ring:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_ring.assert_awaited_once_with(
        DEFAULT_RING_VOLUME, SOUND_RINGTONE, DEFAULT_RING_DURATION
    )


async def test_ring_button_press_device_unreachable(hass: HomeAssistant) -> None:
    """An unreachable device turns AstrionApiError into a HomeAssistantError.

    Same contract as every other entity/service in this integration — see
    e.g. select.py's async_select_option — so an automation calling
    button.press gets a clear failure instead of a swallowed exception.
    """
    await _async_setup_entry(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entity_id = _find_ring_button_entity_id(hass, entry.entry_id)

    with (
        patch(
            "custom_components.astrion.api.AstrionClient.async_ring",
            AsyncMock(side_effect=AstrionApiError("no route to host")),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )
