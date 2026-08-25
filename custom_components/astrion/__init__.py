"""The Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AstrionActivityNotFound,
    AstrionApiError,
    AstrionClient,
    AstrionPageNotFound,
)
from .const import (
    ATTR_ACTIVITY_ID,
    ATTR_DEVICE_ID,
    ATTR_DURATION,
    ATTR_PAGE,
    ATTR_ROOM,
    ATTR_SOUND,
    ATTR_VOLUME,
    DEFAULT_RING_DURATION,
    DEFAULT_RING_VOLUME,
    DOMAIN,
    PLATFORMS,
    RING_SOUNDS,
    SERVICE_RING,
    SERVICE_SET_PAGE,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    SOUND_RINGTONE,
    STARTUP_MESSAGE,
)
from .coordinator import AstrionCoordinator

# Only for static type checking (Pylance, mypy) — a real module-level import
# would circle back, since update.py itself does `from . import
# AstrionConfigEntry`. async_setup_entry() below does the real import,
# locally, once this module is already fully initialized.
if TYPE_CHECKING:
    from .update import AstrionUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class AstrionRuntimeData:
    """Everything one config entry needs at runtime.

    Two coordinators, not one — `coordinator` polls the device itself
    (fast, local), `update_coordinator` checks GitHub for the latest APK
    release (slow, remote, rate-limited). See update.py's own doc comment
    for why they're kept separate rather than one coordinator doing both.
    """

    coordinator: AstrionCoordinator
    update_coordinator: AstrionUpdateCoordinator


type AstrionConfigEntry = ConfigEntry[AstrionRuntimeData]

SET_PAGE_SCHEMA = vol.Schema({vol.Required(ATTR_PAGE): cv.string})
START_ACTIVITY_SCHEMA = vol.Schema({vol.Required(ATTR_ACTIVITY_ID): cv.string})
STOP_ACTIVITY_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})
RING_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_VOLUME, default=DEFAULT_RING_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(ATTR_SOUND, default=SOUND_RINGTONE): vol.In(RING_SOUNDS),
        vol.Optional(ATTR_DURATION, default=DEFAULT_RING_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
        # Omitted = every configured Astrion device, same as before this was
        # added. Given as its own field rather than relying on ServiceCall's
        # built-in `target:` handling, since that's only wired up
        # automatically for entity-domain services — this is a domain-level
        # service with no entity of its own to target.
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Set up Astrion Custom Dashboard from a config entry."""
    # Imported here, not at module level, to avoid a circular import
    # (update.py imports AstrionConfigEntry from this module).
    from .update import (  # pylint: disable=import-outside-toplevel
        AstrionUpdateCoordinator,
    )

    if DOMAIN not in hass.data:
        # Logged once per HA run, not once per configured device — matches
        # the usual custom-component-blueprint pattern of a single banner
        # in the log pointing at the issue tracker.
        _LOGGER.info(STARTUP_MESSAGE)
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = AstrionClient(session, entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = AstrionCoordinator(
        hass, client, entry.unique_id or entry.entry_id, entry.title
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AstrionRuntimeData(
        coordinator=coordinator,
        update_coordinator=AstrionUpdateCoordinator(hass),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # DeviceInfo.sw_version is the installed Astrion app's own version,
    # only known now that the first /version fetch succeeded — set once
    # here (after the entities above have registered the device via their
    # own device_info) rather than kept live on every coordinator refresh,
    # matching how most integrations only reflect firmware version changes
    # after a reload rather than wiring up a listener for something that
    # changes about as often as the user updates the APK.
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, coordinator.unique_id)}
    )
    if device is not None:
        device_registry.async_update_device(
            device.id, sw_version=coordinator.data.installed_version
        )

    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_target_entries(
    hass: HomeAssistant, device_id: str | None
) -> list[AstrionConfigEntry]:
    """Resolve a service call's optional `device_id` to config entries.

    `device_id` omitted -> every configured Astrion device (the fan-out the
    other services here always use). `device_id` given -> just the entry
    that device belongs to, so `ring` can target one specific remote in a
    multi-device home instead of ringing all of them at once.
    """
    if device_id is None:
        return list(hass.config_entries.async_entries(DOMAIN))

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Unknown device_id: {device_id}")

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in device.config_entries
    ]
    if not entries:
        raise HomeAssistantError(f"Device {device_id} is not an Astrion device")
    return entries


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the astrion.* services (idempotent)."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PAGE):

        async def _async_set_page(call: ServiceCall) -> None:
            page = call.data[ATTR_PAGE]
            # Applies to every configured Astrion device — mirrors calling
            # select.select_option on every astrion select entity, but lets an
            # automation target by page name without knowing the entity_id.
            for entry in hass.config_entries.async_entries(DOMAIN):
                coordinator = entry.runtime_data.coordinator
                try:
                    await coordinator.client.async_set_page(page)
                except AstrionPageNotFound as err:
                    raise HomeAssistantError(str(err)) from err
                except AstrionApiError as err:
                    raise HomeAssistantError(
                        f"Astrion device for entry {entry.title} unreachable: {err}"
                    ) from err
                await coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN, SERVICE_SET_PAGE, _async_set_page, schema=SET_PAGE_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, SERVICE_START_ACTIVITY):

        async def _async_start_activity(call: ServiceCall) -> None:
            activity_id = call.data[ATTR_ACTIVITY_ID]
            # Same "every configured device" fan-out as set_page — a no-op
            # for devices that don't have an Activity with this id, since
            # activity ids are only unique within one device's dashboard.json.
            for entry in hass.config_entries.async_entries(DOMAIN):
                coordinator = entry.runtime_data.coordinator
                if not any(a.id == activity_id for a in coordinator.data.activities):
                    continue
                try:
                    await coordinator.client.async_start_activity(activity_id)
                except AstrionActivityNotFound as err:
                    raise HomeAssistantError(str(err)) from err
                except AstrionApiError as err:
                    raise HomeAssistantError(
                        f"Astrion device for entry {entry.title} unreachable: {err}"
                    ) from err
                await coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_START_ACTIVITY,
            _async_start_activity,
            schema=START_ACTIVITY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_STOP_ACTIVITY):

        async def _async_stop_activity(call: ServiceCall) -> None:
            room = call.data[ATTR_ROOM]
            # Same fan-out again, skipping devices with no such room —
            # room names are only unique within one device's dashboard.json.
            for entry in hass.config_entries.async_entries(DOMAIN):
                coordinator = entry.runtime_data.coordinator
                if room not in coordinator.data.rooms:
                    continue
                try:
                    await coordinator.client.async_stop_activity(room)
                except AstrionApiError as err:
                    raise HomeAssistantError(
                        f"Astrion device for entry {entry.title} unreachable: {err}"
                    ) from err
                await coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_ACTIVITY,
            _async_stop_activity,
            schema=STOP_ACTIVITY_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_RING):

        async def _async_ring(call: ServiceCall) -> None:
            volume = call.data[ATTR_VOLUME]
            sound = call.data[ATTR_SOUND]
            duration = call.data[ATTR_DURATION]
            device_id = call.data.get(ATTR_DEVICE_ID)
            # Rings every configured device unless `device_id` narrows it to
            # one — see _async_target_entries above.
            for entry in _async_target_entries(hass, device_id):
                coordinator = entry.runtime_data.coordinator
                try:
                    await coordinator.client.async_ring(volume, sound, duration)
                except AstrionApiError as err:
                    raise HomeAssistantError(
                        f"Astrion device for entry {entry.title} unreachable: {err}"
                    ) from err

        hass.services.async_register(
            DOMAIN, SERVICE_RING, _async_ring, schema=RING_SCHEMA
        )
