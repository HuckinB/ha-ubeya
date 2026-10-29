"""Diagnostics must never leak shift details, earnings or login credentials."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya"
PACKAGE = "ubeya_alpha_test"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(COMPONENT)]
    sys.modules[PACKAGE] = package

demo = importlib.import_module(f"{PACKAGE}.demo")
models = importlib.import_module(f"{PACKAGE}.models")
diagnostic_data = importlib.import_module(f"{PACKAGE}.diagnostic_data")


class UbeyaDiagnosticsTests(unittest.TestCase):
    def test_summary_contains_aggregate_counts_only(self):
        now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        snapshot = models.normalize(*demo.build_demo_responses(now), fetched_at=now)
        diagnostics = diagnostic_data.diagnostics_summary(snapshot, "live")

        self.assertEqual("live", diagnostics["mode"])
        self.assertEqual({"shifts": 3, "timesheets": 3, "payroll_records": 1}, diagnostics["counts"])
        self.assertTrue(diagnostics["has_data"])
        payload = str(diagnostics)
        for private_value in ("Example Event", "Example Venue", "Demo Street", "124", "Example position note"):
            self.assertNotIn(private_value, payload)

    def test_empty_state_is_safe(self):
        self.assertEqual(
            {"mode": "demo", "has_data": False, "counts": {"shifts": 0, "timesheets": 0, "payroll_records": 0}, "currency": None},
            diagnostic_data.diagnostics_summary(None, "demo"),
        )


if __name__ == "__main__":
    unittest.main()
