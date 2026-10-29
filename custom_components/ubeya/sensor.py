"""Shift, hour and income sensors derived from normalized Ubeya data."""

from __future__ import annotations

from datetime import timedelta
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .coordinator import UbeyaCoordinator
from .entity import UbeyaEntity
from .models import ZERO, money


SENSOR_NAMES = {
    "next_shift": "Next shift",
    "next_position": "Next position",
    "next_location": "Next location",
    "next_shift_estimated_earnings": "Next shift estimated earnings",
    "shifts_next_7_days": "Shifts next 7 days",
    "confirmed_shifts_next_7_days": "Confirmed shifts next 7 days",
    "scheduled_hours_next_7_days": "Scheduled hours next 7 days",
    "shifts_this_month": "Shifts this month",
    "scheduled_hours_this_month": "Scheduled hours this month",
    "approved_shifts_this_month": "Approved shifts this month",
    "approved_hours_this_month": "Approved hours this month",
    "approved_earnings_this_month": "Approved earnings this month",
    "approved_earnings_this_week": "Approved earnings this week",
    "approved_earnings_last_30_days": "Approved earnings last 30 days",
    "approved_earnings_last_month": "Approved earnings last month",
    "approved_earnings_this_year": "Approved earnings this year",
    "estimated_upcoming_earnings_this_month": "Estimated upcoming earnings this month",
    "last_sync": "Last sync",
}

MONEY_KEYS = {
    "next_shift_estimated_earnings",
    "approved_earnings_this_week",
    "approved_earnings_last_30_days",
    "approved_earnings_this_month",
    "approved_earnings_last_month",
    "approved_earnings_this_year",
    "estimated_upcoming_earnings_this_month",
}
HOURS_KEYS = {
    "scheduled_hours_this_month",
    "scheduled_hours_next_7_days",
    "approved_hours_this_month",
}


class UbeyaSensor(UbeyaEntity, SensorEntity):
    """Expose native HA scalar values, not large raw API attributes."""

    def __init__(self, coordinator: UbeyaCoordinator, key: str) -> None:
        super().__init__(coordinator, key, SENSOR_NAMES[key])
        self.key = key
        if key in MONEY_KEYS:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_suggested_display_precision = 2
        elif key in {"next_shift", "last_sync"}:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if key == "last_sync":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.key in MONEY_KEYS:
            return self.coordinator.data.currency
        if self.key in HOURS_KEYS:
            return "h"
        return None

    @property
    def native_value(self):
        now = dt_util.now()
        local_now = dt_util.as_local(now)
        data = self.coordinator.data
        shift = data.next_shift(now)
        year, month = local_now.year, local_now.month

        upcoming_end = now + timedelta(days=7)
        week_start = local_now.date() - timedelta(days=local_now.weekday())
        week_end = week_start + timedelta(days=7)

        if self.key == "next_shift":
            return shift.start if shift else None
        if self.key == "next_position":
            return shift.position if shift else None
        if self.key == "next_location":
            return shift.location_name if shift else None
        if self.key == "next_shift_estimated_earnings":
            if not shift or shift.estimated_earnings is None:
                return None
            return float(money(shift.estimated_earnings))
        if self.key == "shifts_next_7_days":
            return len(data.shifts_starting_between(now, upcoming_end))
        if self.key == "confirmed_shifts_next_7_days":
            return sum(
                s.confirmed is True for s in data.shifts_starting_between(now, upcoming_end)
            )
        if self.key == "scheduled_hours_next_7_days":
            return round(float(data.scheduled_hours_between(now, upcoming_end)), 2)
        if self.key == "shifts_this_month":
            return len(data.monthly_shifts(year, month))
        if self.key == "scheduled_hours_this_month":
            return round(float(data.monthly_scheduled_hours(year, month)), 2)
        if self.key == "approved_shifts_this_month":
            return len(data.payroll_for_month(year, month))
        if self.key == "approved_hours_this_month":
            return round(float(data.approved_hours(year, month)), 2)
        if self.key == "approved_earnings_this_month":
            return float(money(data.approved_earnings(year, month)))
        if self.key == "approved_earnings_this_week":
            return float(money(data.approved_earnings_between(week_start, week_end)))
        if self.key == "approved_earnings_last_30_days":
            start_date = local_now.date() - timedelta(days=29)
            return float(
                money(data.approved_earnings_between(
                    start_date, local_now.date() + timedelta(days=1)
                ))
            )
        if self.key == "approved_earnings_last_month":
            last_month = local_now.replace(day=1) - timedelta(days=1)
            return float(money(data.approved_earnings(last_month.year, last_month.month)))
        if self.key == "approved_earnings_this_year":
            return float(money(data.annual_earnings(year)))
        if self.key == "estimated_upcoming_earnings_this_month":
            future = [
                s for s in data.monthly_shifts(year, month)
                if s.start > now
            ]
            estimates = [s.estimated_earnings for s in future]
            if any(value is None for value in estimates):
                return None
            return float(money(sum((v for v in estimates if v is not None), ZERO)))
        if self.key == "last_sync":
            return data.fetched_at
        return None

    @property
    def extra_state_attributes(self):
        if self.key not in {
            "next_shift", "next_position", "next_location", "next_shift_estimated_earnings"
        }:
            return None
        shift = self.coordinator.data.next_shift(dt_util.now())
        if not shift:
            return None
        return {
            "event": shift.title,
            "position": shift.position,
            "location": shift.location_name,
            "address": shift.address,
            "end": shift.end.isoformat(),
            "confirmed": shift.confirmed,
        }


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    async_add_entities([UbeyaSensor(entry.runtime_data, key) for key in SENSOR_NAMES])

