"""Read-only sensor for the Astrion Remote's currently displayed page.

Complements select.page: the select entity both shows and *changes* the
page (a tap on its dropdown navigates the remote), which is exactly what
you want on a dashboard control card but not what you want feeding a
History graph or a Logbook entry, where an accidental option pick would be
a real (if harmless) side effect. This sensor is purely observational.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import AstrionConfigEntry
from .coordinator import AstrionCoordinator


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion current-page sensor and one active-activity sensor per room.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.

    Rooms aren't known until the first coordinator refresh, and a
    dashboard.json edit can add a room later — so entities for new rooms are
    added as they show up, the same "grow as new items appear" pattern
    integrations like Sonos use for dynamically-discovered players, instead
    of a fixed set created once at startup.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities([AstrionCurrentPageSensor(coordinator)])

    known_rooms: set[str] = set()

    @callback
    def _add_new_room_sensors() -> None:
        new_rooms = [room for room in coordinator.data.rooms if room not in known_rooms]
        if not new_rooms:
            return
        known_rooms.update(new_rooms)
        async_add_entities(
            AstrionActiveActivitySensor(coordinator, room) for room in new_rooms
        )

    _add_new_room_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_room_sensors))


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


class AstrionActiveActivitySensor(CoordinatorEntity[AstrionCoordinator], SensorEntity):
    """Which Activity is currently active in one room, read-only.

    Complements select.activity_<room> the same way sensor.current_page
    complements select.page: the select entity both shows and *changes* the
    room's Activity (a tap on its dropdown starts/stops it), which is fine
    on a dashboard control card but not what you want feeding a History
    graph or Logbook entry, where an accidental option pick would be a real
    (if harmless) side effect. This sensor is purely observational.

    `None` means the room currently has nothing active (Harmony PowerOff,
    or nothing ever started) — distinct from the entity going unavailable,
    which only happens if the coordinator itself fails to reach the device.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "active_activity"
    _attr_icon = "mdi:remote-tv"
    _attr_entity_category = None  # a primary state, not a diagnostic value

    def __init__(self, coordinator: AstrionCoordinator, room: str) -> None:
        """Initialize the sensor entity for one room."""
        super().__init__(coordinator)
        self._room = room
        self._attr_translation_placeholders = {"room": room}
        self._attr_unique_id = (
            f"{coordinator.unique_id}-active-activity-{slugify(room)}"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | None:
        """Return the name of the Activity currently active in this room."""
        active = self.coordinator.data.active_by_room.get(self._room)
        return active.name if active is not None else None
