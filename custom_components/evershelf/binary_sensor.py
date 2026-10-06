"""Binary sensor platform for EverShelf."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EverShelfCoordinator
from .sensor import evershelf_device_info


@dataclass(frozen=True, kw_only=True)
class EverShelfBinarySensorDescription(BinarySensorEntityDescription):
    data_key: str = ""


BINARY_SENSOR_DESCRIPTIONS: tuple[EverShelfBinarySensorDescription, ...] = (
    EverShelfBinarySensorDescription(
        key="has_expired_items",
        translation_key="has_expired_items",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:food-off",
        data_key="expired_items",
    ),
    EverShelfBinarySensorDescription(
        key="has_expiring_items",
        translation_key="has_expiring_items",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:food-apple-outline",
        data_key="expiring_soon",
    ),
    EverShelfBinarySensorDescription(
        key="has_expiring_today",
        translation_key="has_expiring_today",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:food-alert",
        data_key="expiring_today",
    ),
    EverShelfBinarySensorDescription(
        key="has_shopping_items",
        translation_key="has_shopping_items",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:cart",
        data_key="shopping_items",
    ),
    EverShelfBinarySensorDescription(
        key="price_tracking_enabled",
        translation_key="price_tracking_enabled",
        icon="mdi:tag-text-outline",
        data_key="price_tracking_enabled",
    ),
    EverShelfBinarySensorDescription(
        key="backup_overdue",
        translation_key="backup_overdue",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:backup-restore",
        data_key="last_backup_at",
    ),
    EverShelfBinarySensorDescription(
        key="bring_connected",
        translation_key="bring_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:cart-check",
        data_key="bring_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EverShelfCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EverShelfBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class EverShelfBinarySensor(CoordinatorEntity[EverShelfCoordinator], BinarySensorEntity):
    """An EverShelf binary sensor (problem indicator)."""

    entity_description: EverShelfBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = evershelf_device_info(coordinator, entry)

    @property
    def is_on(self) -> bool:
        raw = self.coordinator.data.get(self.entity_description.data_key)
        # backup_overdue: ON if last_backup_at is older than 7 days or missing
        if self.entity_description.key == "backup_overdue":
            if not raw:
                return True
            try:
                ts = dt_util.parse_datetime(raw)
                if ts is None:
                    return True
                return (dt_util.utcnow() - ts) > timedelta(days=7)
            except Exception:
                return True
        return bool(raw)
