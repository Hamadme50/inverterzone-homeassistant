"""Diagnostics for inverterzone (Settings > Devices & services > Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import InverterZoneConfigEntry

TO_REDACT = {CONF_TOKEN, CONF_EMAIL, "title", "unique_id", "local_ip", "localIp"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InverterZoneConfigEntry
) -> dict[str, Any]:
    """The entry (token and email redacted) and the latest data of every inverter."""
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "devices": {
            mac: {
                "device": {
                    "name": device.device.name,
                    "model": device.device.model,
                    "brand": device.device.brand,
                },
                "live": {
                    "last_update_success": device.live.last_update_success,
                    "data": async_redact_data(device.live.data or {}, TO_REDACT),
                },
                "energy": {
                    "last_update_success": device.energy.last_update_success,
                    "data": async_redact_data(device.energy.data or {}, TO_REDACT),
                },
            }
            for mac, device in entry.runtime_data.devices.items()
        },
    }
