# Changelog

All notable changes to this project will be documented in this file.

<!--next-version-placeholder-->

## 2026.10.0

### ✨ New features

- **Several remotes in one home.** With Astrion 1.2.7+, each remote is identified by its own id (`/info`), no longer by `host:port`: the entry and device are named after the name set on the remote, and renaming it on the remote renames the device (a name set in Home Assistant still wins).
- **The remote's new IP is followed automatically.** A push from a new private IP is checked against `/info` (same remote id) and the entry moves there. Adding a known remote again with its new IP also just updates the existing entry.
- **Reconfigure.** Change a remote's address from the entry's menu — or point it at a replacement remote, which takes over the old one's entities, device and automations.
- **`astrion_event`.** A hotkey set to "Home Assistant event" on the remote (1.2.7+) fires `astrion_event` with the HA `device_id`, `remote_id`, `remote_name`, `event`, `key`, `long` and `page` — one automation per remote and button, no administrator token needed on the remote.
- **Battery by push.** `{"type": "battery"}` pushes update the battery and charging sensors right away.
- **`sensor.<remote>_last_seen`** (diagnostic): when the remote last answered a poll or pushed something; stays available while the remote is unreachable.

### ⚡ Battery life of the remote

- Once the remote proves it pushes (Astrion 1.2.7+: a push carrying its identity), polling drops from every 10 s to every **5 minutes**: page, Activities and battery all arrive by push, and each poll woke the remote's Wi-Fi.

### 🔧 Fixes

- **Home Assistant 2026.9+ (probatio):** schemas are built with `probatio` instead of `voluptuous` — fixes the `mypy` errors on `async_show_form(data_schema=…)` and `async_register(schema=…)`. Requires Home Assistant **2026.9.0** or later.
- Device registry lookups use `async_get_device_by_identifier` (HA deprecated `async_get_device`).

### 🧱 Internal

- Config entry minor version 1.2: `entity_prefix` in the entry's data keeps every entity unique_id and the device identifier on the value they were created with, so `entry.unique_id` can become the remote's id (or a replacement's) without renaming anything. Migrated automatically.
- `api.py`: `AstrionInfo` + `async_get_info()` (None for an app without `/info`).
- New tests: `tests/test_multi_remote.py` (identity, migration, re-add / reconfigure, webhook battery + button, IP follow).

### 📋 Requirements

- Home Assistant 2026.9.0+.
- Everything works with older Astrion apps as before (identified by `host:port`); identity, IP following, `astrion_event`, battery push and the 5-minute polling need **Astrion 1.2.7+** with the push webhook configured.

## 2026.8.5

### ✨ New features

- **Per-device targeting for `set_page`, `start_activity`, and `stop_activity`.** All three now accept the same optional `device_id` field `ring` already had, to target one specific Astrion device in a multi-device home instead of fanning out to every configured one (the default, unchanged, when omitted).

### 🔧 Fixes

- **Selecting a page or Activity from Home Assistant briefly bounced back to the old value before correcting itself**, on setups with the 2026.8.4 push webhook configured. `select.page`/`select.activity_<room>` (and the `set_page`/`start_activity`/`stop_activity` services) each requested an immediate `coordinator.async_request_refresh()` right after their action — but the device's own `/set-page`, `/activities/start` etc. return as soon as the request is accepted, not once the change has actually landed on screen, so that immediate refresh routinely read back the _old_ state and overwrote the correct one HA had just shown, until the webhook (or the next regular poll) corrected it a moment later. That immediate refresh is now skipped whenever a push webhook is configured — the webhook is fast enough to be the sole source of the quick update, and regular polling is unaffected, still covering the case where a push never arrives.

### 🧱 Internal

- `coordinator.py`: new `AstrionCoordinator.has_push_webhook` flag, set in `__init__.py` right after the webhook is (or isn't) registered for a config entry.
- `select.py`: `AstrionPageSelect`/`AstrionActivitySelect` now share a small `AstrionSelectEntity` base with one helper, `_maybe_refresh()`, replacing every direct `await self.coordinator.async_request_refresh()` call site.
- `__init__.py`: `_async_set_page`/`_async_start_activity`/`_async_stop_activity` now resolve their target entries via `_async_target_entries(hass, device_id)` (previously `ring`-only) instead of always fanning out to `hass.config_entries.async_entries(DOMAIN)`, and skip their own post-action refresh under the same `has_push_webhook` condition as `select.py`.
- `services.yaml`: added the `device_id` device selector (`integration: astrion`) to `set_page`, `start_activity`, and `stop_activity`, matching `ring`'s.

### 📋 Requirements

No device-side change needed — this is HA-integration-only. Works with any Astrion Custom Dashboard version already compatible with 2026.8.4's push webhook (v1.0.7+) to get the fix; `device_id` targeting works regardless of whether a webhook is configured.

## 2026.8.4

### ✨ New features

- **Instant push instead of polling.** New optional webhook — generated automatically at setup, viewable/regeneratable any time from this entry's "Configure" — that the paired Astrion Custom Dashboard app (1.0.7+) POSTs to the moment the current page or an Activity changes, instead of this integration only finding out on its next poll. `sensor.active_activity_<room>`/`select.activity_<room>` update immediately when this is set up on the Astrion side; polling stays on regardless as the reliable fallback (`iot_class` is unchanged — this is additive, not a replacement).

### 🧱 Internal

- `__init__.py`: registers/unregisters the webhook per config entry (`webhook.async_register`/`async_unregister`), bound via closure over that entry's own `AstrionCoordinator` so there's no id → entry lookup at request time. `_apply_page_push`/`_apply_activity_push` translate a push into `coordinator.async_set_updated_data(...)`; an activity push prefers the already-known `AstrionActivity` (by id, from the last poll) to keep its icon, falling back to a minimal one built from the push itself for an id the last poll doesn't know about yet.
- `config_flow.py`: `CONF_WEBHOOK_ID` generated (`webhook.async_generate_id()`) and stored at entry creation — single-step flow unchanged, the id isn't shown until "Configure" so `async_configure()` still returns `CREATE_ENTRY` in one call. New `AstrionOptionsFlow` (`async_get_options_flow`) shows the current webhook id/URL and offers a "regenerate" checkbox, which updates the entry and triggers a reload (new `_async_reload_entry` update-listener) to re-register under the new id.
- Added English and French translations (`strings.json`, `translations/en.json`, `translations/fr.json`) for the new `options.step.init` screen.
- `tests/test_config_flow.py`: `test_user_flow_success` now checks `CONF_HOST`/`CONF_PORT` individually plus that a `CONF_WEBHOOK_ID` was generated, instead of an exact `== VALID_INPUT` match that a random id can no longer satisfy.

### 📋 Requirements

Push is opt-in and additive: leave the webhook field blank in Astrion's web configurator to keep 2026.8.3's polling-only behavior unchanged. To use it, requires Astrion Custom Dashboard v1.0.7 https://github.com/dckiller51/astrion-custom-dashboard/releases (adds the device-side `ha_webhook_id` setting and the pushes themselves).

## 2026.8.3

### ✨ New features

- **"Find my remote."** New `astrion.ring` service plays a sound on the device's own speaker for a few seconds so a misplaced remote can be located by ear. Fields: `volume` (1-100%, default 80), `sound` (`ringtone` | `alarm` | `notification`, default `ringtone`), `duration` (seconds, 1-60, default 15), and an optional `device_id` to ring just one Astrion device instead of every configured one (the default, unchanged, when omitted).
- New `button.find_my_remote` entity — one-click ring at the default volume/sound/duration, no service call needed. Complements the service rather than replacing it: reaching for a specific volume/sound/duration, or targeting one device out of several, still means calling `astrion.ring`.

### 🧱 Internal

- `api.py`: added `AstrionClient.async_ring()`, posting to the device's new `/ring` endpoint.
- `const.py`: added `Platform.BUTTON`, the `ring`-related `ATTR_*`/`SERVICE_RING`/`SOUND_*` constants, and `DEFAULT_RING_VOLUME`/`DEFAULT_RING_DURATION`.
- `__init__.py`: added `RING_SCHEMA` and the `astrion.ring` service handler; added `_async_target_entries()`, a small helper resolving an optional `device_id` to the config entries it should apply to, used by `ring` and reusable if the other services (`set_page`, `start_activity`, `stop_activity`) ever want the same per-device targeting.
- New `button.py` (`AstrionRingButton`), following the same `CoordinatorEntity` + `has_entity_name` pattern as `select.py`.
- Added corresponding English and French translations (`strings.json`, `translations/en.json`, `translations/fr.json`) for the service and the new button entity.
- `tests/test_api.py`: added coverage for `async_ring`, including the device rejecting an unknown `sound`.
- New `tests/test_button.py`: covers the button entity being registered, pressing it calling `async_ring` with exactly the documented defaults, and an unreachable device surfacing as a `HomeAssistantError`.

### 📋 Requirements

Requires an Astrion Custom Dashboard v1.0.4 https://github.com/dckiller51/astrion-custom-dashboard/releases (adds the device's `/ring` and `/ring/stop` endpoints).

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
