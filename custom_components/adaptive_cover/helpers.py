"""Helper functions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from dateutil import parser
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.util import dt as dt_util


def state_attr(hass: HomeAssistant, entity_id: str, attr: str) -> Any | None:
    """Return attribute of an entity's state, or None if unavailable.

    Replaces homeassistant.helpers.template.state_attr, removed in HA 2026.5.
    """
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.attributes.get(attr)


def get_safe_state(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return entity state, or None when unknown/unavailable."""
    state = hass.states.get(entity_id)
    if not state or state.state in ("unknown", "unavailable"):
        return None
    return state.state


def get_domain(entity: str | None) -> str | None:
    """Return domain part of an entity_id, or None if entity is None."""
    if entity is None:
        return None
    domain, _ = split_entity_id(entity)
    return domain


def is_presence_detected(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return True when someone is home according to `entity_id`.

    No sensor, an unavailable sensor or an unreadable zone count all count as
    present: an absent reading must never trigger away-only behaviour.
    """
    if entity_id is None:
        return True
    state = get_safe_state(hass, entity_id)
    if state is None:
        return True
    domain = get_domain(entity_id)
    if domain == "device_tracker":
        return state == "home"
    if domain == "zone":
        try:
            return int(state) > 0
        except ValueError:
            return True
    if domain in ("binary_sensor", "input_boolean"):
        return state == "on"
    return True


def get_datetime_from_str(string: str | None) -> dt.datetime | None:
    """Convert a time/datetime string to a Home Assistant local, aware datetime.

    Home Assistant never calls ``time.tzset()``: ``set_default_time_zone()`` only
    updates its own ``DEFAULT_TIME_ZONE``. So the host clock (``datetime.now()``,
    ``date.today()``) and the configured HA timezone can differ — the common case
    is a container running UTC while HA is set to a local zone.

    Both the missing date components and the resulting tzinfo therefore come from
    ``dt_util.now()`` rather than from the host: parsing ``"20:00:00"`` yields
    20:00 *today in HA's timezone*, tz-aware, so it compares safely against other
    ``dt_util`` values and is scheduled at the instant the user meant.
    """
    if string is None:
        return None
    local_now = dt_util.now()
    midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    parsed = parser.parse(string, ignoretz=True, default=midnight.replace(tzinfo=None))
    return parsed.replace(tzinfo=local_now.tzinfo)
