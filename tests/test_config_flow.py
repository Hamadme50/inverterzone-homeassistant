"""Tests for the inverterzone config flow."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.inverterzone.const import BASE_URL, CONF_TOKEN, DOMAIN

from .conftest import EMAIL, fail, load

CONNECT = f"{BASE_URL}/getConnected"


@pytest.fixture(autouse=True)
def no_setup():
    """Creating an entry must not start polling in these tests."""
    with patch("custom_components.inverterzone.async_setup_entry", return_value=True):
        yield


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow_stores_token_not_password(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Signing in creates an entry with the token and without the password."""
    aioclient_mock.post(CONNECT, json=load("connect.json"))
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: f"  {EMAIL}  ", CONF_PASSWORD: "secret"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["result"].unique_id == EMAIL
    assert result["data"][CONF_TOKEN] == "tok-123"
    assert CONF_PASSWORD not in result["data"]
    assert aioclient_mock.mock_calls[0][2] == {"email": EMAIL, "password": "secret"}


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"status": 401, "json": fail("INVALID_CREDENTIALS")}, "invalid_auth"),
        ({"status": 500, "json": fail("SERVER_ERROR")}, "cannot_connect"),
        ({"status": 404, "text": "<html>not here</html>"}, "cannot_connect"),
        ({"exc": aiohttp.ClientError()}, "cannot_connect"),
        ({"json": {"success": True, "data": {"token": "t", "devices": []}}}, "no_devices"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict, error: str
) -> None:
    """Sign-in failures are shown on the form, which can then be retried."""
    aioclient_mock.post(CONNECT, **response)
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.post(CONNECT, json=load("connect.json"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The same account cannot be added twice, whatever the email's case."""
    config_entry.add_to_hass(hass)
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL.upper(), CONF_PASSWORD: "secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert aioclient_mock.call_count == 0


async def test_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Reauth asks for the password only and stores the new token."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.post(CONNECT, status=401, json=fail("INVALID_CREDENTIALS"))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    fresh = load("connect.json")
    fresh["data"]["token"] = "tok-new"
    aioclient_mock.post(CONNECT, json=fresh)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == "tok-new"
    assert CONF_PASSWORD not in config_entry.data
    assert aioclient_mock.mock_calls[0][2] == {"email": EMAIL, "password": "new-secret"}
