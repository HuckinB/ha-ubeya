"""Test the public calendar-feed format without importing Home Assistant."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya"
sys.path.insert(0, str(COMPONENT))

from demo import build_demo_responses  # noqa: E402
from ics import render_ics  # noqa: E402
from models import normalize  # noqa: E402


class UbeyaICSTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
        self.snapshot = normalize(
            *build_demo_responses(self.now), fetched_at=self.now
        )

    def export(self, *, notes: bool = False, earnings: bool = False) -> str:
        return render_ics(
            self.snapshot.shifts,
            account_uid="example-account",
            fetched_at=self.now,
            include_notes=notes,
            include_earnings=earnings,
            currency="GBP",
        )

    @staticmethod
    def unfolded(feed: str) -> str:
        """Undo RFC 5545 continuation lines before checking logical values."""
        return feed.replace("\r\n ", "")

    def test_events_have_stable_ids_utc_timestamps_and_crlf(self):
        feed = self.export()
        self.assertTrue(feed.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(feed.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(3, feed.count("BEGIN:VEVENT\r\n"))
        self.assertIn("UID:ubeya-shift-1@example-account.ha-ubeya", feed)
        self.assertIn("DTSTART:20261030T090000Z", feed)
        self.assertIn("DTEND:20261030T170000Z", feed)
        self.assertNotIn("\n", feed.replace("\r\n", ""))

    def test_notes_and_earnings_are_explicit_opt_in(self):
        self.assertNotIn("Example position note", self.export())
        self.assertNotIn("Event instructions", self.export())
        self.assertNotIn("gross pay", self.export())
        self.assertIn("Shift notes: Example position note", self.export(notes=True))
        self.assertIn(
            "Estimated gross pay: GBP 124.00",
            self.unfolded(self.export(earnings=True)),
        )

    def test_text_escaping_and_unicode_line_folding(self):
        shift = replace(
            self.snapshot.shifts[0],
            title="Long title: " + "🚦" * 40,
            address="Town, Road; \nNEXT:hello\\world",
            notes="First\r\nSecond\nBEGIN:VEVENT",
        )
        feed = render_ics(
            [shift],
            account_uid="my-id",
            fetched_at=self.now,
            include_notes=True,
        )
        self.assertIn("Town\\, Road\\; \\nNEXT:hello\\\\world", feed)
        self.assertIn(
            "First\\nSecond\\nBEGIN:VEVENT", self.unfolded(feed)
        )
        self.assertEqual(1, feed.count("BEGIN:VEVENT\r\n"))
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in feed.split("\r\n")))

    def test_removed_shift_disappears_from_feed(self):
        before = self.export()
        after = render_ics(
            self.snapshot.shifts[1:],
            account_uid="example-account",
            fetched_at=self.now,
        )
        self.assertIn("UID:ubeya-shift-3@example-account", before)
        self.assertNotIn("UID:ubeya-shift-3@example-account", after)
        self.assertIn("UID:ubeya-shift-1@example-account", after)

    def test_naive_timestamps_are_rejected(self):
        shift = replace(
            self.snapshot.shifts[0],
            start=datetime(2026, 10, 29, 12),
        )
        with self.assertRaises(ValueError):
            render_ics([shift], account_uid="example", fetched_at=self.now)


if __name__ == "__main__":
    unittest.main()
