"""Select entity to pick/read the Astrion Remote's current dashboard page."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AstrionConfigEntry
from .api import AstrionApiError, AstrionPageNotFound
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion page select entity.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.
    """
    async_add_entities([AstrionPageSelect(entry.runtime_data)])


class AstrionPageSelect(CoordinatorEntity[AstrionCoordinator], SelectEntity):
    """Select representation of Astrion's swipeable dashboard pages."""

    _attr_has_entity_name = True
    _attr_translation_key = "page"
    _attr_icon = "mdi:tablet-dashboard"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-page"
        self._attr_device_info = coordinator.device_info

    @property
    def options(self) -> list[str]:
        """Return the dashboard's page names, in pager order."""
        return self.coordinator.data.page_names

    @property
    def current_option(self) -> str | None:
        """Return the page currently visible on the device."""
        return self.coordinator.data.current_page

    async def async_select_option(self, option: str) -> None:
        """Ask the device to jump to this page."""
        try:
            await self.coordinator.client.async_set_page(option)
        except AstrionPageNotFound as err:
            raise HomeAssistantError(str(err)) from err
        except AstrionApiError as err:
            raise HomeAssistantError(f"Astrion device unreachable: {err}") from err
        await self.coordinator.async_request_refresh()
