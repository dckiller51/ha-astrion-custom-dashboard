"""Constants for the Astrion Custom Dashboard integration."""

from homeassistant.const import Platform

DOMAIN = "astrion"
PLATFORMS = [Platform.SELECT, Platform.SENSOR]

NAME = "Astrion Custom Dashboard"
VERSION = "2026.8.0"
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
