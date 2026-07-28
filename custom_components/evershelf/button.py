"""Button platform for EverShelf."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EverShelfCoordinator
from .sensor import evershelf_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EverShelfButtonDescription(ButtonEntityDescription):
    action: str = "refresh"


BUTTON_DESCRIPTIONS: tuple[EverShelfButtonDescription, ...] = (
    EverShelfButtonDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
        action="refresh",
    ),
    EverShelfButtonDescription(
        key="refresh_prices",
        translation_key="refresh_prices",
        icon="mdi:currency-eur",
        action="ha_refresh_prices",
    ),
    EverShelfButtonDescription(
        key="suggest_recipe",
        translation_key="suggest_recipe",
        icon="mdi:chef-hat",
        action="ha_suggest_recipe",
    ),
    EverShelfButtonDescription(
        key="sync_smart_shopping",
        translation_key="sync_smart_shopping",
        icon="mdi:cart-arrow-down",
        action="ha_sync_smart_shopping",
    ),
    EverShelfButtonDescription(
        key="clear_expired",
        translation_key="clear_expired",
        icon="mdi:delete-sweep",
        action="ha_clear_expired",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EverShelfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EverShelfButton(coordinator, entry, desc) for desc in BUTTON_DESCRIPTIONS
    )


class EverShelfButton(CoordinatorEntity[EverShelfCoordinator], ButtonEntity):
    """An EverShelf action button."""

    entity_description: EverShelfButtonDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = evershelf_device_info(coordinator, entry)

    async def async_press(self) -> None:
        action = self.entity_description.action
        if action == "refresh":
            await self.coordinator.async_request_refresh()
        elif action == "ha_refresh_prices":
            result = await self.coordinator.async_refresh_prices()
            if result:
                _LOGGER.info("EverShelf prices refreshed: %s", result.get("total_label"))
            await self.coordinator.async_request_refresh()
        elif action == "ha_suggest_recipe":
            # Prefer structured generation (title + main ingredients + notification + event)
            result = await self.coordinator.async_generate_recipe(
                meal="auto",
                scadenze=True,
                use_prefs=True,
            )
            if not result.get("success"):
                # Fallback to legacy free-text suggestion
                recipe = await self.coordinator.async_suggest_recipe()
                if recipe:
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "EverShelf Recipe Suggestion",
                            "message": recipe,
                            "notification_id": "evershelf_recipe",
                        },
                    )
            await self.coordinator.async_request_refresh()
        elif action == "ha_sync_smart_shopping":
            await self.coordinator.async_sync_smart_shopping()
            await self.coordinator.async_request_refresh()
        elif action == "ha_clear_expired":
            result = await self.coordinator.async_clear_expired()
            if result:
                _LOGGER.info("EverShelf cleared %s expired rows", result.get("deleted"))
            await self.coordinator.async_request_refresh()
