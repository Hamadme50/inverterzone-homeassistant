"""The inverterzone integration: solar inverter data from the inverterzone cloud."""

from __future__ import annotations

import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InverterZoneApi, InverterZoneAuthError, InverterZoneError
from .const import CONF_TOKEN, DOMAIN
from .coordinator import (
    DeviceCoordinators,
    EnergyCoordinator,
    InverterZoneConfigEntry,
    InverterZoneData,
    LiveCoordinator,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: InverterZoneConfigEntry) -> bool:
    """Load the account's inverters and start polling them."""
    api = InverterZoneApi(async_get_clientsession(hass), entry.data[CONF_TOKEN])
    try:
        devices = await api.devices()
    except InverterZoneAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="auth_failed"
        ) from err
    except InverterZoneError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinators: dict[str, DeviceCoordinators] = {}
    for device in devices:
        coordinators[device.mac] = DeviceCoordinators(
            device=device,
            live=LiveCoordinator(hass, entry, api, device),
            energy=EnergyCoordinator(hass, entry, api, device),
        )

    # One inverter that has never reported, or is briefly failing, must not keep the others
    # from loading: refresh each on its own and let failed ones retry on their interval.
    await asyncio.gather(
        *(
            coordinator.async_refresh()
            for device in coordinators.values()
            for coordinator in (device.live, device.energy)
        )
    )
    for device in coordinators.values():
        for coordinator in (device.live, device.energy):
            if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
                raise coordinator.last_exception

    entry.runtime_data = InverterZoneData(api=api, devices=coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InverterZoneConfigEntry) -> bool:
    """Stop polling."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for device in entry.runtime_data.devices.values():
            await device.live.async_shutdown()
            await device.energy.async_shutdown()
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: InverterZoneConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow deleting an inverter that is no longer on the account."""
    macs = entry.runtime_data.devices.keys()
    return not any(
        domain == DOMAIN and identifier in macs
        for domain, identifier in device_entry.identifiers
    )
