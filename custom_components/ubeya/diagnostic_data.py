"""Minimal diagnostics summaries without user or employer-level details."""

from __future__ import annotations

from .models import UbeyaSnapshot


def diagnostics_summary(snapshot: UbeyaSnapshot | None, mode: str) -> dict:
    """No raw API payloads, shift dates, amounts, addresses or credentials."""
    return {
        "mode": mode,
        "has_data": snapshot is not None,
        "counts": {
            "shifts": len(snapshot.shifts) if snapshot else 0,
            "timesheets": len(snapshot.timesheets) if snapshot else 0,
            "payroll_records": len(snapshot.payroll) if snapshot else 0,
        },
        "currency": snapshot.currency if snapshot else None,
    }
