"""Binary sensors for inverterzone: dongle online, grid available, BMS connected."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import InverterZoneConfigEntry, InverterZoneCoordinator
from .entity import InverterZoneEntity
from .sensor import _always, _get

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class InverterZoneBinarySensorDescription(BinarySensorEntityDescription):
    """How to read one on/off state out of the live reading."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = _always
    requires_online: bool = True


BINARY_SENSORS: tuple[InverterZoneBinarySensorDescription, ...] = (
    InverterZoneBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        # This one tells whether the dongle is reporting, so it is shown while it is not.
        requires_online=False,
        value_fn=lambda d: bool(d.get("online")),
    ),
    InverterZoneBinarySensorDescription(
        key="grid_available",
        translation_key="grid_available",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d: _get(d, "grid", "available"),
    ),
    InverterZoneBinarySensorDescription(
        key="bms_connected",
        translation_key="bms_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda d: _get(d, "bms") is not None,
        value_fn=lambda d: _get(d, "bms", "connected"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InverterZoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors of every inverter on the account."""
    entities: list[InverterZoneBinarySensor] = []
    for device in entry.runtime_data.devices.values():
        data = device.live.data
        entities += [
            InverterZoneBinarySensor(device.live, description)
            for description in BINARY_SENSORS
            if (description.exists_fn is _always if data is None else description.exists_fn(data))
        ]
    async_add_entities(entities)


class InverterZoneBinarySensor(InverterZoneEntity, BinarySensorEntity):
    """One on/off state of one inverter."""

    entity_description: InverterZoneBinarySensorDescription

    def __init__(
        self,
        coordinator: InverterZoneCoordinator,
        description: InverterZoneBinarySensorDescription,
    ) -> None:
        """Set up the binary sensor."""
        super().__init__(coordinator, description)

    @property
    def is_on(self) -> bool | None:
        """The current state."""
        if self.coordinator.data is None:
            return None
        value = self.entity_description.value_fn(self.coordinator.data)
        return None if value is None else bool(value)
