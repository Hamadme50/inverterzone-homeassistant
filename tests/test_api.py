"""Tests for the inverterzone API client's error mapping."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.inverterzone.api import (
    InverterZoneApi,
    InverterZoneAuthError,
    InverterZoneConnectionError,
    InverterZoneDeviceNotLinkedError,
    InverterZoneNoDataError,
)
from custom_components.inverterzone.const import BASE_URL

from .conftest import MAC, fail, load

SOLAR = f"{BASE_URL}/getSolarData"


@pytest.mark.parametrize(
    ("response", "error", "code"),
    [
        ({"status": 401, "json": fail("TOKEN_EXPIRED")}, InverterZoneAuthError, "TOKEN_EXPIRED"),
        ({"status": 401, "json": fail("TOKEN_REVOKED")}, InverterZoneAuthError, "TOKEN_REVOKED"),
        ({"status": 403, "json": fail("DEVICE_NOT_LINKED")}, InverterZoneDeviceNotLinkedError, "DEVICE_NOT_LINKED"),
        ({"status": 404, "json": fail("NO_DATA")}, InverterZoneNoDataError, "NO_DATA"),
        ({"status": 404, "text": "<html>"}, InverterZoneConnectionError, None),
        ({"status": 500, "json": fail("SERVER_ERROR")}, InverterZoneConnectionError, "SERVER_ERROR"),
        ({"status": 200, "json": {"success": True, "data": []}}, InverterZoneConnectionError, None),
        ({"exc": aiohttp.ClientError()}, InverterZoneConnectionError, None),
        ({"exc": asyncio.TimeoutError()}, InverterZoneConnectionError, None),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict,
    error: type[Exception],
    code: str | None,
) -> None:
    """Every failure becomes a typed error carrying the API's code."""
    aioclient_mock.get(SOLAR, **response)
    api = InverterZoneApi(async_get_clientsession(hass), "tok-123")

    with pytest.raises(error) as raised:
        await api.solar_data(MAC)
    assert getattr(raised.value, "code", None) == code


async def test_request_shape(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Reads send the bearer token and the mac as a query parameter."""
    aioclient_mock.get(SOLAR, json=load("solar_data.json"))
    api = InverterZoneApi(async_get_clientsession(hass), "tok-123")

    data = await api.solar_data(MAC)

    assert data["solar"]["watts"] == 3150
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert url.query["mac"] == MAC
    assert headers["Authorization"] == "Bearer tok-123"


async def test_no_token(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Without a token nothing is sent."""
    api = InverterZoneApi(async_get_clientsession(hass))
    with pytest.raises(InverterZoneAuthError):
        await api.devices()
    assert aioclient_mock.call_count == 0
