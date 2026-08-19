"""Tests for the Astrion Custom Dashboard config flow.

Uses Home Assistant's own test harness (`hass`, `enable_custom_integrations`
fixtures from pytest-homeassistant-custom-component), so — unlike
test_api.py — these only run in the same Python/HA version the project
targets (see pyproject.toml's requires-python and homeassistant pin).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.astrion.api import AstrionApiError, AstrionPage, AstrionVersion
from custom_components.astrion.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

VALID_INPUT = {CONF_HOST: "10.0.0.5", CONF_PORT: 8080}


@contextmanager
def _mock_reachable_device(pages: list[AstrionPage]) -> Iterator[None]:
    """Mock every AstrionClient call the flow and the coordinator make.

    Covers both the config flow's own validation call and the coordinator's
    first refresh, which Home Assistant kicks off in the background as soon
    as the entry is created — without this, that refresh falls through to a
    real (blocked-by-tests) socket call. Also mocks the update coordinator's
    GitHub check for the same reason — `async_setup_entry` runs it right
    alongside the device coordinator's own first refresh.
    """
    with (
        patch(
            "custom_components.astrion.api.AstrionClient.async_get_pages",
            AsyncMock(return_value=pages),
        ),
        patch(
            "custom_components.astrion.api.AstrionClient.async_get_current_page",
            AsyncMock(return_value=pages[0] if pages else None),
        ),
        patch(
            "custom_components.astrion.api.AstrionClient.async_get_activities",
            AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.astrion.api.AstrionClient.async_get_active_activities",
            AsyncMock(return_value={}),
        ),
        patch(
            "custom_components.astrion.api.AstrionClient.async_get_version",
            AsyncMock(return_value=AstrionVersion(version="0.9.0", version_code=9)),
        ),
        patch(
            "custom_components.astrion.update.AstrionUpdateCoordinator._async_update_data",
            AsyncMock(return_value=None),
        ),
    ):
        yield


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """A reachable device with at least one page creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with _mock_reachable_device([AstrionPage(index=0, name="Main")]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Astrion Custom Dashboard"
    assert result["data"] == VALID_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """An unreachable device redraws the form with a cannot_connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.astrion.config_flow.AstrionClient.async_get_pages",
        AsyncMock(side_effect=AstrionApiError("no route to host")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_no_pages(hass: HomeAssistant) -> None:
    """A device with an empty dashboard is treated as not-yet-usable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.astrion.config_flow.AstrionClient.async_get_pages",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Adding the same host:port twice aborts the second flow."""
    with _mock_reachable_device([AstrionPage(index=0, name="Main")]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(result["flow_id"], VALID_INPUT)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
