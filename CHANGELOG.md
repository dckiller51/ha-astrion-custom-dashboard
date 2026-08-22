# Changelog

All notable changes to this project will be documented in this file.

<!--next-version-placeholder-->

## 2026.8.2

### ✨ New features

- Added binary_sensor.py for remote connectivity (always available, ensuring the entity itself stays reachable to report an offline state rather than going unavailable) and charging status.
- Added battery level sensor (sensor.py) leveraging the new GET /battery endpoint, with appropriate device class, percentage unit, and measurement state class.
- Added corresponding English and French translations (strings.json).

### 🧱 Internal

- api.py: added AstrionBattery dataclass and async_get_battery() method.
- coordinator.py: integrated battery polling into the standard update cycle.
- const.py: added Platform.BINARY_SENSOR to the supported platforms.

### 📋 Requirements

Requires an Astrion Custom Dashboard v1.0.0 https://github.com/dckiller51/astrion-custom-dashboard/releases

## 2026.8.1

### ✨ New features

- Added an `update.app_update` entity reporting the installed Astrion app version (from the device's new `GET /version` route) against the latest `astrion-custom-dashboard` release published on GitHub, with a link to the release page. Informational only — no remote install capability, since there's no way to push an APK to the device.
- Installed-version polling rides along on the existing fast device coordinator (cheap, local); the GitHub check runs on its own coordinator every 12 hours instead, to stay well under GitHub's unauthenticated rate limit and because a new APK build is a rare event. GitHub being briefly unreachable never fails the integration's setup or marks the entity unavailable — it just has no "latest version" to compare against until the next successful check.

### 🔧 Fixes

- `DeviceInfo.sw_version` was showing this _integration's_ own version (e.g. `2026.8.1`) instead of the Astrion app actually running on the device — now set from the real `/version` response once it's known, right after the first successful refresh.

### 🧱 Internal

- `ConfigEntry.runtime_data` is now an `AstrionRuntimeData` dataclass bundling both coordinators (`coordinator` for the device, `update_coordinator` for the GitHub check) instead of a single `AstrionCoordinator` — every existing `entry.runtime_data` access (`sensor.py`, `select.py`, the `astrion.*` service handlers) updated accordingly.

## 2026.8.0

### ✨ New features

- Added a `sensor.active_activity_<room>` entity per room, showing which Activity (composed, or a lightweight `track: true` tile) is currently active there — `unknown`/`None` when nothing is running.
- Added a `select.activity_<room>` entity per room, listing that room's Activities plus an explicit `Off` option, to start or stop an Activity from Home Assistant. Both entities are added dynamically as new rooms are discovered, without requiring a reload.
- Added the `astrion.start_activity` and `astrion.stop_activity` services as id/room-based shortcuts, the same pattern as `astrion.set_page`.
- `stop_activity` fixes the previous gap where the only way to end a classic Harmony Activity was a blanket PowerOff hotkey — which, when a single hub drives more than one room, turned every room on that hub off instead of just the one being stopped. Stopping now targets only the Activity's own hub.
- Added a `select.page` entity per configured Astrion device, showing the page currently displayed on the remote and allowing it to be changed from Home Assistant (dashboards, `select.select_option`, automations).
- Added the `astrion.set_page` service as a name-based shortcut for jumping a remote to a given page without knowing its entity_id.
- Config flow to add a remote by IP address and port (default `8080`), validated against the device's `/pages` endpoint.

### 📋 Requirements

- Requires an Astrion Custom Dashboard v0.9.0 https://github.com/dckiller51/astrion-custom-dashboard/releases
