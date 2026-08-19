"""Select entities: the Astrion Remote's current dashboard page, and which Activity is active in each room."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import AstrionConfigEntry
from .api import (
    AstrionActivity,
    AstrionActivityNotFound,
    AstrionApiError,
    AstrionPageNotFound,
)
from .const import ACTIVITY_OFF_OPTION
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion page select entity and one Activity select per room.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.

    Rooms aren't known until the first coordinator refresh, and a
    dashboard.json edit can add a room later — see sensor.py's own
    `_add_new_room_sensors` for why entities are added as rooms show up
    instead of all at once at startup.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AstrionPageSelect(coordinator)])

    known_rooms: set[str] = set()

    @callback
    def _add_new_room_selects() -> None:
        new_rooms = [room for room in coordinator.data.rooms if room not in known_rooms]
        if not new_rooms:
            return
        known_rooms.update(new_rooms)
        async_add_entities(
            AstrionActivitySelect(coordinator, room) for room in new_rooms
        )

    _add_new_room_selects()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_room_selects))


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


class AstrionActivitySelect(CoordinatorEntity[AstrionCoordinator], SelectEntity):
    """Select entity to start — or stop — the Activity active in one room.

    Complements sensor.active_activity_<room> the same way select.page
    complements sensor.current_page: this one both shows AND changes the
    room's Activity. Includes an explicit "Off" option, which Harmony has
    no per-Activity equivalent for — the hub only ever runs one Activity at
    a time, so "stop" means PowerOff on that Activity's own hub, not a
    global kill switch. See AstrionClient.async_stop_activity's docstring
    for why that's still the narrowest possible stop, not a workaround.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "activity"
    _attr_icon = "mdi:remote-tv"

    def __init__(self, coordinator: AstrionCoordinator, room: str) -> None:
        """Initialize the select entity for one room."""
        super().__init__(coordinator)
        self._room = room
        self._attr_translation_placeholders = {"room": room}
        self._attr_unique_id = f"{coordinator.unique_id}-activity-{slugify(room)}"
        self._attr_device_info = coordinator.device_info

    @property
    def _activities(self) -> list[AstrionActivity]:
        """The Activities available in this room, per the last refresh."""
        return self.coordinator.data.activities_in(self._room)

    @property
    def options(self) -> list[str]:
        """Return this room's Activity names, plus the explicit "Off" option."""
        return [ACTIVITY_OFF_OPTION, *(activity.name for activity in self._activities)]

    @property
    def current_option(self) -> str:
        """Return the name of the Activity active in this room, or "Off"."""
        active = self.coordinator.data.active_by_room.get(self._room)
        return active.name if active is not None else ACTIVITY_OFF_OPTION

    async def async_select_option(self, option: str) -> None:
        """Start the chosen Activity, or stop whatever's running if "Off" was picked."""
        if option == ACTIVITY_OFF_OPTION:
            try:
                await self.coordinator.client.async_stop_activity(self._room)
            except AstrionApiError as err:
                raise HomeAssistantError(f"Astrion device unreachable: {err}") from err
            await self.coordinator.async_request_refresh()
            return

        activity = next((a for a in self._activities if a.name == option), None)
        if activity is None:
            raise HomeAssistantError(
                f"Unknown activity '{option}' in room '{self._room}'"
            )
        try:
            await self.coordinator.client.async_start_activity(activity.id)
        except AstrionActivityNotFound as err:
            raise HomeAssistantError(str(err)) from err
        except AstrionApiError as err:
            raise HomeAssistantError(f"Astrion device unreachable: {err}") from err
        await self.coordinator.async_request_refresh()
