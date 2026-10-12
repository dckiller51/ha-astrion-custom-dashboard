"""Constants for the Astrion Custom Dashboard integration."""

from homeassistant.const import Platform

DOMAIN = "astrion"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]

NAME = "Astrion Custom Dashboard"
VERSION = "2026.10.0"
ISSUE_URL = "https://github.com/dckiller51/ha-astrion-custom-dashboard/issues"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

MANUFACTURER = "Sanytron"
MODEL = "Astrion"

DEFAULT_PORT = 8080

CONF_PAGE = "page"

# How often we poll /current-page + /pages. Astrion's ConfigServer has no
# push mechanism (no websocket) for this, so local_polling is the honest
# iot_class — same reasoning as most local-HTTP integrations without SSE.
UPDATE_INTERVAL_SECONDS = 10

# Once the remote has proven it pushes through the webhook (Astrion 1.2.7+:
# page, Activities AND battery all arrive by push), polling is only a safety
# net — and every poll wakes the remote's Wi-Fi, a real battery cost on the
# handset. See __init__.py's _note_push().
UPDATE_INTERVAL_PUSH_SECONDS = 300

# entry.data key: the prefix every entity unique_id and the device identifier
# were built from when the entry was created. Kept apart from entry.unique_id
# (the remote's own id since 2026.10.0, "host:port" before) so that adopting
# a remote's id, following a new IP or swapping in a replacement remote never
# renames entities or orphans automations.
CONF_ENTITY_PREFIX = "entity_prefix"

# Fired on the bus for a hotkey set to "Home Assistant event" on the remote
# (Astrion 1.2.7+, pushed through the webhook) — carries the HA device_id.
EVENT_ASTRION = "astrion_event"

# How often we check GitHub for the latest astrion-custom-dashboard release.
# Deliberately much slower than UPDATE_INTERVAL_SECONDS — this hits GitHub's
# API (60 unauthenticated requests/hour/IP), not the local device, and a new
# APK build is a rare event; there's nothing to gain from checking more than
# a couple of times a day.
UPDATE_CHECK_INTERVAL_HOURS = 12

# The astrion-custom-dashboard (APK) repo — distinct from this integration's
# own ha-astrion-custom-dashboard repo (see ISSUE_URL above).
APK_REPO = "dckiller51/astrion-custom-dashboard"
APK_RELEASES_API_URL = f"https://api.github.com/repos/{APK_REPO}/releases/latest"

ATTR_PAGE = "page"
ATTR_ROOM = "room"
ATTR_ACTIVITY_ID = "activity_id"
ATTR_VOLUME = "volume"
ATTR_SOUND = "sound"
ATTR_DURATION = "duration"
ATTR_DEVICE_ID = "device_id"

SERVICE_SET_PAGE = "set_page"
SERVICE_START_ACTIVITY = "start_activity"
SERVICE_STOP_ACTIVITY = "stop_activity"
SERVICE_RING = "ring"

# The three sound categories Astrion's /ring endpoint understands — its own
# ringtone/alarm/notification default, chosen by RingtoneManager on-device.
# Not a free-text ringtone picker: keeps the service schema and the device's
# HTTP contract both simple, matching how little Astrion itself exposes.
SOUND_RINGTONE = "ringtone"
SOUND_ALARM = "alarm"
SOUND_NOTIFICATION = "notification"
RING_SOUNDS = [SOUND_RINGTONE, SOUND_ALARM, SOUND_NOTIFICATION]

DEFAULT_RING_VOLUME = 80
DEFAULT_RING_DURATION = 15

# select.activity_<room>'s "nothing running" option. A literal sentinel
# rather than a per-room computed value, same spirit as select.page having
# no such option (every page is always "on") — Activities are the one place
# Astrion has an explicit off state.
ACTIVITY_OFF_OPTION = "Off"
