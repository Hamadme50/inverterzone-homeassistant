"""Base entity for inverterzone."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import InverterZoneCoordinator, LiveCoordinator


class InverterZoneEntity(CoordinatorEntity[InverterZoneCoordinator]):
    """An entity of one inverter."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: InverterZoneCoordinator, description: EntityDescription
    ) -> None:
        """Attach the entity to its inverter's device."""
        super().__init__(coordinator)
        self.entity_description = description
        device = coordinator.device
        self._attr_unique_id = f"{device.mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(device.mac))},
            manufacturer=device.brand or MANUFACTURER,
            model=device.model,
            name=device.name or device.mac,
        )

    @property
    def available(self) -> bool:
        """A live reading is shown only while the dongle is reporting.

        When the dongle has been silent for over 3 minutes the cloud still returns its last
        reading; showing that as current would be misleading.
        """
        if not super().available:
            return False
        if isinstance(self.coordinator, LiveCoordinator) and getattr(
            self.entity_description, "requires_online", True
        ):
            return bool(self.coordinator.data and self.coordinator.data.get("online"))
        return True
