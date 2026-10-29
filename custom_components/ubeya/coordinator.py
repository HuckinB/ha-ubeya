"""Single update coordinator for Ubeya entities."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import UbeyaAuthenticationError, UbeyaClient, UbeyaConnectionError, UbeyaError
from .auth import export_cookies
from .const import CONF_COOKIES, CONF_MODE, DOMAIN, MODE_DEMO, MODE_LIVE, UPDATE_INTERVAL_MINUTES
from .demo import build_demo_responses
from .models import UbeyaSnapshot, normalize


_LOGGER = logging.getLogger(__name__)


class UbeyaCoordinator(DataUpdateCoordinator[UbeyaSnapshot]):
    """Poll a snapshot once and share it with every entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
            always_update=False,
        )
        self.entry = entry
        self._session = session
        self._client = UbeyaClient(session) if session is not None else None

    async def async_close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def _async_update_data(self) -> UbeyaSnapshot:
        now = dt_util.now()
        try:
            if self.entry.data.get(CONF_MODE) == MODE_DEMO:
                responses = build_demo_responses(now)
            elif self.entry.data.get(CONF_MODE) == MODE_LIVE and self._client:
                responses = await self._client.get_snapshot_responses()
                # The refresh endpoint can rotate one or both HttpOnly cookies.
                # Keep the latest credentials across Home Assistant restarts.
                cookies = export_cookies(self._session)
                if cookies != self.entry.data.get(CONF_COOKIES):
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={**self.entry.data, CONF_COOKIES: cookies},
                    )
            else:
                raise UpdateFailed("Unknown Ubeya connection mode")

            return normalize(*responses, fetched_at=now)
        except UbeyaAuthenticationError as error:
            raise ConfigEntryAuthFailed("Ubeya sign-in required") from error
        except (UbeyaConnectionError, UbeyaError) as error:
            raise UpdateFailed("Ubeya API temporarily unavailable") from error
        except (KeyError, TypeError, ValueError) as error:
            raise UpdateFailed("Could not normalize Ubeya response") from error

