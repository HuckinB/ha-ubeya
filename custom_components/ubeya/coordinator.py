"""Single update coordinator for Ubeya entities."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import UbeyaAuthenticationError, UbeyaClient, UbeyaConnectionError, UbeyaError
from .auth import export_cookies
from .const import (
    AUDIT_PAGE_SIZE,
    CONF_COOKIES,
    CONF_MODE,
    DOMAIN,
    EVENT_SHIFT_CHANGED,
    MODE_DEMO,
    MODE_LIVE,
    UPDATE_INTERVAL_MINUTES,
)
from .demo import build_demo_responses
from .models import AuditEvent, UbeyaSnapshot, normalize, normalize_audit_log


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
        self._approval_store = Store(hass, 1, f"ubeya_approvals_{entry.entry_id}")
        self._seen_approvals: set[int] | None = None
        self.last_approval: dict | None = None
        self._audit_store = Store(hass, 1, f"ubeya_audit_{entry.entry_id}")
        self._seen_audit: set[int] | None = None
        self.last_shift_change: dict | None = None
        self.recent_shift_changes: list[dict] = []

    async def async_load_approvals(self) -> None:
        """Load durable detection state before the first API refresh."""
        saved = await self._approval_store.async_load()
        if saved is not None:
            self._seen_approvals = set(saved.get("seen", []))
            self.last_approval = saved.get("last")
        audit = await self._audit_store.async_load()
        if audit is not None:
            self._seen_audit = set(audit.get("seen", []))
            self.last_shift_change = audit.get("last")
            self.recent_shift_changes = list(audit.get("recent", []))

    async def _track_approvals(self, snapshot: UbeyaSnapshot) -> None:
        current = {p.timesheet_id for p in snapshot.payroll}
        if self._seen_approvals is None:
            # First installation establishes a baseline; don't alert on old income.
            self._seen_approvals = current
        else:
            new = [p for p in snapshot.payroll if p.timesheet_id not in self._seen_approvals]
            if new:
                record = max(new, key=lambda p: (p.date, p.timesheet_id))
                shift = snapshot.shift_for_payroll(record)
                self.last_approval = {
                    "detected_at": snapshot.fetched_at.isoformat(),
                    "timesheet_id": record.timesheet_id,
                    "shift": shift.title if shift else None,
                    "shift_date": shift.start.date().isoformat() if shift else None,
                    "approved_hours": float(record.paid_hours),
                    "income": float(record.value),
                    "currency": record.currency,
                }
            self._seen_approvals.update(current)
        await self._approval_store.async_save({
            "seen": sorted(self._seen_approvals), "last": self.last_approval,
        })

    def _shift_change_payload(self, event: AuditEvent, previous: UbeyaSnapshot | None, snapshot: UbeyaSnapshot) -> dict:
        before = next((s for s in previous.shifts if s.id == event.shift_id), None) if previous else None
        after = next((s for s in snapshot.shifts if s.id == event.shift_id), None)
        moved = before is not None and event.start is not None and (before.start != event.start or before.end != event.end)
        return {
            "audit_id": event.id,
            "type": event.type,
            "shift_id": event.shift_id,
            "shift": event.shift_name or (after.title if after else None),
            "position": event.position or (after.position if after else None),
            "location": after.location_name if after else None,
            "start": event.start.isoformat() if event.start else None,
            "end": event.end.isoformat() if event.end else None,
            # Only known if this HA instance saw the shift before the change.
            "previous_start": before.start.isoformat() if moved else None,
            "previous_end": before.end.isoformat() if moved else None,
            "changed_by": event.admin_name,
            "changed_at": event.created_at.isoformat(),
        }

    async def _track_shift_changes(
        self, events: tuple[AuditEvent, ...], previous: UbeyaSnapshot | None, snapshot: UbeyaSnapshot
    ) -> None:
        ids = {e.id for e in events}
        if self._seen_audit is None:
            # First run establishes a baseline; don't announce historic changes.
            self._seen_audit = ids
        else:
            for event in events:  # oldest first, so automations fire in order
                if event.id in self._seen_audit or not event.is_shift_change:
                    continue
                payload = self._shift_change_payload(event, previous, snapshot)
                self.hass.bus.async_fire(EVENT_SHIFT_CHANGED, payload)
                self.last_shift_change = payload
                self.recent_shift_changes = [payload, *self.recent_shift_changes][:10]
            self._seen_audit |= ids
        # The feed only returns recent entries, so old ids can be forgotten safely.
        self._seen_audit = set(sorted(self._seen_audit)[-1000:])
        await self._audit_store.async_save({
            "seen": sorted(self._seen_audit),
            "last": self.last_shift_change,
            "recent": self.recent_shift_changes,
        })

    async def async_close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def _async_update_data(self) -> UbeyaSnapshot:
        now = dt_util.now()
        audit_payload = None
        try:
            if self.entry.data.get(CONF_MODE) == MODE_DEMO:
                responses = build_demo_responses(now)
            elif self.entry.data.get(CONF_MODE) == MODE_LIVE and self._client:
                responses = await self._client.get_snapshot_responses()
                try:
                    audit_payload = await self._client.get_audit_log(AUDIT_PAGE_SIZE)
                except UbeyaAuthenticationError:
                    raise
                except UbeyaError as error:
                    # Shift data is still valid; try the activity feed again next refresh.
                    _LOGGER.debug("Ubeya audit log unavailable: %s", error)
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

            snapshot = normalize(*responses, fetched_at=now)
            await self._track_approvals(snapshot)
            if audit_payload is not None:
                events = normalize_audit_log(audit_payload, dt_util.get_default_time_zone())
                await self._track_shift_changes(events, self.data, snapshot)
            return snapshot
        except UbeyaAuthenticationError as error:
            raise ConfigEntryAuthFailed("Ubeya sign-in required") from error
        except (UbeyaConnectionError, UbeyaError) as error:
            raise UpdateFailed("Ubeya API temporarily unavailable") from error
        except (KeyError, TypeError, ValueError) as error:
            raise UpdateFailed("Could not normalize Ubeya response") from error

