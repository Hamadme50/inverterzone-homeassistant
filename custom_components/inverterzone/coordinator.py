"""Polling for inverterzone: live readings every 15 s, today's energy every 30 min."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Device,
    InverterZoneApi,
    InverterZoneAuthError,
    InverterZoneDeviceNotLinkedError,
    InverterZoneError,
    InverterZoneNoDataError,
)
from .const import DOMAIN, ENERGY_DAY_END, ENERGY_INTERVAL, LIVE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceCoordinators:
    """The two coordinators of one inverter."""

    device: Device
    live: LiveCoordinator
    energy: EnergyCoordinator


@dataclass
class InverterZoneData:
    """What a config entry holds while it is loaded."""

    api: InverterZoneApi
    devices: dict[str, DeviceCoordinators]


type InverterZoneConfigEntry = ConfigEntry[InverterZoneData]


class InverterZoneCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls one endpoint for one inverter."""

    config_entry: InverterZoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InverterZoneConfigEntry,
        api: InverterZoneApi,
        device: Device,
        kind: str,
        interval: timedelta,
    ) -> None:
        """Set up polling of [kind] for [device]."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {kind} {device.mac}",
            update_interval=interval,
        )
        self.api = api
        self.device = device

    async def _fetch(self) -> dict[str, Any]:
        raise NotImplementedError

    async def _async_update_data(self) -> dict[str, Any]:
        mac = self.device.mac
        try:
            return await self._fetch()
        except InverterZoneAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except InverterZoneDeviceNotLinkedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_linked",
                translation_placeholders={"mac": mac},
            ) from err
        except InverterZoneNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={"mac": mac},
            ) from err
        except InverterZoneError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"mac": mac, "error": str(err)},
            ) from err


class LiveCoordinator(InverterZoneCoordinator):
    """The latest reading, every 15 seconds."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InverterZoneConfigEntry,
        api: InverterZoneApi,
        device: Device,
    ) -> None:
        """Poll the live reading of [device]."""
        super().__init__(hass, entry, api, device, "live", LIVE_INTERVAL)

    async def _fetch(self) -> dict[str, Any]:
        return await self.api.solar_data(self.device.mac)


class EnergyCoordinator(InverterZoneCoordinator):
    """Today's energy totals, every 30 minutes and once more just before local midnight.

    The cloud's "today" counters reset at midnight in the site's timezone. Polling every 30
    minutes alone could leave up to half an hour of the day unrecorded, so one extra refresh
    runs at 23:55 site time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InverterZoneConfigEntry,
        api: InverterZoneApi,
        device: Device,
    ) -> None:
        """Poll today's energy of [device]."""
        super().__init__(hass, entry, api, device, "energy", ENERGY_INTERVAL)
        self._unsub_day_end: CALLBACK_TYPE | None = None
        # Also cancelled when setup fails after the first refresh scheduled it.
        entry.async_on_unload(self._cancel_day_end)

    async def _fetch(self) -> dict[str, Any]:
        data = await self.api.energy_data(self.device.mac)
        self._schedule_day_end(data.get("timezone"))
        return data

    @callback
    def _schedule_day_end(self, timezone: str | None) -> None:
        if self._unsub_day_end is not None:
            return
        zone = (dt_util.get_time_zone(timezone) if timezone else None) or dt_util.get_default_time_zone()
        now = dt_util.now(zone)
        target = now.replace(
            hour=ENERGY_DAY_END.hour,
            minute=ENERGY_DAY_END.minute,
            second=0,
            microsecond=0,
        )
        if target <= now:
            target = (target + timedelta(days=1)).replace(
                hour=ENERGY_DAY_END.hour, minute=ENERGY_DAY_END.minute
            )
        self._unsub_day_end = async_track_point_in_utc_time(
            self.hass, self._async_day_end, dt_util.as_utc(target)
        )

    async def _async_day_end(self, _now: datetime) -> None:
        self._unsub_day_end = None
        await self.async_refresh()

    @callback
    def _cancel_day_end(self) -> None:
        if self._unsub_day_end is not None:
            self._unsub_day_end()
            self._unsub_day_end = None

    async def async_shutdown(self) -> None:
        """Cancel the midnight refresh too."""
        self._cancel_day_end()
        await super().async_shutdown()
