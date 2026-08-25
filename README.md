<!-- markdownlint-disable-next-line MD033 -->

# <img src="custom_components/astrion/brand/icon@2x.png" width="48" align="center" alt="Astrion Custom Icon"> Astrion Custom Dashboard

[![GH-release](https://img.shields.io/github/v/release/dckiller51/ha-astrion-custom-dashboard.svg?style=flat-square)](https://github.com/dckiller51/ha-astrion-custom-dashboard/releases)
[![GH-downloads](https://img.shields.io/github/downloads/dckiller51/ha-astrion-custom-dashboard/total?style=flat-square)](https://github.com/dckiller51/ha-astrion-custom-dashboard/releases)
[![GH-last-commit](https://img.shields.io/github/last-commit/dckiller51/ha-astrion-custom-dashboard.svg?style=flat-square)](https://github.com/dckiller51/ha-astrion-custom-dashboard/commits/main)
[![GH-code-size](https://img.shields.io/github/languages/code-size/dckiller51/ha-astrion-custom-dashboard.svg?color=red&style=flat-square)](https://github.com/dckiller51/ha-astrion-custom-dashboard)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=flat-square)](https://github.com/hacs)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy_me_a_coffee-F16061?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/dckiller)

Home Assistant custom integration to remotely control and automate your remote.

> **Prerequisite:** This integration requires **Astrion Custom Dashboard v1.0.4 or higher** to be installed on your remote device.
> Your Astrion build must expose the `/pages`, `/current-page`, `/set-page`, `/activities`, `/activities/active`, `/activities/start`, `/activities/stop`, `/ring`, and `/ring/stop` routes on its local config server (port 8080 by default).

_(Click the banner below to see the project)_
[![Astrion Custom Dashboard](https://github.com/dckiller51/astrion-custom-dashboard/blob/main/docs/banner_astrion_custom_dashboard.png)](https://github.com/dckiller51/astrion-custom-dashboard)

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install
"Astrion Custom Dashboard".

### Manual

Copy `custom_components/astrion` into your Home Assistant `custom_components/`
directory, then restart Home Assistant.

## Configuration

**Settings → Devices & services → Add integration → Astrion Custom Dashboard**, then
enter the IP address (and port, default `8080`) of your Astrion device.

## What you get

- `select.page` — reflects the page currently shown on the remote, and lets
  you change it (dashboards, `select.select_option`, automations).
- `sensor.active_activity_<room>` — one per room found in your `dashboard.json`
  Activities (composed, or a lightweight `"track": true` tile). Read-only:
  reports the name of the Activity currently active in that room, or
  `unknown` when nothing is running.
- `select.activity_<room>` — one per room, alongside its sensor. Lists that
  room's Activities plus an explicit `Off` option. Picking an Activity
  starts it (`select.select_option`); picking `Off` stops whichever one is
  active — for a Harmony-backed Activity this sends PowerOff to _that
  Activity's own hub only_, not a blanket "turn everything off", so other
  rooms sharing the same hub are left untouched.
- `button.find_my_remote` — one per configured device. "Where's my remote?":
  pressing it rings the device's own speaker for a few seconds at a fixed
  default volume/sound/duration. For anything more specific — a different
  volume, sound, duration, or targeting one device in a multi-device home
  — use the `astrion.ring` service below instead.
- `astrion.set_page` service — a name-based shortcut:

  ```yaml
  service: astrion.set_page
  data:
    page: "Media"
  ```

- `astrion.start_activity` service — starts an Activity by id (as returned
  by the device's `/activities` endpoint) without needing its room's
  `select.activity_<room>` entity_id:

  ```yaml
  service: astrion.start_activity
  data:
    activity_id: "watch_appletv"
  ```

- `astrion.stop_activity` service — stops whichever Activity is active in a
  given room, by room name:

  ```yaml
  service: astrion.stop_activity
  data:
    room: "Salon"
  ```

- `astrion.ring` service — "find my remote" with control over how: plays a
  sound on the device's own speaker so you can locate it by ear.

  ```yaml
  service: astrion.ring
  data:
    volume: 90 # 1-100%, default 80
    sound: "alarm" # "ringtone" | "alarm" | "notification", default "ringtone"
    duration: 20 # seconds, 1-60, default 15
    device_id: abc123def456 # optional — omit to ring every configured device
  ```

Both `sensor.active_activity_<room>` and `select.activity_<room>` are added
automatically as soon as a room is discovered — no reload needed after
editing `dashboard.json` to add a new room, once the coordinator's next
refresh picks it up.

## Useful links

- [Astrion Custom Dashboard (Android app / APK)](https://github.com/dckiller51/astrion-custom-dashboard)

## ☕ Support

If you find **Astrion Custom Dashboard** useful and want to support its development, you can buy me a coffee!

[![Ko-fi](https://img.shields.io/badge/Buy_me_a_coffee-Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/dckiller)
