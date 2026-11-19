"""Tests for setting up, polling and unloading inverterzone."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.inverterzone.const import BASE_URL, DOMAIN, LIVE_INTERVAL
from custom_components.inverterzone.diagnostics import async_get_config_entry_diagnostics

from .conftest import MAC, calls_to, fail, load, setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The entry loads with the stored token, creates the device and unloads."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    headers = mock_cloud.mock_calls[0][3]
    assert headers["Authorization"] == "Bearer tok-123"

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, MAC), config_entry.entry_id)
    assert device is not None
    assert device.name == "Home inverter"
    assert device.manufacturer == "ANENJI"
    assert device.model == "6.2KW"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_expired_token_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A revoked token stops setup and asks the user to sign in again."""
    aioclient_mock.get(f"{BASE_URL}/getDevices", status=401, json=fail("TOKEN_REVOKED"))
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_setup_cloud_down_retries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A cloud outage at startup retries later."""
    aioclient_mock.get(f"{BASE_URL}/getDevices", status=502, text="Bad gateway")
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_inverter_without_data_does_not_block_others(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """An inverter that never reported loads with unavailable sensors; the others work."""
    devices = load("devices.json")
    devices["data"].append(
        {"mac": "B1B2B3B4B5B6", "name": "Shop", "model": None, "brand": None, "online": False}
    )
    aioclient_mock.get(f"{BASE_URL}/getDevices", json=devices)
    aioclient_mock.get(
        f"{BASE_URL}/getSolarData?mac=B1B2B3B4B5B6", status=404, json=fail("NO_DATA")
    )
    aioclient_mock.get(
        f"{BASE_URL}/getEnergyData?mac=B1B2B3B4B5B6", status=404, json=fail("NO_DATA")
    )
    aioclient_mock.get(f"{BASE_URL}/getSolarData", json=load("solar_data.json"))
    aioclient_mock.get(f"{BASE_URL}/getEnergyData", json=load("energy_data.json"))

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.home_inverter_solar_power").state == "3150"
    assert hass.states.get("sensor.shop_solar_power").state == "unavailable"
    assert hass.states.get("sensor.shop_solar_energy_today").state == "unavailable"
    # Optional sensors are not guessed for an inverter that has not reported.
    assert hass.states.get("sensor.shop_pv1_power") is None


async def test_token_revoked_while_running_starts_reauth(
    hass: HomeAssistant,
    mock_cloud: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A password change while running marks sensors unavailable and asks to sign in again."""
    await setup_integration(hass, config_entry)
    assert hass.states.get("sensor.home_inverter_solar_power").state == "3150"

    mock_cloud.clear_requests()
    mock_cloud.get(f"{BASE_URL}/getSolarData", status=401, json=fail("TOKEN_REVOKED"))
    freezer.tick(LIVE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_inverter_solar_power").state == "unavailable"
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_live_polls_every_15_seconds(
    hass: HomeAssistant,
    mock_cloud: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Live data refreshes every 15 s; energy does not."""
    await setup_integration(hass, config_entry)
    assert calls_to(mock_cloud, "getSolarData") == 1
    assert calls_to(mock_cloud, "getEnergyData") == 1

    for _ in range(4):
        freezer.tick(timedelta(seconds=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert calls_to(mock_cloud, "getSolarData") == 5
    assert calls_to(mock_cloud, "getEnergyData") == 1

    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls_to(mock_cloud, "getEnergyData") == 2


async def test_energy_refreshes_just_before_site_midnight(
    hass: HomeAssistant,
    mock_cloud: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Today's totals are fetched once more at 23:55 in the site's timezone (Asia/Karachi, UTC+5)."""
    freezer.move_to(datetime(2026, 11, 19, 18, 50, tzinfo=timezone.utc))  # 23:50 in Karachi
    await setup_integration(hass, config_entry)
    assert calls_to(mock_cloud, "getEnergyData") == 1

    freezer.move_to(datetime(2026, 11, 19, 18, 54, 50, tzinfo=timezone.utc))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls_to(mock_cloud, "getEnergyData") == 1

    freezer.move_to(datetime(2026, 11, 19, 18, 55, 1, tzinfo=timezone.utc))  # 23:55:01 Karachi
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert calls_to(mock_cloud, "getEnergyData") == 2


async def test_diagnostics_redact_token_and_email(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Diagnostics never contain the token or the email."""
    await setup_integration(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    text = str(diagnostics)
    assert "tok-123" not in text
    assert "user@example.com" not in text
    assert diagnostics["devices"][MAC]["live"]["data"]["solar"]["watts"] == 3150


async def test_remove_stale_device(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Only inverters that left the account can be deleted from Home Assistant."""
    await setup_integration(hass, config_entry)
    registry = dr.async_get(hass)
    stale = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "OLDOLDOLDOLD")}
    )
    current = registry.async_get_device_by_identifier((DOMAIN, MAC), config_entry.entry_id)

    from custom_components.inverterzone import async_remove_config_entry_device

    assert await async_remove_config_entry_device(hass, config_entry, stale)
    assert not await async_remove_config_entry_device(hass, config_entry, current)
