"""Button platform for the Adaptive Cover integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITIES, CONF_SENSOR_TYPE, DOMAIN
from .coordinator import COVER_TYPE_LABELS, AdaptiveDataUpdateCoordinator

if TYPE_CHECKING:
    from . import AdaptiveCoverConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AdaptiveCoverConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator = config_entry.runtime_data

    _LOGGER.info(
        "Setting up Adaptive Cover buttons for %s",
        config_entry.data.get("name"),
    )

    if not config_entry.options.get(CONF_ENTITIES):
        return

    async_add_entities(
        [
            AdaptiveCoverButton(
                config_entry,
                config_entry.entry_id,
                "Reset Manual Override",
                coordinator,
            )
        ]
    )


class AdaptiveCoverButton(
    CoordinatorEntity[AdaptiveDataUpdateCoordinator], ButtonEntity
):
    """Adaptive Cover button entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cog-refresh-outline"

    def __init__(
        self,
        config_entry: AdaptiveCoverConfigEntry,
        unique_id: str,
        button_name: str,
        coordinator: AdaptiveDataUpdateCoordinator,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator=coordinator)
        self._friendly_name: str = config_entry.data["name"]
        self._attr_unique_id = f"{unique_id}_{button_name}"
        self._button_name = button_name
        self._entities: list[str] = config_entry.options.get(CONF_ENTITIES, [])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=COVER_TYPE_LABELS[config_entry.data[CONF_SENSOR_TYPE]],
        )

    @property
    def name(self) -> str:
        """Name of the entity."""
        return f"{self._button_name} {self._friendly_name}"

    async def async_press(self) -> None:
        """Reset manual overrides for all configured covers."""
        _LOGGER.info("Button %s pressed. Resetting manual overrides.", self.name)
        for entity in self._entities:
            if self.coordinator.manager.is_cover_manual(entity):
                _LOGGER.debug("Resetting manual override for: %s", entity)
                await self.coordinator.async_set_position(
                    entity, self.coordinator.state
                )
                while self.coordinator.wait_for_target.get(entity):
                    await asyncio.sleep(1)
                self.coordinator.manager.reset(entity)
            else:
                _LOGGER.debug(
                    "Reset skipped for %s: already auto-controlled",
                    entity,
                )
        await self.coordinator.async_refresh()
