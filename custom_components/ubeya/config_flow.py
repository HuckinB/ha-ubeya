"""Ubeya Crew setup: demo, or experimental human-assisted OTP login."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import secrets
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, SOURCE_REAUTH
from homeassistant.core import callback

from .api import UbeyaAuthenticationError, UbeyaClient, UbeyaConnectionError, UbeyaError
from .auth import export_cookies, has_session_cookies, new_session
from .calendar_feed import subscription_url
from .const import (
    CONF_COOKIES,
    CONF_FEED_ENABLED,
    CONF_FEED_INCLUDE_EARNINGS,
    CONF_FEED_INCLUDE_NOTES,
    CONF_FEED_TOKEN,
    CONF_FEED_URL,
    CONF_MODE,
    CONF_PHONE,
    DOMAIN,
    MODE_DEMO,
    MODE_LIVE,
)


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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> UbeyaOptionsFlow:
        """Expose the private Apple Calendar subscription settings."""
        return UbeyaOptionsFlow()

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


class UbeyaOptionsFlow(config_entries.OptionsFlow):
    """Manage an optional read-only calendar feed and its access token."""

    def __init__(self) -> None:
        self._pending_options: dict[str, Any] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the current link, enable/disable it or rotate its secret."""
        options = self.config_entry.options
        current_url = ""
        if options.get(CONF_FEED_ENABLED) and options.get(CONF_FEED_TOKEN):
            current_url = subscription_url(
                options.get(CONF_FEED_URL, ""),
                self.config_entry.entry_id,
                options[CONF_FEED_TOKEN],
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            enabled = bool(user_input.get(CONF_FEED_ENABLED, False))
            base_url = str(user_input.get(CONF_FEED_URL, "")).strip().rstrip("/")
            if enabled:
                try:
                    parsed = urlsplit(base_url)
                    valid = (
                        parsed.scheme == "https"
                        and bool(parsed.hostname)
                        and parsed.username is None
                        and parsed.password is None
                        and parsed.path in ("", "/")
                        and not parsed.query
                        and not parsed.fragment
                    )
                except ValueError:
                    valid = False
                if not valid:
                    errors["base"] = "invalid_feed_url"

            if not errors:
                token = (
                    options.get(CONF_FEED_TOKEN, "")
                    if enabled and not user_input.get("rotate_feed_token")
                    else ""
                )
                if enabled and not token:
                    token = secrets.token_urlsafe(32)
                self._pending_options = {
                    CONF_FEED_ENABLED: enabled,
                    CONF_FEED_URL: base_url,
                    CONF_FEED_TOKEN: token if enabled else "",
                    CONF_FEED_INCLUDE_NOTES: bool(
                        user_input.get(CONF_FEED_INCLUDE_NOTES, False)
                    ),
                    CONF_FEED_INCLUDE_EARNINGS: bool(
                        user_input.get(CONF_FEED_INCLUDE_EARNINGS, False)
                    ),
                }
                if not enabled:
                    # Disabling revokes the existing URL immediately.
                    return self.async_create_entry(data=self._pending_options)
                return await self.async_step_confirm()

        default_url = options.get(CONF_FEED_URL) or self.hass.config.external_url or ""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_FEED_ENABLED,
                    default=options.get(CONF_FEED_ENABLED, False),
                ): bool,
                vol.Optional(CONF_FEED_URL, default=default_url): str,
                vol.Required(
                    CONF_FEED_INCLUDE_NOTES,
                    default=options.get(CONF_FEED_INCLUDE_NOTES, False),
                ): bool,
                vol.Required(
                    CONF_FEED_INCLUDE_EARNINGS,
                    default=options.get(CONF_FEED_INCLUDE_EARNINGS, False),
                ): bool,
                vol.Required("rotate_feed_token", default=False): bool,
            }),
            errors=errors,
            description_placeholders={
                "feed_url": current_url or "Not enabled",
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the link before saving it; the user must confirm."""
        options = self._pending_options
        if options is None or not options.get(CONF_FEED_ENABLED):
            return await self.async_step_init()
        if user_input is not None:
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "feed_url": subscription_url(
                    options[CONF_FEED_URL],
                    self.config_entry.entry_id,
                    options[CONF_FEED_TOKEN],
                ),
            },
        )

