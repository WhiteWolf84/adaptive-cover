"""Tests for the pandas-free :mod:`sun` module."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import astral.sun as astral_sun
import pytest
from astral import Observer

from custom_components.adaptive_cover.sun import _STEP, _STEPS, SunData, get_observer


@pytest.fixture
def sun_data():
    """Return a SunData bound to a fake astral observer (no real HA needed)."""
    with patch(
        "custom_components.adaptive_cover.sun.get_observer",
        return_value=Observer(41.9, 12.5, 0.0),
    ):
        return SunData("Europe/Rome", MagicMock(name="hass"))


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
    with (
        patch.object(astral_sun, "azimuth", return_value=123.4),
        patch.object(astral_sun, "elevation", return_value=42.0),
    ):
        azimuth = sun_data.solar_azimuth
        elevation = sun_data.solar_elevation

    assert len(azimuth) == len(elevation) == _STEPS
    assert azimuth[0] == 123.4
    assert elevation[0] == 42.0


def test_solar_positions_are_cached(sun_data):
    with (
        patch.object(astral_sun, "azimuth", return_value=1.0) as azimuth,
        patch.object(astral_sun, "elevation", return_value=1.0) as elevation,
    ):
        assert sun_data.solar_azimuth is sun_data.solar_azimuth
        assert sun_data.solar_elevation is sun_data.solar_elevation
        # azimuth + elevation each iterate the grid once -> 289 calls each.
        assert azimuth.call_count == _STEPS
        assert elevation.call_count == _STEPS


def test_positions_are_computed_for_the_configured_observer(sun_data):
    """Every sample must use the HA observer, elevation included."""
    with patch.object(astral_sun, "azimuth", return_value=0.0) as azimuth:
        _ = sun_data.solar_azimuth
    assert all(call.args[0] is sun_data.observer for call in azimuth.call_args_list)


# ------------------------------------------------------------ configured timezone
def _sun_data_at(utc_moment: datetime) -> SunData:
    """SunData whose "now" is fixed, so _today is deterministic."""
    with (
        patch(
            "custom_components.adaptive_cover.sun.get_observer",
            return_value=Observer(41.9, 12.5, 0.0),
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
    with (
        patch.object(astral_sun, "sunset") as sunset,
        patch.object(astral_sun, "sunrise") as sunrise,
    ):
        data.sunset()
        data.sunrise()
    assert sunset.call_args.args == (data.observer, date(2026, 8, 3))
    assert sunrise.call_args.args == (data.observer, date(2026, 8, 3))


# ---------------------------------------------------------------- observer helper
def test_get_observer_prefers_the_modern_helper():
    """get_astral_location is deprecated and removed in HA Core 2027.7."""
    hass = MagicMock(name="hass")
    helper = MagicMock(name="ha_sun_helper")
    helper.get_astral_observer.return_value = Observer(1.0, 2.0, 3.0)

    with patch("custom_components.adaptive_cover.sun.sun_helper", helper):
        observer = get_observer(hass)

    helper.get_astral_observer.assert_called_once_with(hass)
    helper.get_astral_location.assert_not_called()
    assert observer == Observer(1.0, 2.0, 3.0)


def test_get_observer_falls_back_on_older_cores():
    """Older supported cores have no get_astral_observer; build it ourselves."""

    class _OldHelper:
        """Helper module without the modern name."""

        @staticmethod
        def get_astral_location(hass):
            return SimpleNamespace(latitude=41.9, longitude=12.5), 300.0

    with patch("custom_components.adaptive_cover.sun.sun_helper", _OldHelper):
        observer = get_observer(MagicMock(name="hass"))

    # Same shape the modern helper would have produced, elevation included.
    assert observer == Observer(41.9, 12.5, 300.0)
