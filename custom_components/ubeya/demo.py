"""Synthetic API-shaped data for local integration testing only.

No customer data, captured Ubeya responses, credentials or session tokens are
bundled with this custom integration.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def _shift_time(day, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo("Europe/London"))


def _times(start: datetime, end: datetime) -> dict[str, str]:
    return {
        "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
        "startTimeUTC": start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "endTimeUTC": end.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_demo_responses(now: datetime) -> tuple[dict, dict, dict, dict, dict]:
    """Return bookings, positions, locations, timesheets and payroll payloads."""
    today = now.astimezone(ZoneInfo("Europe/London")).date()
    past_day = today - timedelta(days=2)
    future_days = [today + timedelta(days=1), today + timedelta(days=4)]

    locations = {"data": [{
        "id": 20, "name": "Example Venue", "address": "Demo Street, Example Town",
        "timezoneName": "Europe/London", "lat": 51.5, "lng": -0.12,
    }]}
    positions = {"data": [{"id": 10, "slug": "Demo Supervisor", "jobDescription": None}]}

    def shift_payload(identifier: int, start: datetime, end: datetime) -> dict:
        return {
            "id": identifier, "date": start.date().isoformat(), "positionId": 10,
            "locationId": 20, **_times(start, end),
            "comments": "Example position note",
            "project": {"name": "Example Event", "locationId": 999,
                        "comments": "Synthetic event instructions"},
        }

    bookings = []
    timesheets = []
    for index, day in enumerate(future_days, start=1):
        start, end = _shift_time(day, 9), _shift_time(day, 17)
        raw = shift_payload(index, start, end)
        bookings.append({
            **raw,
            "employeeSlot": {"timesheetId": 100 + index},
            "confirmation": {"isConfirmed": True},
            "wage": {"hourlyWage": 15.50, "flatWage": 0, "flatHours": 0},
        })
        timesheets.append({"id": 100 + index, "shift": raw, "startTime": None,
                           "endTime": None, "breaktimes": [], "userReportedStartTime": None,
                           "userReportedEndTime": None})

    past_start, past_end = _shift_time(past_day, 9), _shift_time(past_day, 17, 30)
    past_shift = shift_payload(3, past_start, past_end)
    timesheets.append({
        "id": 103, "shift": past_shift,
        "startTime": past_start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime": past_end.strftime("%Y-%m-%d %H:%M:%S"),
        "userReportedStartTime": None, "userReportedEndTime": None,
        "breaktimes": [{"id": 1, "startTime": _shift_time(past_day, 12).strftime("%Y-%m-%d %H:%M:%S"),
                        "endTime": _shift_time(past_day, 12, 30).strftime("%Y-%m-%d %H:%M:%S")}],
    })
    payroll = {"data": [{
        "timesheetId": 103, "date": past_day.isoformat(), "value": "124.000",
        "currency": {"code": "GBP", "symbol": "£"},
        "wage": {"hourlyWage": 15.50, "flatWage": 0},
        "aggregatedHours": {"regular": 8, "overtime": 0, "overtime2": 0,
                            "holidayRegular": 0, "holidayOvertime": 0,
                            "holidayOvertime2": 0},
        "breakMinutes": 30,
    }]}

    return {"data": bookings}, positions, locations, {"data": timesheets}, payroll
