"""Read-only sensor for the Astrion Remote's currently displayed page.

Complements select.page: the select entity both shows and *changes* the
page (a tap on its dropdown navigates the remote), which is exactly what
you want on a dashboard control card but not what you want feeding a
History graph or a Logbook entry, where an accidental option pick would be
a real (if harmless) side effect. This sensor is purely observational.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AstrionConfigEntry
from .coordinator import AstrionCoordinator


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion current-page sensor.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.
    """
    async_add_entities([AstrionCurrentPageSensor(entry.runtime_data)])


class AstrionCurrentPageSensor(CoordinatorEntity[AstrionCoordinator], SensorEntity):
    """The page currently displayed on the remote, read-only."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_page"
    _attr_icon = "mdi:tablet-dashboard"
    _attr_entity_category = None  # a primary state, not a diagnostic value

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-current-page-sensor"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | None:
        """Return the page currently visible on the device."""
        return self.coordinator.data.current_page
