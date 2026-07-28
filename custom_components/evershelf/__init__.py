"""EverShelf Home Assistant integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_EXPIRY_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_EXPIRY_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import EverShelfCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.TODO,
    Platform.CALENDAR,
    Platform.TEXT,
]

_ADD_TO_SHOPPING_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("quantity"): vol.Coerce(float),
        vol.Optional("unit"): cv.string,
    }
)

_MARK_USED_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("quantity"): vol.All(vol.Coerce(float), vol.Range(min=0.001)),
        vol.Optional("unit"): cv.string,
    }
)

_SUGGEST_RECIPE_SCHEMA = vol.Schema(
    {
        vol.Optional("location"): cv.string,
    }
)

_GENERATE_RECIPE_SCHEMA = vol.Schema(
    {
        vol.Optional("meal"): vol.In(
            ["auto", "colazione", "pranzo", "merenda", "cena", "dolce", "succo"]
        ),
        vol.Optional("persons"): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Optional("options"): vol.All(
            cv.ensure_list,
            [vol.In(["veloce", "pocafame", "scadenze", "salutare", "opened", "zerowaste", "fuel"])],
        ),
        vol.Optional("meal_plan_type"): cv.string,
        vol.Optional("fuel"): cv.boolean,
        vol.Optional("veloce"): cv.boolean,
        vol.Optional("scadenze"): cv.boolean,
        vol.Optional("pocafame"): cv.boolean,
        vol.Optional("salutare"): cv.boolean,
        vol.Optional("opened"): cv.boolean,
        vol.Optional("zerowaste"): cv.boolean,
        vol.Optional("use_prefs", default=True): cv.boolean,
        vol.Optional("lang"): cv.string,
        vol.Optional("notify", default=True): cv.boolean,
        vol.Optional("fire_event", default=True): cv.boolean,
    }
)

_SERVICES = (
    "add_to_shopping",
    "mark_used",
    "refresh",
    "suggest_recipe",
    "generate_recipe",
    "refresh_prices",
    "clear_expired",
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EverShelf from a config entry."""
    coordinator = EverShelfCoordinator(
        hass,
        entry_id=entry.entry_id,
        url=entry.data[CONF_URL],
        token=entry.data.get(CONF_TOKEN, ""),
        scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        expiry_days=entry.options.get(CONF_EXPIRY_DAYS, DEFAULT_EXPIRY_DAYS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Register services once per HA instance
    if not hass.services.has_service(DOMAIN, "add_to_shopping"):

        async def _handle_add_to_shopping(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            await coord.async_add_to_shopping(
                name=call.data["name"],
                quantity=call.data.get("quantity"),
                unit=call.data.get("unit"),
            )
            await coord.async_request_refresh()

        async def _handle_mark_used(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            ok = await coord.async_mark_used(
                name=call.data["name"],
                quantity=float(call.data["quantity"]),
                unit=call.data.get("unit"),
            )
            if not ok:
                raise ServiceValidationError(
                    f"EverShelf: could not find or update item '{call.data['name']}'"
                )
            await coord.async_request_refresh()

        async def _handle_refresh(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            await coord.async_request_refresh()

        async def _handle_suggest_recipe(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            location = call.data.get("location", "")
            recipe = await coord.async_suggest_recipe(location=location)
            if recipe:
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "EverShelf Recipe Suggestion",
                        "message": recipe,
                        "notification_id": "evershelf_recipe",
                    },
                )
            else:
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "EverShelf Recipe",
                        "message": "No recipe generated (check Gemini key / pantry).",
                        "notification_id": "evershelf_recipe",
                    },
                )
            await coord.async_request_refresh()

        async def _handle_generate_recipe(call: ServiceCall) -> dict[str, Any]:
            coord = _get_coordinator(hass, call)
            result = await coord.async_generate_recipe(
                meal=call.data.get("meal"),
                persons=call.data.get("persons"),
                options=call.data.get("options"),
                meal_plan_type=call.data.get("meal_plan_type"),
                fuel=call.data.get("fuel"),
                veloce=call.data.get("veloce"),
                scadenze=call.data.get("scadenze"),
                pocafame=call.data.get("pocafame"),
                salutare=call.data.get("salutare"),
                opened=call.data.get("opened"),
                zerowaste=call.data.get("zerowaste"),
                use_prefs=call.data.get("use_prefs", True),
                lang=call.data.get("lang"),
                notify=call.data.get("notify", True),
                fire_event=call.data.get("fire_event", True),
            )
            if not result.get("success"):
                err = result.get("error") or "generation_failed"
                raise ServiceValidationError(f"EverShelf: recipe failed — {err}")
            # Response for automations: response_variable
            return {
                "title": result.get("title"),
                "main_ingredients": result.get("main_ingredients", []),
                "summary": result.get("summary"),
                "meal": result.get("meal"),
                "persons": result.get("persons"),
                "prep_time": result.get("prep_time"),
                "cook_time": result.get("cook_time"),
                "tags": result.get("tags", []),
                "ingredients": result.get("ingredients", []),
                "steps_count": result.get("steps_count"),
                "nutrition": result.get("nutrition"),
                "fuel_why": result.get("fuel_why"),
            }

        async def _handle_refresh_prices(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            await coord.async_refresh_prices()
            await coord.async_request_refresh()

        async def _handle_clear_expired(call: ServiceCall) -> None:
            coord = _get_coordinator(hass, call)
            await coord.async_clear_expired()
            await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN, "add_to_shopping", _handle_add_to_shopping, schema=_ADD_TO_SHOPPING_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, "mark_used", _handle_mark_used, schema=_MARK_USED_SCHEMA
        )
        hass.services.async_register(DOMAIN, "refresh", _handle_refresh)
        hass.services.async_register(
            DOMAIN, "suggest_recipe", _handle_suggest_recipe, schema=_SUGGEST_RECIPE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            "generate_recipe",
            _handle_generate_recipe,
            schema=_GENERATE_RECIPE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(DOMAIN, "refresh_prices", _handle_refresh_prices)
        hass.services.async_register(DOMAIN, "clear_expired", _handle_clear_expired)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an EverShelf config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data.get(DOMAIN):
        for svc in _SERVICES:
            hass.services.async_remove(DOMAIN, svc)

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinator(hass: HomeAssistant, call: ServiceCall) -> EverShelfCoordinator:
    """Return the coordinator for a service call."""
    entries: dict[str, EverShelfCoordinator] = hass.data.get(DOMAIN, {})
    entry_id: str | None = call.data.get("config_entry_id")
    if entry_id:
        coord = entries.get(entry_id)
        if coord is None:
            raise ServiceValidationError(f"EverShelf: unknown config entry '{entry_id}'")
        return coord
    if not entries:
        raise ServiceValidationError("EverShelf: no instances configured")
    return next(iter(entries.values()))
