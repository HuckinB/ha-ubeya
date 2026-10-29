"""Tests for private Ubeya cookie jars with artificial values only."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ubeya"
PACKAGE = "ubeya_alpha_test"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(COMPONENT)]
    sys.modules[PACKAGE] = package

auth = importlib.import_module(f"{PACKAGE}.auth")
api = importlib.import_module(f"{PACKAGE}.api")


class UbeyaSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cookies_reach_crew_from_auth_domain(self):
        values = {
            "user_access_token": "sample-access-not-a-real-token",
            "user_refresh_token": "sample-refresh-not-a-real-token",
        }
        async with auth.new_session(values) as session:
            self.assertEqual(values, auth.export_cookies(session))
            self.assertTrue(auth.has_session_cookies(auth.export_cookies(session)))

    async def test_sessions_are_isolated(self):
        async with auth.new_session({"user_access_token": "fake-one"}) as first:
            async with auth.new_session() as second:
                self.assertEqual({"user_access_token": "fake-one"}, auth.export_cookies(first))
                self.assertEqual({}, auth.export_cookies(second))
                self.assertFalse(auth.has_session_cookies(auth.export_cookies(first)))

    async def test_refresh_replaces_only_known_cookie_names(self):
        async with auth.new_session(
            {"user_access_token": "old", "user_refresh_token": "old-refresh"}
        ) as session:
            session.cookie_jar.update_cookies(
                auth._domain_cookies({"user_access_token": "new"}),
            )
            self.assertEqual("new", auth.export_cookies(session)["user_access_token"])
            self.assertEqual("old-refresh", auth.export_cookies(session)["user_refresh_token"])


if __name__ == "__main__":
    unittest.main()
