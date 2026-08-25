"""Button entity: ring the Astrion device to help find it, one click, no service call needed."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AstrionConfigEntry
from .api import AstrionApiError
from .const import DEFAULT_RING_DURATION, DEFAULT_RING_VOLUME, SOUND_RINGTONE
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion ring button.

    `hass` is unused here but kept for the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AstrionRingButton(coordinator)])


class AstrionRingButton(CoordinatorEntity[AstrionCoordinator], ButtonEntity):
    """'Find my remote' button — rings the device at fixed default settings.

    This is the one-click complement to the `astrion.ring` service, not a
    replacement for it: this button has no way to take parameters, so it
    always rings at DEFAULT_RING_VOLUME/SOUND_RINGTONE/DEFAULT_RING_DURATION
    (see const.py). Reaching for a specific volume, sound, or duration — or
    for targeting one device out of several — still means calling the
    service; this is just for the "quick tap on the dashboard" case.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "ring"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Initialize the ring button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-ring"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Ring the device at the default volume/sound/duration."""
        try:
            await self.coordinator.client.async_ring(
                DEFAULT_RING_VOLUME, SOUND_RINGTONE, DEFAULT_RING_DURATION
            )
        except AstrionApiError as err:
            raise HomeAssistantError(f"Astrion device unreachable: {err}") from err
