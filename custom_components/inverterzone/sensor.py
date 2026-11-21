"""Sensors for inverterzone: live readings and today's energy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import InverterZoneConfigEntry, InverterZoneCoordinator
from .entity import InverterZoneEntity

PARALLEL_UPDATES = 0

INVERTER_MODES = {
    "P": "power_on",
    "S": "standby",
    "L": "line",
    "B": "battery",
    "F": "fault",
    "H": "power_saving",
    "D": "shutdown",
}
BATTERY_STATUSES = ["charging", "discharging", "idle"]


def _get(data: dict[str, Any] | None, *path: str) -> Any:
    """data[path[0]][path[1]]..., or None when any step is missing."""
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _always(_: dict[str, Any]) -> bool:
    return True


def _has(*path: str) -> Callable[[dict[str, Any]], bool]:
    return lambda data: _get(data, *path) is not None


def _bms_connected(data: dict[str, Any]) -> bool:
    return bool(_get(data, "bms", "connected"))


def _lower(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) else None


def _timestamp(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _battery_charge_today(data: dict[str, Any]) -> float | None:
    parts = [
        _get(data, "today", "solarToBatteryKwh"),
        _get(data, "today", "gridToBatteryKwh"),
    ]
    known = [p for p in parts if p is not None]
    return round(sum(known), 1) if known else None


@dataclass(frozen=True, kw_only=True)
class InverterZoneSensorDescription(SensorEntityDescription):
    """How to read one sensor out of a coordinator's data."""

    value_fn: Callable[[dict[str, Any]], StateType | datetime]
    exists_fn: Callable[[dict[str, Any]], bool] = _always
    requires_online: bool = True
    # Extra state attributes; the dashboard cards read these (e.g. yesterday's figure).
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _power(
    key: str, *path: str, translation_key: str | None = None, **kw: Any
) -> InverterZoneSensorDescription:
    return InverterZoneSensorDescription(
        key=key,
        translation_key=translation_key or key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda d: _get(d, *path),
        **kw,
    )


def _voltage(
    key: str, *path: str, translation_key: str | None = None, **kw: Any
) -> InverterZoneSensorDescription:
    return InverterZoneSensorDescription(
        key=key,
        translation_key=translation_key or key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda d: _get(d, *path),
        **kw,
    )


def _current(
    key: str, *path: str, translation_key: str | None = None, **kw: Any
) -> InverterZoneSensorDescription:
    return InverterZoneSensorDescription(
        key=key,
        translation_key=translation_key or key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda d: _get(d, *path),
        **kw,
    )


def _frequency(key: str, *path: str) -> InverterZoneSensorDescription:
    return InverterZoneSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=1,
        value_fn=lambda d: _get(d, *path),
    )


def _energy(
    key: str,
    field: str,
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> InverterZoneSensorDescription:
    return InverterZoneSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.ENERGY,
        # "Today" counters reset at local midnight; Home Assistant reads a drop as a new cycle.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d: _get(d, "today", field),
        attrs_fn=attrs_fn or (lambda d: {"yesterday_same_time": _get(d, "compare", field)}),
    )


def _solar_today_attrs(data: dict[str, Any]) -> dict[str, Any]:
    """Yesterday's figure plus what the stats card needs for "Saved" and its comparison label."""
    return {
        "yesterday_same_time": _get(data, "compare", "solarKwh"),
        "compare_label": _get(data, "compareLabel"),
        "rate_per_kwh": _get(data, "ratePerKwh"),
    }


def _battery_charge_attrs(data: dict[str, Any]) -> dict[str, Any]:
    parts = [
        _get(data, "compare", "solarToBatteryKwh"),
        _get(data, "compare", "gridToBatteryKwh"),
    ]
    known = [p for p in parts if p is not None]
    return {"yesterday_same_time": round(sum(known), 1) if known else None}


def _pv_inputs() -> list[InverterZoneSensorDescription]:
    out: list[InverterZoneSensorDescription] = []
    # Each input has its own translation key (pv1_power, pv2_voltage...) so the dashboard
    # cards can tell the inputs apart.
    for i in (1, 2, 3):
        pv = f"pv{i}"
        out += [
            _power(f"{pv}_power", "solar", pv, "watts", exists_fn=_has("solar", pv)),
            _voltage(f"{pv}_voltage", "solar", pv, "volts", exists_fn=_has("solar", pv)),
            _current(f"{pv}_current", "solar", pv, "amps", exists_fn=_has("solar", pv)),
        ]
    return out


LIVE_SENSORS: tuple[InverterZoneSensorDescription, ...] = (
    _power("solar_power", "solar", "watts"),
    *_pv_inputs(),
    # Load (inverter output)
    _power("load_power", "load", "watts"),
    InverterZoneSensorDescription(
        key="load_apparent_power",
        translation_key="load_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        suggested_display_precision=0,
        value_fn=lambda d: _get(d, "load", "va"),
    ),
    _voltage("load_voltage", "load", "volts"),
    _current("load_current", "load", "amps"),
    _frequency("load_frequency", "load", "frequencyHz"),
    InverterZoneSensorDescription(
        key="load_percent",
        translation_key="load_percent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: _get(d, "load", "percent"),
    ),
    # Battery
    InverterZoneSensorDescription(
        key="battery",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: _get(d, "battery", "percent"),
    ),
    _voltage("battery_voltage", "battery", "volts"),
    _power("battery_power", "battery", "watts"),
    _current("battery_charge_current", "battery", "chargeAmps"),
    _current("battery_discharge_current", "battery", "dischargeAmps"),
    InverterZoneSensorDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        options=BATTERY_STATUSES,
        value_fn=lambda d: _lower(_get(d, "battery", "status")),
    ),
    # Grid
    _voltage("grid_voltage", "grid", "volts"),
    _frequency("grid_frequency", "grid", "frequencyHz"),
    _power("grid_power", "grid", "watts"),
    _power("grid_feed_in_power", "grid", "feedInWatts"),
    # Inverter
    InverterZoneSensorDescription(
        key="inverter_mode",
        translation_key="inverter_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[*INVERTER_MODES.values(), "unknown"],
        value_fn=lambda d: (
            INVERTER_MODES.get(code, "unknown")
            if (code := _get(d, "inverter", "modeCode")) is not None
            else None
        ),
    ),
    InverterZoneSensorDescription(
        key="heat_sink_temperature",
        translation_key="heat_sink_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: _get(d, "inverter", "temperatureC"),
    ),
    InverterZoneSensorDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        exists_fn=_has("inverter", "inverterTemperatureC"),
        value_fn=lambda d: _get(d, "inverter", "inverterTemperatureC"),
    ),
    _voltage("bus_voltage", "inverter", "busVolts", entity_category=EntityCategory.DIAGNOSTIC),
    InverterZoneSensorDescription(
        key="charging_stage",
        translation_key="charging_stage",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _get(d, "inverter", "chargingStage"),
    ),
    InverterZoneSensorDescription(
        key="fault",
        translation_key="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        # The cloud sends null when there is no fault.
        value_fn=lambda d: _get(d, "inverter", "fault") or "No fault",
    ),
    # Lithium BMS, only when the inverter reports one
    InverterZoneSensorDescription(
        key="bms_soc",
        translation_key="bms_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        exists_fn=_bms_connected,
        value_fn=lambda d: _get(d, "bms", "soc"),
    ),
    _voltage("bms_charge_voltage", "bms", "chargeVolts", exists_fn=_bms_connected,
             entity_category=EntityCategory.DIAGNOSTIC),
    _voltage("bms_float_voltage", "bms", "floatVolts", exists_fn=_bms_connected,
             entity_category=EntityCategory.DIAGNOSTIC),
    _voltage("bms_cutoff_voltage", "bms", "cutoffVolts", exists_fn=_bms_connected,
             entity_category=EntityCategory.DIAGNOSTIC),
    _current("bms_max_charge_current", "bms", "maxChargeAmps", exists_fn=_bms_connected,
             entity_category=EntityCategory.DIAGNOSTIC),
    _current("bms_max_discharge_current", "bms", "maxDischargeAmps", exists_fn=_bms_connected,
             entity_category=EntityCategory.DIAGNOSTIC),
    InverterZoneSensorDescription(
        key="reading_time",
        translation_key="reading_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda d: _timestamp(_get(d, "readingTime")),
    ),
)

ENERGY_SENSORS: tuple[InverterZoneSensorDescription, ...] = (
    _energy("solar_energy_today", "solarKwh", _solar_today_attrs),
    _energy("solar_to_battery_energy_today", "solarToBatteryKwh"),
    _energy("grid_import_energy_today", "gridImportKwh"),
    _energy("grid_to_battery_energy_today", "gridToBatteryKwh"),
    _energy("grid_export_energy_today", "gridExportKwh"),
    _energy("battery_discharge_energy_today", "batteryDischargeKwh"),
    InverterZoneSensorDescription(
        key="battery_charge_energy_today",
        translation_key="battery_charge_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=_battery_charge_today,
        attrs_fn=_battery_charge_attrs,
    ),
    _energy("load_energy_today", "loadKwh"),
    _energy("total_supplied_energy_today", "totalSuppliedKwh"),
    InverterZoneSensorDescription(
        key="peak_solar_power_today",
        translation_key="peak_solar_power_today",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: _get(d, "peakSolar", "watts"),
        attrs_fn=lambda d: {"time": _get(d, "peakSolar", "time")},
    ),
    InverterZoneSensorDescription(
        key="peak_load_power_today",
        translation_key="peak_load_power_today",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: _get(d, "peakLoad", "watts"),
        attrs_fn=lambda d: {"time": _get(d, "peakLoad", "time")},
    ),
    InverterZoneSensorDescription(
        key="grid_off_today",
        translation_key="grid_off_today",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: _get(d, "gridOffMinutes"),
    ),
)


def _wanted(description: InverterZoneSensorDescription, data: dict[str, Any] | None) -> bool:
    """Optional sensors (PV2/PV3, BMS...) are created only when the inverter reports them."""
    if data is None:
        return description.exists_fn is _always
    return description.exists_fn(data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of every inverter on the account."""
    entities: list[InverterZoneSensor] = []
    for device in entry.runtime_data.devices.values():
        for coordinator, descriptions in (
            (device.live, LIVE_SENSORS),
            (device.energy, ENERGY_SENSORS),
        ):
            entities += [
                InverterZoneSensor(coordinator, description)
                for description in descriptions
                if _wanted(description, coordinator.data)
            ]
    async_add_entities(entities)


class InverterZoneSensor(InverterZoneEntity, SensorEntity):
    """One reading of one inverter."""

    entity_description: InverterZoneSensorDescription

    def __init__(
        self,
        coordinator: InverterZoneCoordinator,
        description: InverterZoneSensorDescription,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> StateType | datetime:
        """The current value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra figures for the dashboard cards, without empty ones."""
        attrs_fn = self.entity_description.attrs_fn
        if attrs_fn is None or self.coordinator.data is None:
            return None
        attrs = {k: v for k, v in attrs_fn(self.coordinator.data).items() if v is not None}
        return attrs or None
