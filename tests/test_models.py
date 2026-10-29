"""Run with the standard library; Home Assistant is not required."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya"
sys.path.insert(0, str(COMPONENT))

from demo import build_demo_responses  # noqa: E402
from models import money, normalize  # noqa: E402


class UbeyaModelTests(unittest.TestCase):
    def make_snapshot(self, now: datetime):
        return normalize(*build_demo_responses(now), fetched_at=now)

    def test_booking_and_timesheet_records_merge(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        self.assertEqual(3, len(snapshot.shifts))
        self.assertEqual(3, len(snapshot.timesheets))
        self.assertEqual(1, len(snapshot.payroll))
        self.assertEqual([3, 1, 2], [shift.id for shift in snapshot.shifts])

    def test_shift_location_override_and_position_slug(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        shift = self.make_snapshot(now).next_shift(now)
        self.assertIsNotNone(shift)
        self.assertEqual("Example Venue", shift.location_name)
        self.assertEqual("Demo Supervisor", shift.position)
        self.assertTrue(shift.confirmed)
        self.assertEqual(Decimal("124.00"), money(shift.estimated_earnings))
        self.assertEqual("Example position note", shift.notes)

    def test_calendar_range_uses_exclusive_boundaries(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        shift = snapshot.next_shift(now)
        self.assertEqual(1, len(snapshot.shifts_in_range(shift.start, shift.end)))
        self.assertEqual(0, len(snapshot.shifts_in_range(shift.end, shift.end + timedelta(hours=1))))
        self.assertEqual(0, len(snapshot.shifts_in_range(shift.start - timedelta(hours=1), shift.start)))

    def test_shifts_start_count_excludes_previous_ongoing_shift(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        next_shift = snapshot.next_shift(now)
        self.assertEqual((next_shift,), snapshot.shifts_starting_between(next_shift.start, next_shift.end))
        self.assertEqual(Decimal("8"), snapshot.scheduled_hours_between(next_shift.start, next_shift.end))
        self.assertEqual((), snapshot.shifts_starting_between(next_shift.end, next_shift.end))

    def test_summer_utc_to_london(self):
        now = datetime(2026, 7, 1, 10, tzinfo=timezone.utc)
        shift = self.make_snapshot(now).next_shift(now)
        self.assertEqual(timedelta(hours=1), shift.start.utcoffset())
        self.assertEqual(8, shift.start.astimezone(timezone.utc).hour)
        self.assertEqual(9, shift.start.hour)

    def test_money_uses_decimal_and_half_even_rounding(self):
        self.assertEqual(Decimal("372.94"), money(Decimal("372.945")))
        self.assertEqual(Decimal("2757.68"), money(Decimal("2757.676")))

    def test_payroll_uses_reported_value_and_paid_hours(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        self.assertEqual(Decimal("124.000"), snapshot.approved_earnings(2026, 10))
        self.assertEqual(Decimal("8"), snapshot.approved_hours(2026, 10))
        self.assertEqual(Decimal("30"), snapshot.payroll[0].break_minutes)
        self.assertEqual("GBP", snapshot.currency)
        self.assertEqual(1, len(snapshot.payroll_for_month(2026, 10)))

    def test_approved_earnings_between_excludes_upper_date(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        payday = snapshot.payroll[0].date
        self.assertEqual(
            Decimal("124.000"),
            snapshot.approved_earnings_between(payday, payday + timedelta(days=1)),
        )
        self.assertEqual(
            Decimal("0"),
            snapshot.approved_earnings_between(payday + timedelta(days=1), date(2027, 1, 1)),
        )

    def test_future_timesheets_are_not_pending_payroll(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        self.assertEqual((), snapshot.completed_without_payroll(now))

    def test_missing_pay_rate_disables_historical_estimate(self):
        now = datetime(2026, 10, 29, 12, tzinfo=ZoneInfo("Europe/London"))
        snapshot = self.make_snapshot(now)
        historical = next(s for s in snapshot.shifts if s.id == 3)
        self.assertIsNone(historical.estimated_earnings)


if __name__ == "__main__":
    unittest.main()
