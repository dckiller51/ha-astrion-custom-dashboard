# Changelog

All notable changes to this project will be documented in this file.

<!--next-version-placeholder-->

## 2026.8.0

### ✨ New features

- Added a `select.page` entity per configured Astrion device, showing the
  page currently displayed on the remote and allowing it to be changed from
  Home Assistant (dashboards, `select.select_option`, automations).
- Added the `astrion.set_page` service as a name-based shortcut for jumping
  a remote to a given page without knowing its entity_id.
- Config flow to add a remote by IP address and port (default `8080`),
  validated against the device's `/pages` endpoint.

### 📋 Requirements

- Requires an Astrion build that exposes the `GET /pages`,
  `GET /current-page`, and `POST /set-page` routes on its local config
  server (port 8080).
