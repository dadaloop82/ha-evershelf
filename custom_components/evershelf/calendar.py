"""Calendar platform for EverShelf — shows product expiry dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EverShelfCoordinator
from .sensor import evershelf_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EverShelfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EverShelfCalendar(coordinator, entry)])


class EverShelfCalendar(CalendarEntity):
    """EverShelf product expiry calendar."""

    _attr_has_entity_name = True
    _attr_translation_key = "expiry_calendar"

    def __init__(self, coordinator: EverShelfCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_expiry_calendar"
        self._attr_device_info = evershelf_device_info(coordinator, entry)
        self._cached_events: list[CalendarEvent] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming expiry event."""
        today = dt_util.now().date()
        upcoming = [e for e in self._cached_events if e.start >= today]
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Fetch expiry events from EverShelf within the date range."""
        raw_events = await self._coordinator.async_get_calendar_events()
        events: list[CalendarEvent] = []
        start_d = start_date.date()
        end_d = end_date.date()

        for ev in raw_events:
            try:
                expiry = date.fromisoformat(ev["start"])
            except (KeyError, ValueError):
                continue
            if start_d <= expiry <= end_d:
                desc = ev.get("description", "") or ""
                # EverShelf ≥ 1.11.5 tags low-risk best-before leftovers.
                if ev.get("needs_attention") is False:
                    desc = f"{desc} · OK (best before)".strip(" ·")
                events.append(
                    CalendarEvent(
                        start=expiry,
                        end=expiry + timedelta(days=1),
                        summary=ev["summary"],
                        description=desc,
                        location=ev.get("location", ""),
                    )
                )
        self._cached_events = events
        return events
