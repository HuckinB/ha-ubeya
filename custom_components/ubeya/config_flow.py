"""Ubeya Crew setup: demo, or experimental human-assisted OTP login."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, SOURCE_REAUTH

from .api import UbeyaAuthenticationError, UbeyaClient, UbeyaConnectionError, UbeyaError
from .auth import export_cookies, has_session_cookies, new_session
from .const import CONF_COOKIES, CONF_MODE, CONF_PHONE, DOMAIN, MODE_DEMO, MODE_LIVE


def normalize_phone(value: str) -> str:
    """Ubeya expects international numbers such as 447xxxxxxxxx, no plus."""
    phone = value.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if not phone.isascii() or not phone.isdecimal() or not 8 <= len(phone) <= 15:
        raise ValueError("Use an international phone number with country code")
    return phone


class UbeyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Only the official Ubeya website initiates the reCAPTCHA-protected SMS."""

    VERSION = 1

    def __init__(self) -> None:
        self._phone: str | None = None

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["live", "demo"])

    async def async_step_demo(self, user_input: dict | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id("ubeya_demo")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Ubeya (Demo)", data={CONF_MODE: MODE_DEMO})
        return self.async_show_form(step_id="demo", data_schema=vol.Schema({}))

    async def async_step_live(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._phone = normalize_phone(user_input[CONF_PHONE])
            except (KeyError, ValueError, AttributeError):
                errors["base"] = "invalid_phone"
            else:
                return await self.async_step_otp()
        return self.async_show_form(
            step_id="live",
            data_schema=vol.Schema({vol.Required(CONF_PHONE): str}),
            errors=errors,
        )

    async def async_step_otp(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and self._phone:
            code = str(user_input.get("code", "")).strip()
            if not 4 <= len(code) <= 12 or not code.isascii() or not code.isdecimal():
                errors["base"] = "invalid_code"
            else:
                try:
                    async with new_session() as session:
                        client = UbeyaClient(session)
                        await client.verify_sms(self._phone, code)
                        cookies = export_cookies(session)
                        if not has_session_cookies(cookies):
                            raise UbeyaError("Ubeya did not issue session cookies")
                        # Verify cookies work on the separate Crew API host.
                        await client.request("/auth/me")
                        cookies = export_cookies(session)
                        if not has_session_cookies(cookies):
                            raise UbeyaError("Ubeya session cookies unavailable")
                except UbeyaAuthenticationError:
                    errors["base"] = "invalid_code"
                except UbeyaConnectionError:
                    errors["base"] = "cannot_connect"
                except UbeyaError:
                    errors["base"] = "invalid_response"
                else:
                    unique_id = f"ubeya_crew_{sha256(self._phone.encode()).hexdigest()}"
                    await self.async_set_unique_id(unique_id)
                    if self.source == SOURCE_REAUTH:
                        self._abort_if_unique_id_mismatch(reason="wrong_account")
                        return self.async_update_reload_and_abort(
                            self._get_reauth_entry(),
                            data_updates={
                                CONF_MODE: MODE_LIVE,
                                CONF_PHONE: self._phone,
                                CONF_COOKIES: cookies,
                            },
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Ubeya Crew",
                        data={
                            CONF_MODE: MODE_LIVE,
                            CONF_PHONE: self._phone,
                            CONF_COOKIES: cookies,
                        },
                    )
        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"crew_url": "https://crew.ubeya.com/"},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Re-run human-initiated login after revoked refresh credentials."""
        self._phone = entry_data.get(CONF_PHONE)
        if not self._phone:
            return await self.async_step_live()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_otp()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
        )

