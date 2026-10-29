"""Read-only calendar of employee shifts."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .coordinator import UbeyaCoordinator
from .entity import UbeyaEntity
from .models import Shift


def _calendar_event(shift: Shift) -> CalendarEvent:
    description = []
    if shift.position:
        description.append(f"Position: {shift.position}")
    if shift.confirmed is not None:
        description.append(f"Confirmed: {'Yes' if shift.confirmed else 'No'}")
    if shift.notes:
        description.append(f"Shift notes: {shift.notes}")
    if shift.event_notes:
        description.append(f"Event instructions: {shift.event_notes}")
    return CalendarEvent(
        start=shift.start,
        end=shift.end,
        summary=f"{shift.title} — {shift.location_name}" if shift.location_name else shift.title,
        location=shift.address or shift.location_name,
        description="\n\n".join(description) if description else None,
        uid=f"ubeya-shift-{shift.id}",
    )


class UbeyaCalendar(UbeyaEntity, CalendarEntity):
    """Home Assistant's native calendar.get_events API is supported."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: UbeyaCoordinator) -> None:
        super().__init__(coordinator, "shifts", "Shifts")

    @property
    def event(self) -> CalendarEvent | None:
        shift = self.coordinator.data.current_or_next_shift(dt_util.now())
        return _calendar_event(shift) if shift else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return [
            _calendar_event(shift)
            for shift in self.coordinator.data.shifts_in_range(start_date, end_date)
        ]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([UbeyaCalendar(entry.runtime_data)])

