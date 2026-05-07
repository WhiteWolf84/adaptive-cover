"""Sensor platform for Adaptive Cover integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SENSOR_TYPE, DOMAIN
from .coordinator import COVER_TYPE_LABELS, AdaptiveDataUpdateCoordinator

if TYPE_CHECKING:
    from . import AdaptiveCoverConfigEntry

_LOGGER = logging.getLogger(__name__)

# Silver: parallel-updates — 0 = illimitato per integrazioni push/coordinator-driven
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdaptiveCoverConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Adaptive Cover config entry."""
    name: str = config_entry.data["name"]
    coordinator = config_entry.runtime_data

    _LOGGER.info("Setting up Adaptive Cover sensors for %s", name)

    async_add_entities(
        [
            AdaptiveCoverSensorEntity(config_entry.entry_id, config_entry, name, coordinator),
            AdaptiveCoverTimeSensorEntity(
                config_entry.entry_id,
                config_entry,
                name,
                "Start Sun",
                "start",
                "mdi:sun-clock-outline",
                coordinator,
            ),
            AdaptiveCoverTimeSensorEntity(
                config_entry.entry_id,
                config_entry,
                name,
                "End Sun",
                "end",
                "mdi:sun-clock",
                coordinator,
            ),
            AdaptiveCoverControlSensorEntity(
                config_entry.entry_id, config_entry, name, coordinator
            ),
        ]
    )


class _BaseAdaptiveCoverSensor(
    CoordinatorEntity[AdaptiveDataUpdateCoordinator], SensorEntity
):
    """Common base for adaptive cover sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        config_entry: AdaptiveCoverConfigEntry,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator=coordinator)
        self._device_id = unique_id
        device_name = COVER_TYPE_LABELS[config_entry.data[CONF_SENSOR_TYPE]]
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._device_id)},
            name=device_name,
        )

    @property
    def available(self) -> bool:
        """Return False if coordinator update has failed or no data yet."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class AdaptiveCoverSensorEntity(_BaseAdaptiveCoverSensor):
    """Adaptive Cover position sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:sun-compass"

    def __init__(
        self,
        unique_id: str,
        config_entry: AdaptiveCoverConfigEntry,
        name: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(unique_id, config_entry, coordinator)
        self._sensor_name = "Cover Position"
        self._attr_unique_id = f"{unique_id}_{self._sensor_name}"
        self._friendly_name = name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "AdaptiveCoverSensorEntity %s updated. State: %s",
            self.name,
            self.coordinator.data.states.get("state"),
        )
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._sensor_name} {self._friendly_name}"

    @property
    def native_value(self) -> int | None:
        """Return current adaptive cover position."""
        return self.coordinator.data.states.get("state")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return diagnostic attributes."""
        return self.coordinator.data.attributes


class AdaptiveCoverTimeSensorEntity(_BaseAdaptiveCoverSensor):
    """Adaptive Cover time sensor (start / end of sun)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        unique_id: str,
        config_entry: AdaptiveCoverConfigEntry,
        name: str,
        sensor_name: str,
        key: str,
        icon: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the time sensor."""
        super().__init__(unique_id, config_entry, coordinator)
        self._attr_icon = icon
        self._key = key
        self._sensor_name = sensor_name
        self._friendly_name = name
        self._attr_unique_id = f"{unique_id}_{sensor_name}"

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._sensor_name} {self._friendly_name}"

    @property
    def native_value(self):
        """Return start/end timestamp."""
        return self.coordinator.data.states.get(self._key)


class AdaptiveCoverControlSensorEntity(_BaseAdaptiveCoverSensor):
    """Adaptive Cover control method sensor."""

    _attr_translation_key = "control"

    def __init__(
        self,
        unique_id: str,
        config_entry: AdaptiveCoverConfigEntry,
        name: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the control method sensor."""
        super().__init__(unique_id, config_entry, coordinator)
        self._sensor_name = "Control Method"
        self._friendly_name = name
        self._attr_unique_id = f"{unique_id}_{self._sensor_name}"

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._sensor_name} {self._friendly_name}"

    @property
    def native_value(self) -> str | None:
        """Return current control method."""
        return self.coordinator.data.states.get("control")
