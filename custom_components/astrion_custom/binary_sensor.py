"""Binary sensors: whether the Astrion device is reachable, and whether it's charging."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
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
    """Set up the Astrion connectivity and charging binary sensors.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            AstrionConnectivitySensor(coordinator),
            AstrionChargingSensor(coordinator),
        ]
    )


class AstrionConnectivitySensor(
    CoordinatorEntity[AstrionCoordinator], BinarySensorEntity
):
    """Whether the Astrion device answered the last poll.

    Deliberately overrides `available` to always return True. A
    CoordinatorEntity's default `available` goes unavailable when the last
    refresh failed — exactly backwards for an entity whose entire purpose
    is to report "device unreachable" as an explicit `off` state. Every
    other Astrion entity keeps the default (correctly — a stale page name
    or battery reading really should show as unavailable rather than a
    silently frozen value); this one alone needs to stay visible through
    the very condition it exists to report.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-connectivity"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Always available — see class docstring."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True if the last poll of the device succeeded."""
        return self.coordinator.last_update_success


class AstrionChargingSensor(CoordinatorEntity[AstrionCoordinator], BinarySensorEntity):
    """Whether the tablet running Astrion is currently charging.

    Standard CoordinatorEntity availability here (unlike
    AstrionConnectivitySensor) — if the device is unreachable, we genuinely
    don't know its charging state, so "unavailable" is the honest answer.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Initialize the charging sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-charging"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return True if the tablet is currently charging."""
        return self.coordinator.data.battery.charging
