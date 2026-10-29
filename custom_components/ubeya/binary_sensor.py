"""Whether a shift is currently scheduled, not a clock-in assertion."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .coordinator import UbeyaCoordinator
from .entity import UbeyaEntity


class UbeyaScheduledOnShift(UbeyaEntity, BinarySensorEntity):
    _attr_icon = "mdi:briefcase-clock"

    def __init__(self, coordinator: UbeyaCoordinator) -> None:
        super().__init__(coordinator, "scheduled_on_shift", "Scheduled on shift")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.current_shift(dt_util.now()) is not None


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    async_add_entities([UbeyaScheduledOnShift(entry.runtime_data)])
