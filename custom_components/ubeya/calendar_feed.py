"""Capability-protected iCalendar subscription for external calendar apps."""

from __future__ import annotations

import hmac

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import (
    CONF_FEED_ENABLED,
    CONF_FEED_INCLUDE_EARNINGS,
    CONF_FEED_INCLUDE_NOTES,
    CONF_FEED_TOKEN,
    DOMAIN,
)
from .coordinator import UbeyaCoordinator
from .ics import render_ics


FEED_ROUTE = "/api/ubeya/calendar/{entry_id}/{token}.ics"


def subscription_url(base_url: str, entry_id: str, token: str) -> str:
    """Build the link without depending on the incoming request's Host header."""
    return f"{base_url.rstrip('/')}/api/ubeya/calendar/{entry_id}/{token}.ics"


class UbeyaCalendarFeedView(HomeAssistantView):
    """Read-only feed authenticated by an independently revocable random token."""

    url = FEED_ROUTE
    name = "api:ubeya:calendar_feed"
    requires_auth = False  # Apple Calendar cannot send a Home Assistant bearer token.

    async def get(
        self, request: web.Request, entry_id: str, token: str
    ) -> web.Response:
        """Serve shifts only when the exact configured token matches."""
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != DOMAIN
            or not entry.options.get(CONF_FEED_ENABLED, False)
        ):
            raise web.HTTPNotFound()

        saved_token = entry.options.get(CONF_FEED_TOKEN, "")
        if (
            not isinstance(saved_token, str)
            or len(token) > 200
            or not saved_token
            or not hmac.compare_digest(token, saved_token)
        ):
            raise web.HTTPNotFound()

        coordinator = getattr(entry, "runtime_data", None)
        if not isinstance(coordinator, UbeyaCoordinator) or coordinator.data is None:
            raise web.HTTPServiceUnavailable()

        snapshot = coordinator.data
        body = render_ics(
            snapshot.shifts,
            account_uid=entry_id,
            fetched_at=snapshot.fetched_at,
            include_notes=entry.options.get(CONF_FEED_INCLUDE_NOTES, False),
            include_earnings=entry.options.get(CONF_FEED_INCLUDE_EARNINGS, False),
            currency=snapshot.currency,
        )
        return web.Response(
            text=body,
            content_type="text/calendar",
            charset="utf-8",
            headers={
                "Cache-Control": "private, no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
