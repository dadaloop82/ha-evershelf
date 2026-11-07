"""Config flow for EverShelf integration."""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_auth import evershelf_headers, evershelf_params
from .const import (
    CONF_CALENDAR_ATTENTION,
    CONF_EXPIRY_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_CALENDAR_ATTENTION,
    DEFAULT_EXPIRY_DAYS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_EXPIRY_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_EXPIRY_DAYS,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
_RE_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


async def _async_test_url(
    hass, url: str, token: str = ""
) -> tuple[bool, str, dict[str, Any]]:
    """Test EverShelf URL. Returns (ok, error_key, info_dict)."""
    session = async_get_clientsession(hass)
    headers = evershelf_headers(token)

    # Try ha_info first (richer response)
    for action in ("ha_info", "ha_sensor"):
        try:
            async with session.get(
                f"{url}/api/index.php",
                params=evershelf_params(token, {"action": action}),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    info = await resp.json(content_type=None)
                    if action == "ha_info":
                        return True, "", info
                    # ha_sensor fallback - build minimal info dict
                    attrs = info.get("attributes", {})
                    return True, "", {
                        "instance": "EverShelf",
                        "version": "?",
                        "items_count": attrs.get("total_items", "?"),
                    }
                if resp.status in (401, 403):
                    return False, "invalid_auth" if token else "token_required", {}
        except aiohttp.ClientError:
            pass

    return False, "cannot_connect", {}


class EverShelfConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle EverShelf config flow: Zeroconf discovery + manual entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_url: str = ""
        self._existing_entry_id: str = ""
        self._info: dict[str, Any] = {}

    # ── Zeroconf auto-discovery ────────────────────────────────────────

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a Zeroconf-discovered EverShelf instance."""
        host = discovery_info.host
        port = discovery_info.port or 80
        scheme = "https" if port == 443 else "http"
        url = f"{scheme}://{host}" + (f":{port}" if port not in (80, 443) else "")

        ok, _, info = await _async_test_url(self.hass, url)
        if not ok:
            return self.async_abort(reason="cannot_connect")

        unique_id = info.get("unique_id") or f"evershelf_{host}"
        known = await self._async_handle_known_instance(unique_id, url, info)
        if known is not None:
            return known

        self._discovered_url = url
        self._info = info
        self.context["title_placeholders"] = {
            "name": info.get("instance", DEFAULT_NAME),
            "host": host,
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Zeroconf-discovered EverShelf device."""
        if user_input is not None:
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._info.get("instance", DEFAULT_NAME),
                "url": self._discovered_url,
                "version": str(self._info.get("version", "?")),
                "items": str(self._info.get("items_count", "?")),
            },
        )

    # ── Already configured instance found at a different address ──────

    async def _async_handle_known_instance(
        self, unique_id: str, url: str, info: dict[str, Any]
    ) -> FlowResult | None:
        """Return a result when ``unique_id`` belongs to an existing entry, else None.

        The unique_id is published unauthenticated by EverShelf, so a discovered host
        can claim it. A different address therefore never replaces the stored URL on
        its own: the user has to confirm, because the API token follows the URL.
        """
        existing = await self.async_set_unique_id(unique_id)
        if existing is None:
            return None
        if existing.data.get(CONF_URL) == url:
            return self.async_abort(reason="already_configured")
        self._existing_entry_id = existing.entry_id
        self._discovered_url = url
        self._info = info
        self.context["title_placeholders"] = {
            "name": info.get("instance", DEFAULT_NAME),
            "host": url,
        }
        return await self.async_step_confirm_url_update()

    async def async_step_confirm_url_update(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask before pointing an existing entry at a different address."""
        entry = self.hass.config_entries.async_get_entry(self._existing_entry_id)
        if entry is None:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_URL: self._discovered_url}
            )
            return self.async_abort(reason="url_updated")

        return self.async_show_form(
            step_id="confirm_url_update",
            description_placeholders={
                "name": self._info.get("instance", DEFAULT_NAME),
                "old_url": str(entry.data.get(CONF_URL, "?")),
                "new_url": self._discovered_url,
            },
        )

    # ── Discovery helper ──────────────────────────────────────────────

    async def _async_probe_or_menu(self, menu_step_id: str) -> FlowResult:
        """Probe http://evershelf.local; confirm if found, show menu if not."""
        probe_url = "http://evershelf.local"
        ok, _, info = await _async_test_url(self.hass, probe_url)
        if ok:
            self._discovered_url = probe_url
            self._info = info
            unique_id = info.get("unique_id") or "evershelf_evershelf.local"
            known = await self._async_handle_known_instance(unique_id, probe_url, info)
            if known is not None:
                return known
            self.context["title_placeholders"] = {
                "name": info.get("instance", DEFAULT_NAME),
                "host": "evershelf.local",
            }
            return await self.async_step_zeroconf_confirm()

        return self.async_show_menu(
            step_id=menu_step_id,
            menu_options=["retry_discovery", "manual"],
            description_placeholders={"tried": probe_url},
        )

    # ── User entry: auto-probe first ──────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Entry: probe evershelf.local automatically, show menu if not found."""
        return await self._async_probe_or_menu("user")

    async def async_step_retry_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Retry auto-discovery."""
        return await self._async_probe_or_menu("retry_discovery")

    # ── Manual URL entry ──────────────────────────────────────────────

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual URL entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_url = user_input[CONF_URL].strip().rstrip("/")
            # Auto-prepend http:// if missing
            if not raw_url.startswith(("http://", "https://")):
                raw_url = f"http://{raw_url}"

            if not _RE_URL.match(raw_url):
                errors[CONF_URL] = "invalid_url"
            else:
                ok, err_key, info = await _async_test_url(self.hass, raw_url)
                if not ok:
                    errors["base"] = err_key
                else:
                    self._discovered_url = raw_url
                    self._info = info
                    unique_id = info.get("unique_id") or raw_url.lower()
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return await self.async_step_auth()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL, default="http://evershelf.local"): str}
            ),
            errors=errors,
        )

    # ── Optional token ────────────────────────────────────────────────

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Optional token step — enables write operations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = (user_input.get(CONF_TOKEN) or "").strip()
            if self._info.get("api_token_required") and not token:
                errors[CONF_TOKEN] = "token_required"
            elif token:
                ok, err_key, _ = await _async_test_url(
                    self.hass, self._discovered_url, token
                )
                if not ok:
                    errors[CONF_TOKEN] = err_key

            if not errors:
                name = self._info.get("instance") or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_URL: self._discovered_url,
                        CONF_TOKEN: token,
                    },
                    options={
                        CONF_EXPIRY_DAYS: DEFAULT_EXPIRY_DAYS,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {vol.Optional(CONF_TOKEN, default=""): str}
            ),
            description_placeholders={
                "url": self._discovered_url,
                "name": self._info.get("instance", DEFAULT_NAME),
                "token_hint": (
                    "API_TOKEN is required on this server."
                    if self._info.get("api_token_required")
                    else "Optional — only if API_TOKEN is set in .env."
                ),
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return EverShelfOptionsFlow(config_entry)


class EverShelfOptionsFlow(config_entries.OptionsFlow):
    """Options flow for EverShelf — expiry threshold + scan interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXPIRY_DAYS,
                        default=opts.get(CONF_EXPIRY_DAYS, DEFAULT_EXPIRY_DAYS),
                    ): vol.All(int, vol.Range(min=MIN_EXPIRY_DAYS, max=MAX_EXPIRY_DAYS)),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    vol.Required(
                        CONF_CALENDAR_ATTENTION,
                        default=opts.get(
                            CONF_CALENDAR_ATTENTION, DEFAULT_CALENDAR_ATTENTION
                        ),
                    ): bool,
                }
            ),
        )
