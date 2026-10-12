"""DataUpdateCoordinator for the Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AstrionActivity,
    AstrionApiError,
    AstrionBattery,
    AstrionClient,
    AstrionInfo,
)
from .const import DOMAIN, MANUFACTURER, MODEL, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


@dataclass
class AstrionData:
    """Snapshot of the Astrion device's dashboard state."""

    page_names: list[str]
    current_page: str | None
    activities: list[AstrionActivity]
    active_by_room: dict[str, AstrionActivity | None]
    installed_version: str
    battery: AstrionBattery

    @property
    def rooms(self) -> list[str]:
        """Every room with at least one trackable Activity, first-seen order."""
        seen: dict[str, None] = {}
        for activity in self.activities:
            seen.setdefault(activity.room, None)
        return list(seen)

    def activities_in(self, room: str) -> list[AstrionActivity]:
        """Return the activities available in one room, in declaration order."""
        return [activity for activity in self.activities if activity.room == room]


class AstrionCoordinator(DataUpdateCoordinator[AstrionData]):
    """Polls /pages and /current-page so entities stay in sync with the device."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AstrionClient,
        unique_id: str,
        device_name: str,
        info: AstrionInfo | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        # The prefix of every entity unique_id and the device identifier — the
        # entry's CONF_ENTITY_PREFIX, NOT necessarily entry.unique_id (see const.py).
        self.unique_id = unique_id
        # What /info said at setup (None for an app older than 1.2.7).
        self.info = info
        # Last time the remote answered a poll or pushed something — see sensor.py's
        # AstrionLastSeenSensor. Set on every successful refresh and every webhook push.
        self.last_seen: datetime | None = None
        # True once a push carrying the remote's identity arrived (Astrion 1.2.7+),
        # which also slows polling down — see __init__.py's _note_push().
        self.push_confirmed = False
        # Set by __init__.py right after registering (or skipping) the push
        # webhook. Read by select.py to decide whether an action's own
        # immediate async_request_refresh() is worth doing at all — see its
        # docstring for why that immediate refresh is actually harmful once
        # a webhook is configured, not just redundant.
        self.has_push_webhook = False
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            hw_version=(
                f"{info.manufacturer} {info.model}".strip()
                if info is not None
                else None
            ),
            # No sw_version here — it's the *installed Astrion app's* own
            # version, only known after the first successful /version
            # fetch, not this integration's own VERSION constant. Set once
            # in __init__.py right after async_config_entry_first_refresh().
        )

    async def _async_update_data(self) -> AstrionData:
        try:
            pages = await self.client.async_get_pages()
            current = await self.client.async_get_current_page()
            activities = await self.client.async_get_activities()
            active_by_room = await self.client.async_get_active_activities()
            version = await self.client.async_get_version()
            battery = await self.client.async_get_battery()
        except AstrionApiError as err:
            raise UpdateFailed(str(err)) from err

        self.last_seen = dt_util.utcnow()
        return AstrionData(
            page_names=[page.name for page in pages],
            current_page=current.name if current else None,
            activities=activities,
            active_by_room=active_by_room,
            installed_version=version.version,
            battery=battery,
        )
