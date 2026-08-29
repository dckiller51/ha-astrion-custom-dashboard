"""Config flow for the Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AstrionApiError, AstrionClient
from .const import DEFAULT_PORT, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

REGENERATE_SCHEMA = vol.Schema({vol.Optional("regenerate", default=False): bool})


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Check we can reach the device's /pages endpoint."""
    session = async_get_clientsession(hass)
    client = AstrionClient(session, data[CONF_HOST], data[CONF_PORT])
    try:
        pages = await client.async_get_pages()
    except AstrionApiError as err:
        raise CannotConnect from err

    if not pages:
        raise CannotConnect

    return {"title": NAME}


class AstrionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Astrion Custom Dashboard."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial (and only) step: ask for host/port, then create the entry.

        The webhook id is generated and stored right away, but not shown here
        — a single-step flow keeps `async_configure()` behaving the way every
        other part of this integration (and its tests) expect: one call in,
        a finished entry out. The id/URL live in this entry's "Configure"
        (see AstrionOptionsFlow below) instead, discoverable any time.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-exception-caught
                # Deliberately broad: a config flow step must never raise, it
                # must always redraw the form with an error — same pattern
                # the built-in `harmony` integration's own config flow uses.
                _LOGGER.exception("Unexpected exception validating Astrion connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                data = {**user_input, CONF_WEBHOOK_ID: webhook.async_generate_id()}
                return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> AstrionOptionsFlow:
        """Get the options flow — where the webhook id/URL can be viewed or regenerated."""
        return AstrionOptionsFlow()


class AstrionOptionsFlow(OptionsFlow):
    """Re-view or regenerate this entry's push webhook, after initial setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the current webhook URL; create one if missing, or roll it over to a new id."""
        current_id = self.config_entry.data.get(CONF_WEBHOOK_ID)

        if user_input is not None:
            # Two cases mint a (new) id: the checkbox was explicitly checked, or
            # this entry never had one at all (created before this feature
            # existed — nothing else ever gives it one otherwise, since
            # "regenerate" alone only makes sense once an id already exists).
            if user_input.get("regenerate") or not current_id:
                new_id = webhook.async_generate_id()
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_WEBHOOK_ID: new_id},
                )
                # __init__.py's update-listener re-registers the webhook under
                # the new id (and unregisters the old one, if any) on reload.
                current_id = new_id
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=REGENERATE_SCHEMA,
            description_placeholders=_webhook_placeholders(self.hass, current_id),
        )


def _webhook_placeholders(
    hass: HomeAssistant, webhook_id: str | None
) -> dict[str, str]:
    """Build the {webhook_id}/{webhook_url} description placeholders shared by both flows."""
    if not webhook_id:
        return {
            "webhook_id": "(none yet — submit below to create one)",
            "webhook_url": "(none yet — submit below to create one)",
        }
    return {
        "webhook_id": webhook_id,
        "webhook_url": webhook.async_generate_url(hass, webhook_id),
    }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the Astrion device."""
