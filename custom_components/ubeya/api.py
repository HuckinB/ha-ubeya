"""Asynchronous Ubeya Crew client: read-only data and session renewal.

SMS issuance requires Ubeya's own reCAPTCHA, so the experimental HA login
flow never issues an OTP or attempts to bypass that human challenge.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

import aiohttp

from .const import AUTH_API, CREW_API


class UbeyaError(Exception):
    """Ubeya API error without secret-bearing request details."""


class UbeyaAuthenticationError(UbeyaError):
    """Credentials must be renewed by the user."""


class UbeyaConnectionError(UbeyaError):
    """Temporary transport or upstream problem."""


class _Unauthorized(UbeyaError):
    """Internal control flow for a 401 response."""


class UbeyaClient:
    """An isolated session is required so cookies cannot leak to other APIs."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._refresh_lock = asyncio.Lock()
        self._refresh_generation = 0

    async def _raw_request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "X-App-Name": "Ubeya"}
        if extra_headers:
            headers.update(extra_headers)
        request_options: dict[str, Any] = {
            "headers": headers,
            "timeout": aiohttp.ClientTimeout(total=30),
        }
        if params is not None:
            request_options["params"] = params
        if json_body is not None:
            request_options["json"] = json_body
        try:
            async with self._session.request(method, url, **request_options) as response:
                if response.status == 401:
                    raise _Unauthorized("Authentication expired")
                if response.status == 429 or response.status >= 500:
                    raise UbeyaConnectionError(f"Ubeya temporarily unavailable ({response.status})")
                if response.status >= 400:
                    raise UbeyaError(f"Ubeya returned HTTP {response.status}")
                if response.status == 204:
                    return {}
                payload = await response.json(
                    content_type=None,
                    loads=lambda body: json.loads(body, parse_float=Decimal),
                )
                if not isinstance(payload, dict):
                    raise UbeyaError("Unexpected Ubeya response structure")
                return payload
        except (aiohttp.ClientError, TimeoutError) as error:
            raise UbeyaConnectionError("Could not contact Ubeya") from error

    async def _refresh(self) -> None:
        try:
            # No JSON body: the official Crew web client relies on cookies.
            await self._raw_request("POST", f"{AUTH_API}/user/refresh")
        except UbeyaConnectionError:
            raise
        except (_Unauthorized, UbeyaError) as error:
            raise UbeyaAuthenticationError("Ubeya session expired") from error

    async def request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retry once after one coordinated cookie refresh on HTTP 401."""
        generation = self._refresh_generation
        try:
            return await self._raw_request("GET", f"{CREW_API}{path}", params=params)
        except _Unauthorized:
            async with self._refresh_lock:
                if generation == self._refresh_generation:
                    await self._refresh()
                    self._refresh_generation += 1
            try:
                return await self._raw_request("GET", f"{CREW_API}{path}", params=params)
            except _Unauthorized as error:
                raise UbeyaAuthenticationError("Ubeya login required") from error

    async def request_sms(self, phone: str, recaptcha_token: str, *, is_voice: bool = False) -> None:
        """Accept a legitimately obtained Ubeya CAPTCHA token, never create one."""
        if not recaptcha_token:
            raise ValueError("An official Ubeya reCAPTCHA token is required")
        await self._raw_request(
            "POST",
            f"{AUTH_API}/user/signup",
            json_body={"phone": phone, "isVoice": is_voice},
            extra_headers={"x-recaptcha-token": recaptcha_token},
        )

    async def verify_sms(self, phone: str, code: str) -> None:
        """Session cookies, not the returned JWTs, are held by the cookie jar."""
        try:
            await self._raw_request(
                "POST", f"{AUTH_API}/user/login", json_body={"phone": phone, "code": code}
            )
        except UbeyaConnectionError:
            raise
        except (_Unauthorized, UbeyaError) as error:
            raise UbeyaAuthenticationError("Ubeya rejected the verification code") from error

    async def get_snapshot_responses(self) -> tuple[dict[str, Any], ...]:
        """Read only employee-visible API endpoints."""
        return await asyncio.gather(
            self.request("/bookings"),
            self.request("/positions"),
            self.request("/locations"),
            self.request("/timesheets/history"),
            self.request("/payroll"),
        )

