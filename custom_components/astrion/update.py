"""Update entity: installed Astrion app version vs. the latest GitHub release.

Two separate concerns, two separate coordinators:
 - "installed" comes from the device itself (GET /version), polled at the
   same fast cadence as everything else in AstrionCoordinator — it's a
   cheap local call, no reason to special-case it.
 - "latest" comes from GitHub's releases API, which is rate-limited (60
   unauthenticated requests/hour/IP) and changes rarely (a new APK build),
   so it gets its own coordinator on a much slower interval instead of
   riding along on the fast one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import AstrionConfigEntry
from .const import APK_RELEASES_API_URL, APK_REPO, DOMAIN, UPDATE_CHECK_INTERVAL_HOURS
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)

_RELEASE_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


@dataclass
class AstrionLatestRelease:
    """The latest published astrion-custom-dashboard (APK) release."""

    version: str
    release_url: str


class AstrionUpdateCoordinator(DataUpdateCoordinator[AstrionLatestRelease | None]):
    """Polls GitHub's releases API for the latest astrion-custom-dashboard build.

    `None` data (rather than raising) on any failure — GitHub being briefly
    unreachable, or answering with something unexpected, shouldn't mark this
    coordinator as failed the way `AstrionCoordinator` legitimately does for
    the local device: there's a real difference between "your Astrion box
    dropped off the LAN" (worth surfacing loudly) and "couldn't check for
    updates this cycle" (worth a debug log and trying again next interval).
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_update_check",
            update_interval=timedelta(hours=UPDATE_CHECK_INTERVAL_HOURS),
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> AstrionLatestRelease | None:
        try:
            async with self._session.get(
                APK_RELEASES_API_URL, timeout=_RELEASE_REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "GitHub releases check for %s returned HTTP %s",
                        APK_REPO,
                        response.status,
                    )
                    return None
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("GitHub releases check for %s failed: %s", APK_REPO, err)
            return None

        tag_name = payload.get("tag_name")
        release_url = payload.get("html_url")
        if not tag_name or not release_url:
            return None

        # Release tags on this repo may or may not carry a "v" prefix
        # ("v0.9.0" vs "0.9.0") — BuildConfig.VERSION_NAME (what /version
        # reports) never does, so strip it here or every release would
        # permanently look like an available update.
        version = tag_name.removeprefix("v").removeprefix("V")
        return AstrionLatestRelease(version=version, release_url=release_url)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: AstrionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Astrion app update entity.

    `hass` is unused here but kept — it's part of the standard
    `async_setup_entry(hass, entry, async_add_entities)` platform signature
    Home Assistant calls positionally for every platform.
    """
    runtime = entry.runtime_data
    update_coordinator = runtime.update_coordinator
    # Soft-fail refresh, not async_config_entry_first_refresh(): GitHub
    # being briefly unreachable at startup shouldn't block the rest of the
    # integration (pages/activities) from loading — see the coordinator's
    # own doc comment.
    await update_coordinator.async_refresh()
    async_add_entities([AstrionUpdateEntity(runtime.coordinator, update_coordinator)])


class AstrionUpdateEntity(CoordinatorEntity[AstrionUpdateCoordinator], UpdateEntity):
    """Reports the installed Astrion app version and the latest GitHub release.

    Informational only — no `UpdateEntityFeature.INSTALL`, since there's no
    way to push an APK to the device remotely; this just tells you one is
    available and links to the release, same as a plain "firmware version"
    sensor would, but using HA's dedicated update entity (and its "update
    available" UI treatment) instead of reinventing that with a sensor's
    attributes.

    Tied to [AstrionUpdateCoordinator] (the slow one) for its own
    availability/polling, since that's the entity's whole reason to exist;
    also listens to the fast [AstrionCoordinator] so `installed_version`
    stays live without waiting for the next 12-hour GitHub check.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "app_update"
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        device_coordinator: AstrionCoordinator,
        update_coordinator: AstrionUpdateCoordinator,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(update_coordinator)
        self._device_coordinator = device_coordinator
        self._attr_unique_id = f"{device_coordinator.unique_id}-app-update"
        self._attr_device_info = device_coordinator.device_info
        self._attr_title = "Astrion Custom Dashboard"

    async def async_added_to_hass(self) -> None:
        """Also react to the fast coordinator's own refreshes, not just the slow one."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device_coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def installed_version(self) -> str | None:
        """Return the version currently running on the Astrion device."""
        return self._device_coordinator.data.installed_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest version published on GitHub, if known."""
        release = self.coordinator.data
        return release.version if release else None

    @property
    def release_url(self) -> str | None:
        """Return the GitHub release page for `latest_version`."""
        release = self.coordinator.data
        return release.release_url if release else None
