"""Audit-log parsing (rota changes) - standard library only."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya"
sys.path.insert(0, str(COMPONENT))

from models import normalize_audit_log  # noqa: E402

LONDON = ZoneInfo("Europe/London")

# Shape of a real EmployeeShiftUpdated entry, with made-up ids and names.
SHIFT_UPDATED = {
    "id": 900001,
    "createdAt": "2026-11-24 16:36:03",
    "type": "EmployeeShiftUpdated",
    "accountId": 1,
    "tenantId": 1,
    "branchId": None,
    "timesheetId": None,
    "projectId": 4000001,
    "shiftId": 12000001,
    "employeeId": 100,
    "adminId": 200,
    "isUbeyaAdmin": False,
    "compoundType": 4,
    "data": json.dumps({
        "startTime": "2026-11-26 13:30:00",
        "endTime": "2026-11-26 17:30:00",
        "shiftName": "KART",
        "adminName": "Example Admin",
        "positionSlug": "Karting Duty Manager",
    }),
}


class AuditLogTests(unittest.TestCase):
    def test_shift_updated_entry(self):
        (event,) = normalize_audit_log([SHIFT_UPDATED], LONDON)
        self.assertEqual(900001, event.id)
        self.assertTrue(event.is_shift_change)
        self.assertEqual(12000001, event.shift_id)
        self.assertEqual(4000001, event.project_id)
        self.assertEqual("Example Admin", event.admin_name)
        self.assertEqual("KART", event.shift_name)
        self.assertEqual("Karting Duty Manager", event.position)
        self.assertEqual(datetime(2026, 11, 26, 13, 30, tzinfo=LONDON), event.start)
        self.assertEqual(datetime(2026, 11, 26, 17, 30, tzinfo=LONDON), event.end)
        self.assertEqual(datetime(2026, 11, 24, 16, 36, 3, tzinfo=timezone.utc), event.created_at)

    def test_summer_shift_times_are_local(self):
        raw = {**SHIFT_UPDATED, "data": json.dumps({"startTime": "2026-07-01 09:00:00", "endTime": "2026-07-01 17:00:00"})}
        (event,) = normalize_audit_log([raw], LONDON)
        self.assertEqual(8, event.start.astimezone(timezone.utc).hour)

    def test_wrapped_payload_and_ordering(self):
        older = {**SHIFT_UPDATED, "id": 899999, "createdAt": "2026-11-23 10:00:00"}
        events = normalize_audit_log({"data": [SHIFT_UPDATED, older]}, LONDON)
        self.assertEqual([899999, 900001], [e.id for e in events])

    def test_other_types_are_parsed_but_not_shift_changes(self):
        raw = {**SHIFT_UPDATED, "type": "EmployeeAvailabilityUpdated", "shiftId": None, "data": None}
        (event,) = normalize_audit_log([raw], LONDON)
        self.assertFalse(event.is_shift_change)
        self.assertIsNone(event.start)
        self.assertIsNone(event.admin_name)

    def test_malformed_entries_are_skipped(self):
        bad = [
            {"type": "EmployeeShiftUpdated"},  # no id
            {**SHIFT_UPDATED, "id": "x"},
            {**SHIFT_UPDATED, "createdAt": None},
            {**SHIFT_UPDATED, "id": 5, "data": "{not json"},
            "not a dict",
        ]
        events = normalize_audit_log(bad, LONDON)
        self.assertEqual([5], [e.id for e in events])
        self.assertIsNone(events[0].start)

    def test_unexpected_payload_shapes(self):
        self.assertEqual((), normalize_audit_log(None, LONDON))
        self.assertEqual((), normalize_audit_log({"data": "nope"}, LONDON))


if __name__ == "__main__":
    unittest.main()
