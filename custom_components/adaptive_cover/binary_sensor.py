"""Binary Sensor platform for the Adaptive Cover integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SENSOR_TYPE, DOMAIN
from .coordinator import COVER_TYPE_LABELS, AdaptiveDataUpdateCoordinator

if TYPE_CHECKING:
    from . import AdaptiveCoverConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdaptiveCoverConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adaptive Cover binary sensor platform."""
    coordinator = config_entry.runtime_data

    _LOGGER.info(
        "Setting up Adaptive Cover binary sensors for %s",
        config_entry.data.get("name"),
    )

    async_add_entities(
        [
            AdaptiveCoverBinarySensor(
                config_entry,
                config_entry.entry_id,
                "Sun Infront",
                "sun_motion",
                BinarySensorDeviceClass.MOTION,
                coordinator,
            ),
            AdaptiveCoverBinarySensor(
                config_entry,
                config_entry.entry_id,
                "Manual Override",
                "manual_override",
                BinarySensorDeviceClass.RUNNING,
                coordinator,
            ),
        ]
    )


class AdaptiveCoverBinarySensor(
    CoordinatorEntity[AdaptiveDataUpdateCoordinator], BinarySensorEntity
):
    """Adaptive Cover binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: AdaptiveCoverConfigEntry,
        unique_id: str,
        binary_name: str,
        key: str,
        device_class: BinarySensorDeviceClass,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator=coordinator)
        self._key = key
        self._attr_translation_key = key
        self._friendly_name: str = config_entry.data["name"]
        self._binary_name = binary_name
        self._attr_unique_id = f"{unique_id}_{binary_name}"
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=COVER_TYPE_LABELS[config_entry.data[CONF_SENSOR_TYPE]],
        )

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._binary_name} {self._friendly_name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.states.get(self._key)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return list of manually-controlled covers for the override sensor."""
        if self._key == "manual_override":
            return {"manual_controlled": self.coordinator.data.states.get("manual_list")}
        return None
