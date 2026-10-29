"""Cookie-refresh protocol tests without network access or real credentials."""

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

api = importlib.import_module(f"{PACKAGE}.api")


class Response:
    def __init__(self, status: int, payload=None):
        self.status = status
        self.payload = payload if payload is not None else {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def json(self, **_):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class UbeyaAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_401_triggers_empty_post_and_one_get_retry(self):
        session = Session([Response(401), Response(200), Response(200, {"data": []})])
        client = api.UbeyaClient(session)
        result = await client.request("/bookings")

        self.assertEqual({"data": []}, result)
        self.assertEqual(["GET", "POST", "GET"], [call[0] for call in session.calls])
        self.assertEqual("https://auth.api.ubeya.com/user/refresh", session.calls[1][1])
        self.assertNotIn("json", session.calls[1][2])
        self.assertEqual("Ubeya", session.calls[0][2]["headers"]["X-App-Name"])

    async def test_failed_refresh_raises_auth_error(self):
        session = Session([Response(401), Response(401)])
        client = api.UbeyaClient(session)
        with self.assertRaises(api.UbeyaAuthenticationError):
            await client.request("/payroll")

    async def test_does_not_request_sms_without_valid_captcha_input(self):
        session = Session([])
        client = api.UbeyaClient(session)
        with self.assertRaises(ValueError):
            await client.request_sms("0000000000", "")
        self.assertEqual([], session.calls)

    async def test_login_bad_code_does_not_expose_response_details(self):
        session = Session([Response(400)])
        client = api.UbeyaClient(session)
        with self.assertRaises(api.UbeyaAuthenticationError) as context:
            await client.verify_sms("447000000000", "00000")
        self.assertNotIn("00000", str(context.exception))

    async def test_bad_refresh_request_reauthenticates(self):
        session = Session([Response(401), Response(403)])
        client = api.UbeyaClient(session)
        with self.assertRaises(api.UbeyaAuthenticationError):
            await client.request("/payroll")


if __name__ == "__main__":
    unittest.main()
