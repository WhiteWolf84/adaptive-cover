"""Tests for the datetime helper.

Regression: Home Assistant never calls ``time.tzset()`` — ``set_default_time_zone``
only updates HA's own ``DEFAULT_TIME_ZONE``. So ``datetime.now()`` (host clock) and
``dt_util.now()`` (HA clock) diverge whenever the container timezone differs from the
configured one, which is the default for Docker installs. ``get_datetime_from_str``
used ``parser.parse(..., ignoretz=True)``, taking *both* the implicit date and the
naive-ness from the host.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.adaptive_cover.helpers import (
    get_datetime_from_str,
    is_presence_detected,
)

ROME = ZoneInfo("Europe/Rome")


def _at(moment: dt.datetime):
    """Patch dt_util.now() as seen by the helper module."""
    return patch(
        "custom_components.adaptive_cover.helpers.dt_util.now", return_value=moment
    )


def test_returns_none_for_none():
    assert get_datetime_from_str(None) is None


def test_result_is_timezone_aware():
    with _at(dt.datetime(2026, 8, 2, 12, 0, tzinfo=ROME)):
        parsed = get_datetime_from_str("20:00:00")
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == dt.timedelta(hours=2)


def test_missing_date_comes_from_ha_timezone_not_host():
    """23:30 UTC is already the 3rd in Rome: the time must land on the 3rd."""
    ha_now = dt.datetime(2026, 8, 2, 23, 30, tzinfo=dt.UTC).astimezone(ROME)
    assert ha_now.date() == dt.date(2026, 8, 3)

    with _at(ha_now):
        parsed = get_datetime_from_str("20:00:00")

    assert parsed.date() == dt.date(2026, 8, 3)
    assert (parsed.hour, parsed.minute) == (20, 0)


def test_comparable_against_dt_util_now():
    """Aware-vs-naive comparison used to raise TypeError; it must not."""
    ha_now = dt.datetime(2026, 8, 2, 12, 0, tzinfo=ROME)
    with _at(ha_now):
        end = get_datetime_from_str("20:00:00")
    assert ha_now < end


def test_explicit_date_is_preserved():
    with _at(dt.datetime(2026, 8, 2, 12, 0, tzinfo=ROME)):
        parsed = get_datetime_from_str("2026-12-25 07:30:00")
    assert parsed.date() == dt.date(2026, 12, 25)
    assert (parsed.hour, parsed.minute) == (7, 30)


# ---------------------------------------------------------- is_presence_detected
def _hass_with_state(state: str | None) -> MagicMock:
    hass = MagicMock()
    hass.states.get.return_value = None if state is None else MagicMock(state=state)
    return hass


@pytest.mark.parametrize(
    ("entity_id", "state", "expected"),
    [
        ("device_tracker.phone", "home", True),
        ("device_tracker.phone", "not_home", False),
        ("zone.home", "2", True),
        ("zone.home", "0", False),
        ("binary_sensor.occupancy", "on", True),
        ("binary_sensor.occupancy", "off", False),
        ("input_boolean.guests", "on", True),
        ("input_boolean.guests", "off", False),
    ],
)
def test_presence_per_domain(entity_id, state, expected):
    assert is_presence_detected(_hass_with_state(state), entity_id) is expected


def test_presence_without_sensor_counts_as_present():
    assert is_presence_detected(_hass_with_state("off"), None) is True


@pytest.mark.parametrize("state", [None, "unknown", "unavailable"])
def test_presence_unreadable_sensor_counts_as_present(state):
    assert is_presence_detected(_hass_with_state(state), "binary_sensor.x") is True


def test_presence_non_numeric_zone_count_does_not_raise():
    """int() on the zone state used to raise ValueError and abort the tick."""
    assert is_presence_detected(_hass_with_state("garbage"), "zone.home") is True
