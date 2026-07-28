"""DataUpdateCoordinator for EverShelf."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_auth import evershelf_headers, evershelf_params
from .const import DEFAULT_EXPIRY_DAYS, DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_RECIPE_GENERATED

_LOGGER = logging.getLogger(__name__)


class EverShelfCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch pantry data from an EverShelf instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        url: str,
        token: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        expiry_days: int = DEFAULT_EXPIRY_DAYS,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry_id = entry_id
        self.url = url.rstrip("/")
        self.token = token
        self.expiry_days = expiry_days
        self.last_recipe: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        return evershelf_headers(self.token, json_body=json_body)

    def _params(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return evershelf_params(self.token, params)

    def _session(self) -> aiohttp.ClientSession:
        return async_get_clientsession(self.hass, verify_ssl=False)

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sensor overview and shopping list from EverShelf."""
        try:
            session = self._session()

            # Fetch sensor/inventory data
            async with session.get(
                f"{self.url}/api/index.php",
                params=self._params(
                    {"action": "ha_sensor", "expiry_days": self.expiry_days}
                ),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    raise UpdateFailed("EverShelf API token invalid or missing")
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status} from EverShelf")
                raw: dict[str, Any] = await resp.json(content_type=None)
                attrs: dict[str, Any] = raw.get("attributes", {})
                result: dict[str, Any] = {
                    "state": raw.get("state", 0),
                    "shopping_list": [],
                    **attrs,
                }
                # Safety-net: ensure total_items is always set even if the PHP
                # response structure changes. Uses state value as fallback when
                # the sensor=total variant is called directly.
                result.setdefault("total_items", result["state"])

            # Keep last generated recipe attrs across polls
            if self.last_recipe:
                result["last_recipe_title"] = self.last_recipe.get("title")
                result["last_recipe_summary"] = self.last_recipe.get("summary")
                result["last_recipe_main_ingredients"] = self.last_recipe.get(
                    "main_ingredients", []
                )
                result["last_recipe_meal"] = self.last_recipe.get("meal")
                result["last_recipe_persons"] = self.last_recipe.get("persons")

            # Fetch shopping list (non-fatal if it fails)
            try:
                async with session.get(
                    f"{self.url}/api/index.php",
                    params=self._params({"action": "ha_shopping_items"}),
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp2:
                    if resp2.status == 200:
                        shopping_data = await resp2.json(content_type=None)
                        result["shopping_list"] = shopping_data.get("items", [])
            except aiohttp.ClientError:
                pass  # shopping list failure is non-fatal

            return result

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Cannot reach EverShelf: {err}") from err

    # ------------------------------------------------------------------
    # Connection test (called from config_flow)
    # ------------------------------------------------------------------

    async def async_test_connection(self) -> tuple[bool, str]:
        """Test connection. Returns (True, info_text) or (False, error_key)."""
        # Try ha_info first (richer response with instance name)
        try:
            async with self._session().get(
                f"{self.url}/api/index.php",
                params=self._params({"action": "ha_info"}),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    info = await resp.json(content_type=None)
                    if info.get("api_token_required") and not self.token:
                        return False, "token_required"
                    return True, info.get("name", info.get("instance", "EverShelf"))
                if resp.status in (401, 403):
                    return False, "invalid_auth"
        except aiohttp.ClientError:
            pass

        # Fallback to ha_sensor (older EverShelf versions)
        try:
            async with self._session().get(
                f"{self.url}/api/index.php",
                params=self._params({"action": "ha_sensor"}),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return True, "EverShelf"
                if resp.status in (401, 403):
                    return False, "invalid_auth"
        except aiohttp.ClientError:
            pass

        return False, "cannot_connect"

    async def async_get_info(self) -> dict[str, Any]:
        """Fetch ha_info from EverShelf (for zeroconf confirmation)."""
        try:
            async with self._session().get(
                f"{self.url}/api/index.php",
                params=self._params({"action": "ha_info"}),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
        except aiohttp.ClientError:
            pass
        return {}

    # ------------------------------------------------------------------
    # HA Services
    # ------------------------------------------------------------------

    async def async_add_to_shopping(
        self,
        name: str,
        quantity: float | None,
        unit: str | None,
    ) -> bool:
        """Add a product to the EverShelf shopping list."""
        item: dict[str, Any] = {"name": name}
        if quantity is not None:
            item["quantity"] = quantity
        if unit:
            item["unit"] = unit
        return await self._post("shopping_add", {"items": [item]})

    async def async_remove_from_shopping(self, name: str) -> bool:
        """Remove a product from the EverShelf shopping list by name or uid."""
        return await self._post("shopping_remove", {"name": name})

    async def async_mark_used(
        self,
        name: str,
        quantity: float,
        unit: str | None,
    ) -> bool:
        """Reduce the stock of an inventory item by *quantity*."""
        session = self._session()
        try:
            async with session.get(
                f"{self.url}/api/index.php",
                params=self._params({"action": "inventory_list"}),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("EverShelf inventory_list returned HTTP %s", resp.status)
                    return False
                data: dict[str, Any] = await resp.json(content_type=None)

            items: list[dict[str, Any]] = data.get("inventory") or data.get("items") or []
            name_l = name.lower()
            # Prefer unit match when provided
            match = None
            if unit:
                unit_l = unit.lower()
                match = next(
                    (
                        i
                        for i in items
                        if i.get("name", "").lower() == name_l
                        and str(i.get("unit", "")).lower() == unit_l
                    ),
                    None,
                )
            if match is None:
                match = next(
                    (i for i in items if i.get("name", "").lower() == name_l),
                    None,
                )
            if not match:
                _LOGGER.warning("EverShelf: item '%s' not found in inventory", name)
                return False

            item_id = match["id"]
            current_qty = float(match.get("quantity", 0))
            new_qty = max(0.0, current_qty - quantity)

            async with session.post(
                f"{self.url}/api/index.php",
                params=self._params({"action": "update_inventory"}),
                headers=self._headers(json_body=True),
                json={"id": item_id, "quantity": new_qty},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp2:
                return resp2.status == 200

        except aiohttp.ClientError as err:
            _LOGGER.error("EverShelf mark_used error: %s", err)
            return False

    # ------------------------------------------------------------------
    # Internal POST helper
    # ------------------------------------------------------------------

    async def _post(
        self, action: str, payload: dict[str, Any], timeout: int = 15
    ) -> bool:
        data = await self._post_json(action, payload, timeout=timeout)
        return data is not None

    async def _post_json(
        self,
        action: str,
        payload: dict[str, Any],
        timeout: int = 15,
    ) -> dict[str, Any] | None:
        """POST JSON and return parsed body (or None on transport/HTTP error)."""
        try:
            async with self._session().post(
                f"{self.url}/api/index.php",
                params=self._params({"action": action}),
                headers=self._headers(json_body=True),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                # Still try to parse error body for callers
                try:
                    body = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001
                    body = None
                _LOGGER.warning(
                    "EverShelf %s returned HTTP %s: %s",
                    action,
                    resp.status,
                    body,
                )
                if isinstance(body, dict):
                    body.setdefault("success", False)
                    body.setdefault("http_status", resp.status)
                    return body
                return None
        except aiohttp.ClientError as err:
            _LOGGER.error("EverShelf %s error: %s", action, err)
            return None

    async def _get_json(self, action: str, params: dict | None = None, timeout: int = 15) -> dict[str, Any] | None:
        """GET request returning parsed JSON or None on error."""
        try:
            p = self._params({"action": action, **(params or {})})
            async with self._session().get(
                f"{self.url}/api/index.php",
                params=p,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                _LOGGER.warning("EverShelf %s returned HTTP %s", action, resp.status)
        except aiohttp.ClientError as err:
            _LOGGER.error("EverShelf %s error: %s", action, err)
        return None

    # ------------------------------------------------------------------
    # Action methods (called by button/service entities)
    # ------------------------------------------------------------------

    async def async_refresh_prices(self) -> dict[str, Any] | None:
        """Compute shopping total from existing price cache (no AI calls)."""
        return await self._get_json("ha_refresh_prices")

    async def async_suggest_recipe(self, location: str = "") -> str | None:
        """Ask EverShelf AI for a free-text recipe using items expiring soonest."""
        params = {}
        if location:
            params["location"] = location
        data = await self._get_json("ha_suggest_recipe", params, timeout=35)
        if data:
            return data.get("recipe")
        return None

    async def async_generate_recipe(
        self,
        *,
        meal: str | None = None,
        persons: int | None = None,
        options: list[str] | None = None,
        meal_plan_type: str | None = None,
        fuel: bool | None = None,
        veloce: bool | None = None,
        scadenze: bool | None = None,
        pocafame: bool | None = None,
        salutare: bool | None = None,
        opened: bool | None = None,
        zerowaste: bool | None = None,
        use_prefs: bool = True,
        lang: str | None = None,
        save: bool = True,
        notify: bool = True,
        fire_event: bool = True,
    ) -> dict[str, Any]:
        """Generate a structured recipe (same options as the EverShelf UI).

        Returns a dict with at least success/title/main_ingredients/summary.
        Fires EVENT_RECIPE_GENERATED and updates last_recipe sensor data.
        By default the recipe is also saved in EverShelf's Ricette archive.
        """
        payload: dict[str, Any] = {"use_prefs": use_prefs, "save": save}
        if meal:
            payload["meal"] = meal
        if persons is not None:
            payload["persons"] = persons
        if options:
            payload["options"] = options
        if meal_plan_type:
            payload["meal_plan_type"] = meal_plan_type
        if lang:
            payload["lang"] = lang
        for key, val in (
            ("fuel", fuel),
            ("veloce", veloce),
            ("scadenze", scadenze),
            ("pocafame", pocafame),
            ("salutare", salutare),
            ("opened", opened),
            ("zerowaste", zerowaste),
        ):
            if val is not None:
                payload[key] = val

        data = await self._post_json("ha_generate_recipe", payload, timeout=90)
        if not data:
            return {"success": False, "error": "unreachable"}

        if data.get("success"):
            self.last_recipe = data
            # Push into coordinator data for sensors without waiting for poll
            merged = dict(self.data or {})
            merged["last_recipe_title"] = data.get("title")
            merged["last_recipe_summary"] = data.get("summary")
            merged["last_recipe_main_ingredients"] = data.get("main_ingredients", [])
            merged["last_recipe_meal"] = data.get("meal")
            merged["last_recipe_persons"] = data.get("persons")
            self.async_set_updated_data(merged)

            if fire_event:
                self.hass.bus.async_fire(
                    EVENT_RECIPE_GENERATED,
                    {
                        "title": data.get("title"),
                        "main_ingredients": data.get("main_ingredients", []),
                        "summary": data.get("summary"),
                        "meal": data.get("meal"),
                        "persons": data.get("persons"),
                        "prep_time": data.get("prep_time"),
                        "cook_time": data.get("cook_time"),
                        "options": data.get("options", []),
                        "entry_id": self.entry_id,
                    },
                )

            if notify:
                ings = data.get("main_ingredients") or []
                ings_txt = ", ".join(ings) if ings else "—"
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": f"EverShelf: {data.get('title', 'Ricetta')}",
                        "message": (
                            f"**{data.get('title', '')}**\n\n"
                            f"Ingredienti: {ings_txt}\n"
                            f"Pasto: {data.get('meal', '')} · "
                            f"{data.get('persons', '')} pers.\n"
                            f"{data.get('prep_time') or ''} / {data.get('cook_time') or ''}"
                        ),
                        "notification_id": "evershelf_recipe",
                    },
                )

        return data

    async def async_sync_smart_shopping(self) -> bool:
        """Trigger smart shopping AI sync."""
        return await self._post("smart_shopping", {})

    async def async_clear_expired(self) -> dict[str, Any] | None:
        """Remove expired zero-stock inventory rows."""
        return await self._get_json("ha_clear_expired")

    async def async_get_calendar_events(self) -> list[dict[str, Any]]:
        """Fetch all expiry events from EverShelf for the calendar entity."""
        data = await self._get_json("ha_calendar")
        if data:
            return data.get("events", [])
        return []
