"""Adaptive Cover integration diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import AdaptiveCoverConfigEntry

# Redact entity ids that may reveal user-defined naming/topology.
TO_REDACT: set[str] = {
    "name",
    "title",
    "group",
    "temp_entity",
    "presence_entity",
    "weather_entity",
    "outside_temp",
    "lux_entity",
    "irradiance_entity",
    "start_entity",
    "end_entity",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AdaptiveCoverConfigEntry
) -> dict[str, Any]:
    """Return config entry diagnostics."""
    coordinator = config_entry.runtime_data

    coordinator_data: dict[str, Any] = {}
    if coordinator and coordinator.data is not None:
        coordinator_data = {
            "climate_mode_toggle": coordinator.data.climate_mode_toggle,
            "states": dict(coordinator.data.states),
            "attributes": dict(coordinator.data.attributes),
        }

    return {
        "title": "Adaptive Cover Configuration",
        "type": "config_entry",
        "identifier": config_entry.entry_id,
        "config_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "config_options": async_redact_data(dict(config_entry.options), TO_REDACT),
        "coordinator_data": async_redact_data(coordinator_data, TO_REDACT),
    }
