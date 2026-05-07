"""Switch platform for the Adaptive Cover integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CLIMATE_MODE,
    CONF_ENTITIES,
    CONF_IRRADIANCE_ENTITY,
    CONF_LUX_ENTITY,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_SENSOR_TYPE,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)
from .coordinator import COVER_TYPE_LABELS, AdaptiveDataUpdateCoordinator

if TYPE_CHECKING:
    from . import AdaptiveCoverConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdaptiveCoverConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Adaptive Cover switch platform."""
    coordinator = config_entry.runtime_data

    _LOGGER.info(
        "Setting up Adaptive Cover switches for %s",
        config_entry.data.get("name"),
    )

    options = config_entry.options
    switches: list[AdaptiveCoverSwitch] = []

    if options.get(CONF_ENTITIES):
        switches.extend(
            [
                AdaptiveCoverSwitch(
                    config_entry, config_entry.entry_id, "Toggle Control", True,
                    "control_toggle", coordinator,
                ),
                AdaptiveCoverSwitch(
                    config_entry, config_entry.entry_id, "Manual Override", True,
                    "manual_toggle", coordinator,
                ),
            ]
        )

    if options.get(CONF_CLIMATE_MODE):
        switches.append(
            AdaptiveCoverSwitch(
                config_entry, config_entry.entry_id, "Climate Mode", True,
                "switch_mode", coordinator,
            )
        )
        if options.get(CONF_WEATHER_ENTITY) or options.get(CONF_OUTSIDETEMP_ENTITY):
            switches.append(
                AdaptiveCoverSwitch(
                    config_entry, config_entry.entry_id, "Outside Temperature", False,
                    "temp_toggle", coordinator,
                )
            )
        if options.get(CONF_LUX_ENTITY):
            switches.append(
                AdaptiveCoverSwitch(
                    config_entry, config_entry.entry_id, "Lux", True,
                    "lux_toggle", coordinator,
                )
            )
        if options.get(CONF_IRRADIANCE_ENTITY):
            switches.append(
                AdaptiveCoverSwitch(
                    config_entry, config_entry.entry_id, "Irradiance", True,
                    "irradiance_toggle", coordinator,
                )
            )

    async_add_entities(switches)


class AdaptiveCoverSwitch(
    CoordinatorEntity[AdaptiveDataUpdateCoordinator], SwitchEntity, RestoreEntity
):
    """Adaptive Cover switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: AdaptiveCoverConfigEntry,
        unique_id: str,
        switch_name: str,
        initial_state: bool,
        key: str,
        coordinator: AdaptiveDataUpdateCoordinator,
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator=coordinator)
        self._friendly_name: str = config_entry.data["name"]
        self._key = key
        self._attr_translation_key = key
        self._switch_name = switch_name
        self._attr_device_class = device_class
        self._initial_state = initial_state
        self._attr_unique_id = f"{unique_id}_{switch_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=COVER_TYPE_LABELS[config_entry.data[CONF_SENSOR_TYPE]],
        )

        self.coordinator.logger.debug("Setup switch")

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._switch_name} {self._friendly_name}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        _LOGGER.debug("Turning on switch: %s", self.name)
        self._attr_is_on = True
        setattr(self.coordinator, self._key, True)
        if self._key == "control_toggle" and kwargs.get("added") is not True:
            for entity in self.coordinator.entities:
                if (
                    not self.coordinator.manager.is_cover_manual(entity)
                    and self.coordinator.check_adaptive_time
                ):
                    await self.coordinator.async_set_position(
                        entity, self.coordinator.state
                    )
        await self.coordinator.async_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        _LOGGER.debug("Turning off switch: %s", self.name)
        self._attr_is_on = False
        setattr(self.coordinator, self._key, False)
        if self._key == "control_toggle" and kwargs.get("added") is not True:
            for entity in self.coordinator.manager.manual_controlled:
                self.coordinator.manager.reset(entity)
        await self.coordinator.async_refresh()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state and apply initial value when added to HA."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        self.coordinator.logger.debug(
            "%s: last state is %s", self._friendly_name, last_state
        )
        if (last_state is None and self._initial_state) or (
            last_state is not None and last_state.state == STATE_ON
        ):
            await self.async_turn_on(added=True)
        else:
            await self.async_turn_off(added=True)
