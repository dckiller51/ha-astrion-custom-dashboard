"""The Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AstrionActivityNotFound,
    AstrionApiError,
    AstrionClient,
    AstrionPageNotFound,
)
from .const import (
    ATTR_ACTIVITY_ID,
    ATTR_PAGE,
    ATTR_ROOM,
    DOMAIN,
    PLATFORMS,
    SERVICE_SET_PAGE,
    SERVICE_START_ACTIVITY,
    SERVICE_STOP_ACTIVITY,
    STARTUP_MESSAGE,
)
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)

type AstrionConfigEntry = ConfigEntry[AstrionCoordinator]

SET_PAGE_SCHEMA = vol.Schema({vol.Required(ATTR_PAGE): cv.string})
START_ACTIVITY_SCHEMA = vol.Schema({vol.Required(ATTR_ACTIVITY_ID): cv.string})
STOP_ACTIVITY_SCHEMA = vol.Schema({vol.Required(ATTR_ROOM): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Set up Astrion Custom Dashboard from a config entry."""
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

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the astrion.* services (idempotent)."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PAGE):

        async def _async_set_page(call: ServiceCall) -> None:
            page = call.data[ATTR_PAGE]
            # Applies to every configured Astrion device — mirrors calling
            # select.select_option on every astrion select entity, but lets an
            # automation target by page name without knowing the entity_id.
            for entry in hass.config_entries.async_entries(DOMAIN):
                coordinator: AstrionCoordinator = entry.runtime_data
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
                coordinator: AstrionCoordinator = entry.runtime_data
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
                coordinator: AstrionCoordinator = entry.runtime_data
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
