"""Tests for the inverterzone sensors and binary sensors."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from custom_components.inverterzone.const import BASE_URL

from .conftest import load, setup_integration

P = "sensor.home_inverter_"


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} was not created"
    return state.state


async def test_live_sensors(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Live readings map to the right entities, values and units."""
    await setup_integration(hass, config_entry)

    expected = {
        "solar_power": "3150",
        "pv1_power": "2100",
        "pv1_voltage": "310.5",
        "pv2_current": "3.6",
        "load_power": "1240",
        "load_apparent_power": "1350",
        "output_voltage": "230.1",
        "output_frequency": "50.0",
        "load": "20",
        "battery": "85",
        "battery_voltage": "52.4",
        "battery_power": "1572",
        "battery_status": "charging",
        "grid_voltage": "0.0",
        "grid_power": "0",
        "grid_feed_in_power": "unknown",
        "inverter_mode": "battery",
        "heat_sink_temperature": "41",
        "bus_voltage": "380.0",
        "charging_stage": "Bulk",
        "fault": "No fault",
        "bms_state_of_charge": "85",
        "bms_max_discharge_current": "120",
        "last_reading": "2026-11-19T10:00:00+00:00",
    }
    for suffix, value in expected.items():
        assert _state(hass, P + suffix) == value, suffix

    solar = hass.states.get(P + "solar_power")
    assert solar.attributes[ATTR_UNIT_OF_MEASUREMENT] == "W"
    assert solar.attributes[ATTR_DEVICE_CLASS] == "power"
    assert solar.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    # PV3 is not reported and the inverter temperature is null: no entities for them.
    assert hass.states.get(P + "pv3_power") is None
    assert hass.states.get(P + "inverter_temperature") is None

    assert hass.states.get("binary_sensor.home_inverter_online").state == "on"
    assert hass.states.get("binary_sensor.home_inverter_grid_available").state == "off"
    assert hass.states.get("binary_sensor.home_inverter_bms_connected").state == "on"


async def test_energy_sensors(
    hass: HomeAssistant, mock_cloud: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Today's totals are kWh counters usable in the Energy dashboard."""
    await setup_integration(hass, config_entry)

    expected = {
        "solar_energy_today": "12.3",
        "solar_to_battery_today": "4.1",
        "grid_import_today": "2.2",
        "grid_to_battery_today": "0.5",
        "grid_export_today": "0.0",
        "battery_discharge_today": "3.4",
        "battery_charge_today": "4.6",
        "load_energy_today": "13.0",
        "total_supplied_today": "17.9",
        "peak_solar_power_today": "4210",
        "peak_load_power_today": "3120",
        "grid_off_today": "185",
    }
    for suffix, value in expected.items():
        assert _state(hass, P + suffix) == value, suffix

    solar = hass.states.get(P + "solar_energy_today")
    assert solar.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kWh"
    assert solar.attributes[ATTR_DEVICE_CLASS] == "energy"
    assert solar.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING


async def test_offline_dongle(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A dongle that stopped reporting shows as offline instead of stale live values."""
    solar = load("solar_data.json")
    solar["data"]["online"] = False
    aioclient_mock.get(f"{BASE_URL}/getDevices", json=load("devices.json"))
    aioclient_mock.get(f"{BASE_URL}/getSolarData", json=solar)
    aioclient_mock.get(f"{BASE_URL}/getEnergyData", json=load("energy_data.json"))

    await setup_integration(hass, config_entry)

    assert _state(hass, P + "solar_power") == "unavailable"
    assert _state(hass, P + "battery") == "unavailable"
    assert _state(hass, "binary_sensor.home_inverter_online") == "off"
    assert _state(hass, P + "last_reading") == "2026-11-19T10:00:00+00:00"
    assert _state(hass, P + "solar_energy_today") == "12.3"
