"""Config flow for the Astrion Custom Dashboard integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
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
        """Handle the initial step: ask for host/port."""
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
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the Astrion device."""
