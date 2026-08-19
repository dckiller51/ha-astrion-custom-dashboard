"""Constants for the Astrion Custom Dashboard integration."""

from homeassistant.const import Platform

DOMAIN = "astrion"
PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.UPDATE]

NAME = "Astrion Custom Dashboard"
VERSION = "2026.8.1"
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

SERVICE_SET_PAGE = "set_page"
SERVICE_START_ACTIVITY = "start_activity"
SERVICE_STOP_ACTIVITY = "stop_activity"

# select.activity_<room>'s "nothing running" option. A literal sentinel
# rather than a per-room computed value, same spirit as select.page having
# no such option (every page is always "on") — Activities are the one place
# Astrion has an explicit off state.
ACTIVITY_OFF_OPTION = "Off"
