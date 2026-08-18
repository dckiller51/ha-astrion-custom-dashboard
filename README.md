# ha_astrion_custom_dashboard

Home Assistant custom integration to remotely control and automate your remote.

_(Click the banner below to see the project)_
[![Astrion Custom Dashboard](https://github.com/dckiller51/astrion-custom-dashboard/blob/main/docs/banner_astrion_custom_dashboard.png)](https://github.com/dckiller51/astrion-custom-dashboard)

> **Prerequisite:** This integration requires **Astrion Custom Dashboard v0.9.0 or higher** to be installed on your remote device.
> Your Astrion build must expose the `/pages`, `/current-page`, and `/set-page` routes on its local config server (port 8080 by default).

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install
"Astrion Custom Dashboard".

### Manual

Copy `custom_components/ha_astrion_custom_dashboard` into your Home Assistant `custom_components/`
directory, then restart Home Assistant.

## Configuration

**Settings → Devices & services → Add integration → Astrion Remote**, then
enter the IP address (and port, default `8080`) of your Astrion device.

## What you get

- `select.page` — reflects the page currently shown on the remote, and lets
  you change it (dashboards, `select.select_option`, automations).
- `astrion.set_page` service — a name-based shortcut:

  ```yaml
  service: astrion.set_page
  data:
    page: "Media"
  ```
