"""Tests for the pandas-free :mod:`sun` module."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.adaptive_cover.sun import _STEP, _STEPS, SunData


@pytest.fixture
def sun_data():
    """Return a SunData bound to a fake astral location (no real HA needed)."""
    location = MagicMock(name="astral_location")
    with patch(
        "custom_components.adaptive_cover.sun.get_astral_location",
        return_value=(location, 0.0),
    ):
        data = SunData("Europe/Rome", MagicMock(name="hass"))
    return data


def test_grid_has_289_points(sun_data):
    """A full day on a 5-minute grid, inclusive of the closing midnight."""
    assert _STEPS == 289
    assert len(sun_data.times) == 289


def test_grid_is_timezone_aware(sun_data):
    assert all(t.tzinfo is not None for t in sun_data.times)


def test_grid_spacing_is_five_minutes(sun_data):
    assert timedelta(minutes=5) == _STEP
    times = sun_data.times
    diffs = {b - a for a, b in zip(times, times[1:])}
    # Outside DST transitions the absolute spacing is exactly the step.
    assert diffs == {_STEP}


def test_times_is_cached(sun_data):
    """cached_property returns the very same list (computed once per tick)."""
    assert sun_data.times is sun_data.times


def test_solar_positions_span_the_grid(sun_data):
    sun_data.location.solar_azimuth.return_value = 123.4
    sun_data.location.solar_elevation.return_value = 42.0

    azimuth = sun_data.solar_azimuth
    elevation = sun_data.solar_elevation

    assert len(azimuth) == len(elevation) == _STEPS
    assert azimuth[0] == 123.4
    assert elevation[0] == 42.0


def test_solar_positions_are_cached(sun_data):
    sun_data.location.solar_azimuth.return_value = 1.0
    sun_data.location.solar_elevation.return_value = 1.0

    assert sun_data.solar_azimuth is sun_data.solar_azimuth
    assert sun_data.solar_elevation is sun_data.solar_elevation
    # azimuth + elevation each iterate the grid once -> 289 calls each.
    assert sun_data.location.solar_azimuth.call_count == _STEPS
    assert sun_data.location.solar_elevation.call_count == _STEPS


# ------------------------------------------------------------ configured timezone
def _sun_data_at(utc_moment: datetime) -> SunData:
    """SunData whose "now" is fixed, so _today is deterministic."""
    with (
        patch(
            "custom_components.adaptive_cover.sun.get_astral_location",
            return_value=(MagicMock(), 0.0),
        ),
        patch(
            "custom_components.adaptive_cover.sun.dt_util.utcnow",
            return_value=utc_moment,
        ),
    ):
        data = SunData("Europe/Rome", MagicMock(name="hass"))
        # Materialise the cached properties while the clock is still patched.
        _ = data.times
        _ = data._today
    return data


def test_today_follows_the_configured_timezone_not_the_host():
    """23:30 UTC is already the next day in Rome.

    The module used ``date.today()``, which reads the host clock. On a UTC container
    with a local HA timezone that is a different date for part of every day, shifting
    the whole 24h grid — and the sunrise/sunset behind ``sunset_valid`` — by a day.
    """
    data = _sun_data_at(datetime(2026, 8, 2, 23, 30, tzinfo=UTC))
    assert data._today == date(2026, 8, 3)


def test_grid_starts_at_local_midnight_of_the_configured_day():
    data = _sun_data_at(datetime(2026, 8, 2, 23, 30, tzinfo=UTC))
    start = data.times[0]
    assert start.date() == date(2026, 8, 3)
    assert (start.hour, start.minute) == (0, 0)
    assert start.utcoffset() == timedelta(hours=2)


def test_sunrise_and_sunset_use_the_same_day_as_the_grid():
    data = _sun_data_at(datetime(2026, 8, 2, 23, 30, tzinfo=UTC))
    data.sunset()
    data.sunrise()
    assert data.location.sunset.call_args[0][0] == date(2026, 8, 3)
    assert data.location.sunrise.call_args[0][0] == date(2026, 8, 3)
