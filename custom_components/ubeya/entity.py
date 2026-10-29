"""Shared entity identity for the Ubeya integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UbeyaCoordinator


class UbeyaEntity(CoordinatorEntity[UbeyaCoordinator]):
    """No physical HA device is created for an online employee account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UbeyaCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name

