"""Isolated cross-subdomain Ubeya cookie storage, without JWT logging."""

from __future__ import annotations

from http.cookies import SimpleCookie

import aiohttp
from yarl import URL

from .const import ACCESS_COOKIE, AUTH_API, CREW_API, REFRESH_COOKIE

COOKIE_NAMES = (ACCESS_COOKIE, REFRESH_COOKIE)


def new_session(cookies: dict[str, str] | None = None) -> aiohttp.ClientSession:
    """Give each account its own jar; don't share HA's general HTTP session."""
    jar = aiohttp.CookieJar()
    if cookies:
        jar.update_cookies(_domain_cookies(cookies), response_url=URL(AUTH_API))
    return aiohttp.ClientSession(cookie_jar=jar)


def _domain_cookies(values: dict[str, str]) -> SimpleCookie:
    cookie = SimpleCookie()
    for name in COOKIE_NAMES:
        if value := values.get(name):
            cookie[name] = value
            cookie[name]["domain"] = ".ubeya.com"
            cookie[name]["path"] = "/"
            cookie[name]["secure"] = True
            cookie[name]["httponly"] = True
    return cookie


def export_cookies(session: aiohttp.ClientSession) -> dict[str, str]:
    """Export only session tokens, not unrelated cookies or response JWTs."""
    available = session.cookie_jar.filter_cookies(URL(CREW_API))
    return {name: available[name].value for name in COOKIE_NAMES if name in available}


def has_session_cookies(cookies: dict[str, str]) -> bool:
    return all(cookies.get(name) for name in COOKIE_NAMES)
