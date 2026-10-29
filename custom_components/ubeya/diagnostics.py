"""Privacy-safe Home Assistant diagnostics for Ubeya Crew."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MODE
from .diagnostic_data import diagnostics_summary


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Never include cookies, phone, names, venues, dates, notes or pay."""
    coordinator = getattr(entry, "runtime_data", None)
    snapshot = getattr(coordinator, "data", None)
    return diagnostics_summary(snapshot, str(entry.data.get(CONF_MODE, "unknown")))
