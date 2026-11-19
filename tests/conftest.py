"""Shared fixtures for the inverterzone tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant

from custom_components.inverterzone.const import BASE_URL, CONF_EXPIRES_AT, CONF_TOKEN, DOMAIN

MAC = "A1B2C3D4E5F6"
EMAIL = "user@example.com"
FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    """A JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fail(error: str, message: str = "failed") -> dict[str, Any]:
    """An API error envelope."""
    return {"success": False, "error": error, "message": message}


def calls_to(aioclient_mock: AiohttpClientMocker, path: str) -> int:
    """How many requests went to [path]."""
    return sum(1 for call in aioclient_mock.mock_calls if path in str(call[1]))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
def mock_cloud(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """A healthy cloud with one inverter."""
    aioclient_mock.post(f"{BASE_URL}/getConnected", json=load("connect.json"))
    aioclient_mock.get(f"{BASE_URL}/getDevices", json=load("devices.json"))
    aioclient_mock.get(f"{BASE_URL}/getSolarData", json=load("solar_data.json"))
    aioclient_mock.get(f"{BASE_URL}/getEnergyData", json=load("energy_data.json"))
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A signed-in account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=EMAIL,
        data={CONF_EMAIL: EMAIL, CONF_TOKEN: "tok-123", CONF_EXPIRES_AT: "2027-11-19T10:00:00Z"},
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and load [entry]."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
