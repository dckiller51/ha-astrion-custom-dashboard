"""The Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from functools import partial
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aiohttp.web import Request
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AstrionActivity,
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
from .coordinator import AstrionCoordinator, AstrionData

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

SET_PAGE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_PAGE): cv.string, vol.Optional(ATTR_DEVICE_ID): cv.string}
)
START_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ACTIVITY_ID): cv.string,
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)
STOP_ACTIVITY_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ROOM): cv.string, vol.Optional(ATTR_DEVICE_ID): cv.string}
)
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

    # Optional: instant push (current page, active Activity per room) instead
    # of only ever finding out on the next poll. webhook_id is generated once
    # by config_flow.py at setup and shown there for the person to paste into
    # Astrion's own web configurator — see coordinator.py's docstring for why
    # polling stays on regardless (it's the reliable fallback, this is the
    # nice-to-have speedup).
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if webhook_id:
        webhook.async_register(
            hass,
            DOMAIN,
            "Astrion push",
            webhook_id,
            _make_webhook_handler(coordinator),
            allowed_methods=["POST"],
        )
        coordinator.has_push_webhook = True
        _LOGGER.debug(
            "Astrion webhook registered: %s (all registered ids now: %s)",
            webhook_id,
            list(hass.data.get("webhook", {}).keys()),
        )
    else:
        # Entries created before this feature existed never got a
        # CONF_WEBHOOK_ID written to entry.data — silently skipping
        # registration here (as the old code did) is indistinguishable from
        # "registered fine, HA just hasn't been pushed to yet", which made a
        # report of "push isn't instant" nearly undiagnosable. Re-adding the
        # integration (or any entry.data update, e.g. via the options flow's
        # "regenerate") mints one; there's no automatic migration for an
        # entry that's just sitting there with the field missing.
        _LOGGER.debug(
            "Astrion: no CONF_WEBHOOK_ID on this entry, push webhook not registered"
        )
    # Reload if options.py's "regenerate webhook id" ever updates entry.data —
    # that's the only thing that changes post-setup here, so an unconditional
    # reload is fine (re-registers under the new id; async_unload_entry below
    # drops the old one first).
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # DeviceInfo.sw_version is the installed Astrion app's own version,
    # only known now that the first /version fetch succeeded — set once
    # here (after the entities above have registered the device via their
    # own device_info) rather than kept live on every coordinator refresh,
    # matching how most integrations only reflect firmware version changes
    # after a reload rather than wiring up a listener for something that
    # changes about as often as the user updates the APK.
    #
    # Best-effort and non-fatal on purpose: this is purely cosmetic (the
    # displayed firmware version), so a device_registry API mismatch here
    # must never take down setup for the rest of the integration (webhook
    # registration, coordinator, entities) — it already has once, when this
    # lookup's signature changed out from under a HA core update.
    try:
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device_by_identifier(
            config_entry_id=entry.entry_id, identifier=(DOMAIN, coordinator.unique_id)
        )
        if device is not None:
            device_registry.async_update_device(
                device.id, sw_version=coordinator.data.installed_version
            )
    except Exception:  # pylint: disable=broad-exception-caught
        _LOGGER.exception(
            "Failed to sync installed_version onto the device registry entry"
        )

    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Unload a config entry."""
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if webhook_id:
        webhook.async_unregister(hass, webhook_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> None:
    """Reload this entry (e.g. after the options flow regenerates the webhook id)."""
    await hass.config_entries.async_reload(entry.entry_id)


def _make_webhook_handler(
    coordinator: AstrionCoordinator,
) -> Callable[[HomeAssistant, str, Request], Coroutine[Any, Any, None]]:
    """Bind the webhook handler to this entry's own coordinator via closure.

    One handler per entry (registered under that entry's own webhook_id), so
    there's no id -> entry lookup needed at request time.
    """

    async def _handle_webhook(
        _hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Apply a push from Astrion instantly instead of waiting for the next poll.

        Payload shapes (see Astrion's `HaClient.pushWebhook` call sites):
          {"type": "page", "index": <int>, "name": "<str>"}
          {"type": "activity", "rooms": {"<room>": {"id": "...", "name": "..."} | null}}
        Anything else — malformed JSON or an unrecognized "type" — is
        silently ignored; this is a nice-to-have speedup, never the only
        way this data arrives (the regular poll corrects anything it misses).
        `coordinator.data` is never None by the time this can run: the
        webhook isn't registered until after the coordinator's first
        refresh succeeds (async_setup_entry would have raised
        ConfigEntryNotReady and never gotten this far otherwise).
        """
        data = coordinator.data
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.debug("Astrion webhook %s: invalid JSON body, ignoring", webhook_id)
            return

        kind = payload.get("type") if isinstance(payload, dict) else None
        if kind == "page":
            _apply_page_push(coordinator, data, payload)
            _LOGGER.debug(
                "Astrion webhook %s: applied page push %r", webhook_id, payload
            )
        elif kind == "activity":
            _apply_activity_push(coordinator, data, payload)
            _LOGGER.debug(
                "Astrion webhook %s: applied activity push %r", webhook_id, payload
            )
        else:
            _LOGGER.debug(
                "Astrion webhook %s: unknown type %r, ignoring", webhook_id, kind
            )

    return _handle_webhook


def _apply_page_push(
    coordinator: AstrionCoordinator, data: AstrionData, payload: dict
) -> None:
    """Handle a `{"type": "page", ...}` push."""
    coordinator.async_set_updated_data(
        replace(data, current_page=payload.get("name") or None)
    )


def _apply_activity_push(
    coordinator: AstrionCoordinator, data: AstrionData, payload: dict
) -> None:
    """Handle a `{"type": "activity", "rooms": {...}}` push."""
    rooms_payload = payload.get("rooms")
    if not isinstance(rooms_payload, dict):
        return
    by_id = {activity.id: activity for activity in data.activities}
    active_by_room = dict(data.active_by_room)
    for room, value in rooms_payload.items():
        if value is None:
            active_by_room[room] = None
            continue
        if not isinstance(value, dict):
            continue
        activity_id = value.get("id")
        if not activity_id:
            continue
        activity_id = str(activity_id)
        # Prefer the already-known Activity (keeps its icon etc.); fall back to
        # a minimal one built from the push itself for an id the last poll
        # doesn't know about yet (e.g. dashboard.json changed since then).
        active_by_room[room] = by_id.get(activity_id) or AstrionActivity(
            id=activity_id, name=str(value.get("name") or activity_id), room=room
        )
    coordinator.async_set_updated_data(replace(data, active_by_room=active_by_room))


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


async def _async_set_page(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle astrion.set_page — see services.yaml.

    Applies to every configured Astrion device — mirrors calling
    select.select_option on every astrion select entity, but lets an
    automation target by page name without knowing the entity_id.
    `device_id` narrows it to one device, same as `ring`.
    """
    page = call.data[ATTR_PAGE]
    device_id = call.data.get(ATTR_DEVICE_ID)
    for entry in _async_target_entries(hass, device_id):
        coordinator = entry.runtime_data.coordinator
        try:
            await coordinator.client.async_set_page(page)
        except AstrionPageNotFound as err:
            raise HomeAssistantError(str(err)) from err
        except AstrionApiError as err:
            raise HomeAssistantError(
                f"Astrion device for entry {entry.title} unreachable: {err}"
            ) from err
        if not coordinator.has_push_webhook:
            await coordinator.async_request_refresh()


async def _async_start_activity(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle astrion.start_activity — see services.yaml.

    Same "every configured device" fan-out as set_page — a no-op for
    devices that don't have an Activity with this id, since activity ids
    are only unique within one device's dashboard.json. `device_id`
    narrows the fan-out to one device first, same as `ring`; the id still
    has no selector of its own (services.yaml: free text) since an
    Activity's internal id isn't known to HA ahead of time — a typo or the
    display name typed here instead of the id used to silently do nothing
    on every device with zero feedback; raising below instead.
    select.activite_<room> is the friendlier path (a real dropdown,
    matches by name) if this keeps happening — see select.py's
    AstrionActivitySelect.
    """
    activity_id = call.data[ATTR_ACTIVITY_ID]
    device_id = call.data.get(ATTR_DEVICE_ID)
    matched = False
    for entry in _async_target_entries(hass, device_id):
        coordinator = entry.runtime_data.coordinator
        if not any(a.id == activity_id for a in coordinator.data.activities):
            continue
        matched = True
        try:
            await coordinator.client.async_start_activity(activity_id)
        except AstrionActivityNotFound as err:
            raise HomeAssistantError(str(err)) from err
        except AstrionApiError as err:
            raise HomeAssistantError(
                f"Astrion device for entry {entry.title} unreachable: {err}"
            ) from err
        if not coordinator.has_push_webhook:
            await coordinator.async_request_refresh()
    if not matched:
        raise HomeAssistantError(
            f"No configured Astrion device has an Activity with id '{activity_id}'"
        )


async def _async_stop_activity(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle astrion.stop_activity — see services.yaml.

    Same fan-out again, skipping devices with no such room — room names
    are only unique within one device's dashboard.json. `device_id`
    narrows the fan-out to one device first, same as `ring`.
    """
    room = call.data[ATTR_ROOM]
    device_id = call.data.get(ATTR_DEVICE_ID)
    matched = False
    for entry in _async_target_entries(hass, device_id):
        coordinator = entry.runtime_data.coordinator
        if room not in coordinator.data.rooms:
            continue
        matched = True
        try:
            await coordinator.client.async_stop_activity(room)
        except AstrionApiError as err:
            raise HomeAssistantError(
                f"Astrion device for entry {entry.title} unreachable: {err}"
            ) from err
        if not coordinator.has_push_webhook:
            await coordinator.async_request_refresh()
    if not matched:
        raise HomeAssistantError(
            f"No configured Astrion device has a room named '{room}'"
        )


async def _async_ring(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle astrion.ring — see services.yaml.

    Rings every configured device unless `device_id` narrows it to one —
    see _async_target_entries.
    """
    volume = call.data[ATTR_VOLUME]
    sound = call.data[ATTR_SOUND]
    duration = call.data[ATTR_DURATION]
    device_id = call.data.get(ATTR_DEVICE_ID)
    for entry in _async_target_entries(hass, device_id):
        coordinator = entry.runtime_data.coordinator
        try:
            await coordinator.client.async_ring(volume, sound, duration)
        except AstrionApiError as err:
            raise HomeAssistantError(
                f"Astrion device for entry {entry.title} unreachable: {err}"
            ) from err


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the astrion.* services (idempotent)."""
    if not hass.services.has_service(DOMAIN, SERVICE_SET_PAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_PAGE,
            partial(_async_set_page, hass),
            schema=SET_PAGE_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_START_ACTIVITY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_START_ACTIVITY,
            partial(_async_start_activity, hass),
            schema=START_ACTIVITY_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_STOP_ACTIVITY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_ACTIVITY,
            partial(_async_stop_activity, hass),
            schema=STOP_ACTIVITY_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_RING):
        hass.services.async_register(
            DOMAIN, SERVICE_RING, partial(_async_ring, hass), schema=RING_SCHEMA
        )
