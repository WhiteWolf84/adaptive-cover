"""Helper functions."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd
from dateutil import parser
from homeassistant.core import HomeAssistant, split_entity_id


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


def get_timedelta_str(string: str | None) -> pd.Timedelta | None:
    """Convert ISO duration string to a pandas Timedelta."""
    if string is None:
        return None
    return pd.to_timedelta(string)


def get_datetime_from_str(string: str | None) -> dt.datetime | None:
    """Convert datetime string to naive datetime, or None when input is None."""
    if string is None:
        return None
    return parser.parse(string, ignoretz=True)


def get_last_updated(entity_id: str | None, hass: HomeAssistant) -> dt.datetime | None:
    """Return last_updated for an entity, or None if not present."""
    if entity_id is None:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return state.last_updated


def check_time_passed(time: dt.datetime) -> bool:
    """Check if `time.time()` has passed in local time today."""
    return dt.datetime.now().time() >= time.time()


def dt_check_time_passed(time: dt.datetime) -> bool:
    """Check if a UTC datetime is in the past relative to now (UTC)."""
    now = dt.datetime.now(dt.UTC)
    if now.date() == time.date():
        return now.time() > time.time()
    return True
