"""Generate a standards-compliant, read-only iCalendar feed of Ubeya shifts.

This module intentionally has no Home Assistant imports so it can be tested
without a running Home Assistant installation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .models import Shift


def _escape(value: str) -> str:
    """Escape RFC 5545 TEXT values, including untrusted Ubeya notes."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold at 75 UTF-8 octets; continuation lines begin with one space."""
    parts: list[str] = []
    current = ""
    length = 0
    for char in line:
        size = len(char.encode("utf-8"))
        if length + size > 75:
            parts.append(current)
            current = " "
            length = 1
        current += char
        length += size
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Shift calendar timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render_ics(
    shifts: Iterable[Shift],
    *,
    account_uid: str,
    fetched_at: datetime,
    include_notes: bool = False,
    include_earnings: bool = False,
    currency: str | None = None,
) -> str:
    """Export the available shifts with stable IDs for calendar updates."""
    stamp = _utc(fetched_at)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HuckinB//Ubeya Home Assistant//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Ubeya Shifts",
    ]

    for shift in shifts:
        summary = (
            f"{shift.title} — {shift.location_name}"
            if shift.location_name
            else shift.title
        )
        details: list[str] = []
        if shift.position:
            details.append(f"Position: {shift.position}")
        if shift.confirmed is not None:
            details.append(f"Confirmed: {'Yes' if shift.confirmed else 'No'}")
        if include_notes and shift.notes:
            details.append(f"Shift notes: {shift.notes}")
        if include_notes and shift.event_notes:
            details.append(f"Event instructions: {shift.event_notes}")
        if include_earnings and (earnings := shift.estimated_earnings) is not None:
            amount = earnings.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            details.append(
                f"Estimated gross pay: {currency or 'GBP'} {amount:.2f} "
                "(excludes breaks and payroll adjustments)"
            )

        lines.extend((
            "BEGIN:VEVENT",
            f"UID:ubeya-shift-{shift.id}@{account_uid}.ha-ubeya",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_utc(shift.start)}",
            f"DTEND:{_utc(shift.end)}",
            f"SUMMARY:{_escape(summary)}",
        ))
        if shift.address or shift.location_name:
            lines.append(f"LOCATION:{_escape(shift.address or shift.location_name)}")
        if details:
            lines.append(f"DESCRIPTION:{_escape(chr(10).join(details))}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
