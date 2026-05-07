"""The Adaptive Cover integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_END_ENTITY,
    CONF_ENTITIES,
    CONF_PRESENCE_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN as DOMAIN,
)
from .coordinator import AdaptiveDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Typed ConfigEntry — HA core 2024.x best practice. Permette type-checking
# di entry.runtime_data senza cast.
type AdaptiveCoverConfigEntry = ConfigEntry[AdaptiveDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AdaptiveCoverConfigEntry
) -> bool:
    """Set up Adaptive Cover from a config entry."""
    coordinator = AdaptiveDataUpdateCoordinator(hass, entry)

    tracked_entities: list[str] = ["sun.sun"]
    for option in (
        CONF_TEMP_ENTITY,
        CONF_PRESENCE_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_END_ENTITY,
    ):
        entity = entry.options.get(option)
        if entity is not None:
            tracked_entities.append(entity)

    cover_entities: list[str] = entry.options.get(CONF_ENTITIES, [])

    _LOGGER.info("Setting up entry %s", entry.data.get("name"))

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            tracked_entities,
            coordinator.async_check_entity_state_change,
        )
    )

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            cover_entities,
            coordinator.async_check_cover_state_change,
        )
    )

    await coordinator.async_config_entry_first_refresh()

    # Bronze: runtime-data — usa entry.runtime_data invece di hass.data[DOMAIN]
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AdaptiveCoverConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: AdaptiveCoverConfigEntry
) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug(
        "Migrating Adaptive Cover config entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )
    # Future schema migrations: branch on entry.version / entry.minor_version
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: AdaptiveCoverConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
