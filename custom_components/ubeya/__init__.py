"""Experimental read-only Ubeya Crew integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .auth import new_session
from .calendar_feed import UbeyaCalendarFeedView
from .const import CONF_COOKIES, CONF_MODE, MODE_LIVE
from .coordinator import UbeyaCoordinator


PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the read-only feed once, before account entries load."""
    hass.http.register_view(UbeyaCalendarFeedView)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Ubeya account from the UI configuration flow."""
    session = new_session(entry.data[CONF_COOKIES]) if entry.data.get(CONF_MODE) == MODE_LIVE else None
    coordinator = UbeyaCoordinator(hass, entry, session)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await coordinator.async_close()
        raise
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await coordinator.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ubeya entities."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded

