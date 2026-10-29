"""Pure data model for the Ubeya Crew API.

This module deliberately has no Home Assistant imports so the normalization and
money calculations can be tested independently of a running HA instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ZERO = Decimal("0")
PENNY = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    """Round only at display boundaries; Ubeya returns sub-penny values."""
    return value.quantize(PENNY, rounding=ROUND_HALF_EVEN)


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _datetime(value: str, zone: ZoneInfo, utc_value: str | None = None) -> datetime:
    """Prefer Ubeya's UTC schedule field to avoid DST ambiguity."""
    if utc_value:
        parsed = datetime.fromisoformat(utc_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(zone)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)


def _rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise ValueError("Ubeya response 'data' must be a list")
    return data


@dataclass(frozen=True, slots=True)
class Shift:
    id: int
    start: datetime
    end: datetime
    title: str
    position: str | None
    location_name: str | None
    address: str | None
    notes: str | None
    event_notes: str | None
    confirmed: bool | None
    hourly_rate: Decimal | None
    flat_wage: Decimal | None
    timesheet_id: int | None

    @property
    def scheduled_hours(self) -> Decimal:
        seconds = (self.end - self.start).total_seconds()
        return Decimal(str(max(seconds, 0))) / Decimal(3600)

    @property
    def estimated_earnings(self) -> Decimal | None:
        """Simple gross estimate; no break/overtime/flat-pay guesses."""
        if self.flat_wage is not None and self.flat_wage > ZERO:
            return None
        if self.hourly_rate is None:
            return None
        return self.scheduled_hours * self.hourly_rate


@dataclass(frozen=True, slots=True)
class Timesheet:
    id: int
    shift_id: int
    start: datetime | None
    end: datetime | None
    reported_start: datetime | None
    reported_end: datetime | None
    break_minutes: Decimal


@dataclass(frozen=True, slots=True)
class PayrollRecord:
    timesheet_id: int
    date: date
    value: Decimal
    currency: str
    hourly_rate: Decimal
    break_minutes: Decimal
    hour_categories: tuple[tuple[str, Decimal], ...]

    @property
    def paid_hours(self) -> Decimal:
        return sum((amount for _, amount in self.hour_categories), ZERO)


@dataclass(frozen=True, slots=True)
class UbeyaSnapshot:
    shifts: tuple[Shift, ...]
    timesheets: tuple[Timesheet, ...]
    payroll: tuple[PayrollRecord, ...]
    fetched_at: datetime

    @property
    def currency(self) -> str | None:
        return self.payroll[-1].currency if self.payroll else None

    def current_shift(self, now: datetime) -> Shift | None:
        return next((s for s in self.shifts if s.start <= now < s.end), None)

    def next_shift(self, now: datetime) -> Shift | None:
        return next((s for s in self.shifts if s.start > now), None)

    def current_or_next_shift(self, now: datetime) -> Shift | None:
        return self.current_shift(now) or self.next_shift(now)

    def shifts_in_range(self, start: datetime, end: datetime) -> tuple[Shift, ...]:
        """Calendar's requested interval has exclusive end boundaries."""
        return tuple(s for s in self.shifts if s.end > start and s.start < end)

    def shifts_starting_between(self, start: datetime, end: datetime) -> tuple[Shift, ...]:
        """Scheduled starts in [start, end), excluding ongoing prior shifts."""
        return tuple(s for s in self.shifts if start <= s.start < end)

    def scheduled_hours_between(self, start: datetime, end: datetime) -> Decimal:
        return sum(
            (s.scheduled_hours for s in self.shifts_starting_between(start, end)),
            ZERO,
        )

    def monthly_shifts(self, year: int, month: int) -> tuple[Shift, ...]:
        return tuple(
            s for s in self.shifts
            if s.start.year == year and s.start.month == month
        )

    def monthly_scheduled_hours(self, year: int, month: int) -> Decimal:
        return sum((s.scheduled_hours for s in self.monthly_shifts(year, month)), ZERO)

    def monthly_estimate(self, year: int, month: int) -> Decimal | None:
        estimates = [s.estimated_earnings for s in self.monthly_shifts(year, month)]
        if not estimates or any(value is None for value in estimates):
            return None
        return sum((value for value in estimates if value is not None), ZERO)

    def payroll_for_month(self, year: int, month: int) -> tuple[PayrollRecord, ...]:
        return tuple(p for p in self.payroll if p.date.year == year and p.date.month == month)

    def approved_earnings(self, year: int, month: int) -> Decimal:
        return sum((p.value for p in self.payroll_for_month(year, month)), ZERO)

    def approved_earnings_between(self, start: date, end: date) -> Decimal:
        """Approved payroll records with dates in the half-open date range."""
        return sum((p.value for p in self.payroll if start <= p.date < end), ZERO)

    def approved_hours(self, year: int, month: int) -> Decimal:
        return sum((p.paid_hours for p in self.payroll_for_month(year, month)), ZERO)

    def annual_earnings(self, year: int) -> Decimal:
        return sum((p.value for p in self.payroll if p.date.year == year), ZERO)

    def completed_without_payroll(self, now: datetime) -> tuple[Timesheet, ...]:
        """Candidates only: missing payroll does not prove pending approval."""
        paid_ids = {p.timesheet_id for p in self.payroll}
        return tuple(
            t for t in self.timesheets
            if t.id not in paid_ids and t.end is not None and t.end <= now
        )


def normalize(
    bookings: Mapping[str, Any],
    positions: Mapping[str, Any],
    locations: Mapping[str, Any],
    timesheets: Mapping[str, Any],
    payroll: Mapping[str, Any],
    fetched_at: datetime,
) -> UbeyaSnapshot:
    """Join employee-visible API responses without exposing unrelated records."""
    position_lookup = {int(p["id"]): p.get("slug") for p in _rows(positions)}
    location_lookup = {int(p["id"]): p for p in _rows(locations)}
    normalized_shifts: dict[int, Shift] = {}

    def build_shift(
        raw: Mapping[str, Any],
        *,
        booking: Mapping[str, Any] | None,
        timesheet_id: int | None,
    ) -> Shift:
        # IMPORTANT: use the shift-specific location, not project.locationId.
        location = location_lookup.get(raw.get("locationId"), {})
        zone = _zone(location.get("timezoneName"))
        project = raw.get("project") or {}
        wage = (booking or {}).get("wage") or {}
        confirmation = (booking or {}).get("confirmation")
        return Shift(
            id=int(raw["id"]),
            start=_datetime(raw["startTime"], zone, raw.get("startTimeUTC")),
            end=_datetime(raw["endTime"], zone, raw.get("endTimeUTC")),
            title=str(project.get("name") or "Shift"),
            position=position_lookup.get(raw.get("positionId")),
            location_name=location.get("name"),
            address=location.get("address"),
            notes=raw.get("comments"),
            event_notes=project.get("comments"),
            confirmed=confirmation.get("isConfirmed") if isinstance(confirmation, dict) else None,
            hourly_rate=_decimal(wage.get("hourlyWage")) if wage else None,
            flat_wage=_decimal(wage.get("flatWage")) if wage else None,
            timesheet_id=timesheet_id,
        )

    for raw in _rows(bookings):
        employee_slot = raw.get("employeeSlot") or {}
        shift = build_shift(raw, booking=raw, timesheet_id=employee_slot.get("timesheetId"))
        normalized_shifts[shift.id] = shift

    normalized_timesheets = []
    for raw in _rows(timesheets):
        shift_raw = raw.get("shift")
        if not isinstance(shift_raw, dict):
            continue
        shift_id = int(shift_raw["id"])
        location = location_lookup.get(shift_raw.get("locationId"), {})
        zone = _zone(location.get("timezoneName"))

        def optional_time(key: str) -> datetime | None:
            return _datetime(raw[key], zone) if raw.get(key) else None

        breaks = ZERO
        for entry in raw.get("breaktimes") or []:
            if entry.get("startTime") and entry.get("endTime"):
                duration = _datetime(entry["endTime"], zone) - _datetime(entry["startTime"], zone)
                breaks += Decimal(str(max(duration.total_seconds(), 0))) / Decimal(60)

        normalized_timesheets.append(Timesheet(
            id=int(raw["id"]),
            shift_id=shift_id,
            start=optional_time("startTime"),
            end=optional_time("endTime"),
            reported_start=optional_time("userReportedStartTime"),
            reported_end=optional_time("userReportedEndTime"),
            break_minutes=breaks,
        ))
        # Historical shifts are only present in /timesheets/history.
        if shift_id not in normalized_shifts:
            normalized_shifts[shift_id] = build_shift(shift_raw, booking=None, timesheet_id=int(raw["id"]))

    normalized_payroll = []
    for raw in _rows(payroll):
        categories = raw.get("aggregatedHours") or {}
        currency = raw.get("currency") or {}
        normalized_payroll.append(PayrollRecord(
            timesheet_id=int(raw["timesheetId"]),
            date=date.fromisoformat(raw["date"][:10]),
            value=_decimal(raw.get("value")),
            currency=str(currency.get("code") or ""),
            hourly_rate=_decimal((raw.get("wage") or {}).get("hourlyWage")),
            break_minutes=_decimal(raw.get("breakMinutes")),
            hour_categories=tuple((str(key), _decimal(value)) for key, value in categories.items()),
        ))

    return UbeyaSnapshot(
        shifts=tuple(sorted(normalized_shifts.values(), key=lambda s: (s.start, s.id))),
        timesheets=tuple(sorted(normalized_timesheets, key=lambda t: t.id)),
        payroll=tuple(sorted(normalized_payroll, key=lambda p: (p.date, p.timesheet_id))),
        fetched_at=fetched_at,
    )
