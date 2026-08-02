"""Tests for the pandas-free / tz-aware / cached calculation logic."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import math

import pytest
from astral import Observer

from custom_components.adaptive_cover.calculation import (
    AdaptiveTiltCover,
    AdaptiveVerticalCover,
    ClimateCoverData,
    ClimateCoverState,
)

BASE = datetime(2026, 6, 28, tzinfo=UTC)


def make_cover(**overrides) -> AdaptiveVerticalCover:
    """Build a concrete cover with a fake astral location."""
    kwargs = {
        "hass": MagicMock(),
        "logger": MagicMock(),
        "sol_azi": 180.0,
        "sol_elev": 30.0,
        "sunset_pos": 0,
        "sunset_off": 0,
        "sunrise_off": 0,
        "timezone": "Europe/Rome",
        "fov_left": 90,
        "fov_right": 90,
        "win_azi": 180,
        "h_def": 60,
        "max_pos": 100,
        "min_pos": 0,
        "max_pos_bool": False,
        "min_pos_bool": False,
        "blind_spot_left": None,
        "blind_spot_right": None,
        "blind_spot_elevation": None,
        "blind_spot_on": False,
        "min_elevation": None,
        "max_elevation": None,
        "distance": 0.5,
        "h_win": 2.1,
        "obstacle_height": 0,
        "obstacle_distance": 0,
    }
    kwargs.update(overrides)
    with patch(
        "custom_components.adaptive_cover.sun.get_observer",
        return_value=Observer(41.9, 12.5, 0.0),
    ):
        return AdaptiveVerticalCover(**kwargs)


def _grid(n: int) -> list[datetime]:
    return [BASE + timedelta(minutes=5 * i) for i in range(n)]


# --------------------------------------------------------------- solar_times
def test_solar_times_returns_first_and_last_in_window():
    cover = make_cover(win_azi=180, fov_left=90, fov_right=90)
    # azi_min_abs=90, azi_max_abs=270 -> accepted span [90, 270]
    times = _grid(6)
    azimuth = [80, 100, 150, 260, 280, 200]
    elevation = [10, 10, 10, 10, 10, -5]
    cover.sun_data = SimpleNamespace(
        times=times, solar_azimuth=azimuth, solar_elevation=elevation
    )

    start, end = cover.solar_times()

    # idx0 out of azimuth band, idx4 out of band, idx5 below horizon.
    assert start == times[1]
    assert end == times[3]


def test_solar_times_none_when_never_in_window():
    cover = make_cover()
    times = _grid(4)
    cover.sun_data = SimpleNamespace(
        times=times,
        solar_azimuth=[10, 20, 30, 40],  # all outside [90, 270]
        solar_elevation=[10, 10, 10, 10],
    )

    assert cover.solar_times() == (None, None)


def test_solar_times_handles_wraparound_band():
    # Window facing north: azi_min_abs=315, azi_max_abs=45 -> band wraps 0/360.
    cover = make_cover(win_azi=0, fov_left=45, fov_right=45)
    times = _grid(4)
    cover.sun_data = SimpleNamespace(
        times=times,
        solar_azimuth=[350, 10, 180, 30],  # 350,10,30 inside wrapped band; 180 out
        solar_elevation=[5, 5, 5, 5],
    )

    start, end = cover.solar_times()
    assert start == times[0]
    assert end == times[3]


def test_solar_times_returns_aware_datetimes():
    cover = make_cover()
    times = _grid(3)
    cover.sun_data = SimpleNamespace(
        times=times, solar_azimuth=[180, 180, 180], solar_elevation=[5, 5, 5]
    )
    start, end = cover.solar_times()
    assert start.tzinfo is not None and end.tzinfo is not None


# --------------------------------------------------------------- sunset_valid
def _with_sun(cover, sunset_hour, sunrise_hour):
    cover.sun_data = SimpleNamespace(
        sunset=lambda: BASE + timedelta(hours=sunset_hour),
        sunrise=lambda: BASE + timedelta(hours=sunrise_hour),
    )


def test_sunset_valid_true_after_sunset():
    cover = make_cover(sunset_off=0, sunrise_off=0)
    _with_sun(cover, sunset_hour=20, sunrise_hour=5)
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=22),
    ):
        assert cover.sunset_valid is True


def test_sunset_valid_true_before_sunrise():
    cover = make_cover()
    _with_sun(cover, sunset_hour=20, sunrise_hour=5)
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=3),
    ):
        assert cover.sunset_valid is True


def test_sunset_valid_false_during_day():
    cover = make_cover()
    _with_sun(cover, sunset_hour=20, sunrise_hour=5)
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=12),
    ):
        assert cover.sunset_valid is False


def test_sunset_offset_shifts_threshold():
    cover = make_cover(sunset_off=60)  # sunset effectively pushed one hour later
    _with_sun(cover, sunset_hour=20, sunrise_hour=5)
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=20, minutes=30),
    ):
        # 20:30 is after raw sunset but before sunset+60min -> still daytime.
        assert cover.sunset_valid is False


def test_sunset_valid_is_cached_for_the_tick():
    cover = make_cover()
    _with_sun(cover, sunset_hour=20, sunrise_hour=5)
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=22),
    ):
        first = cover.sunset_valid
    # Even though "now" moved to midday, the cached value persists this tick.
    with patch(
        "custom_components.adaptive_cover.calculation.dt_util.utcnow",
        return_value=BASE + timedelta(hours=12),
    ):
        assert cover.sunset_valid == first is True


# ------------------------------------------------------ ClimateCoverData cache
def make_climate(**overrides) -> ClimateCoverData:
    kwargs = {
        "hass": MagicMock(),
        "logger": MagicMock(),
        "temp_entity": "sensor.inside",
        "temp_low": 18.0,
        "temp_high": 25.0,
        "presence_entity": None,
        "weather_entity": None,
        "weather_condition": None,
        "outside_entity": "sensor.outside",
        "temp_switch": True,
        "blind_type": "cover_blind",
        "transparent_blind": False,
        "lux_entity": None,
        "irradiance_entity": None,
        "lux_threshold": None,
        "irradiance_threshold": None,
        "temp_summer_outside": None,
        "_use_lux": False,
        "_use_irradiance": False,
    }
    kwargs.update(overrides)
    return ClimateCoverData(**kwargs)


def test_state_registry_is_read_once_per_tick():
    """is_summer + is_winter + get_current_temperature share one state read."""
    with patch(
        "custom_components.adaptive_cover.calculation.get_safe_state",
        return_value="21.5",
    ) as get_state:
        data = make_climate()
        _ = data.is_summer
        _ = data.is_winter
        _ = data.get_current_temperature
        # Without caching outside_temperature would be fetched repeatedly.
        assert get_state.call_count == 1


def test_get_current_temperature_value():
    with patch(
        "custom_components.adaptive_cover.calculation.get_safe_state",
        return_value="30.0",
    ):
        data = make_climate()
        assert data.get_current_temperature == 30.0
        assert data.is_summer is True
        assert data.is_winter is False


# ------------------------------------------------------------- tilt geometry
def make_tilt(**overrides) -> AdaptiveTiltCover:
    """Build a venetian (tilt) cover with a fake astral location."""
    kwargs = {
        "hass": MagicMock(),
        "logger": MagicMock(),
        "sol_azi": 180.0,
        "sol_elev": 30.0,
        "sunset_pos": 0,
        "sunset_off": 0,
        "sunrise_off": 0,
        "timezone": "Europe/Rome",
        "fov_left": 90,
        "fov_right": 90,
        "win_azi": 180,
        "h_def": 60,
        "max_pos": 100,
        "min_pos": 0,
        "max_pos_bool": False,
        "min_pos_bool": False,
        "blind_spot_left": None,
        "blind_spot_right": None,
        "blind_spot_elevation": None,
        "blind_spot_on": False,
        "min_elevation": None,
        "max_elevation": None,
        "slat_distance": 2.0,
        "depth": 3.0,
        "mode": "mode1",
    }
    kwargs.update(overrides)
    with patch(
        "custom_components.adaptive_cover.sun.get_observer",
        return_value=Observer(41.9, 12.5, 0.0),
    ):
        return AdaptiveTiltCover(**kwargs)


def test_tilt_position_no_nan_when_slat_exceeds_depth():
    """slat_distance > depth drives the sqrt radicand negative; must not NaN/crash."""
    cover = make_tilt(slat_distance=10.0, depth=5.0, sol_elev=30.0)
    result = cover.calculate_position()
    assert not math.isnan(result)
    # round(NaN) used to raise ValueError and abort the coordinator tick.
    assert isinstance(cover.calculate_percentage(), int)


def test_tilt_position_valid_config_is_finite():
    """A geometrically valid config (slat_distance < depth) is unchanged/finite."""
    cover = make_tilt(slat_distance=2.0, depth=3.0, sol_elev=30.0)
    result = cover.calculate_position()
    assert not math.isnan(result)
    assert 0 <= result <= 180


# --------------------------------------------------- redundant tilt computation
def test_tilt_percentage_computes_the_angle_once():
    """calculate_position ran twice (once per scaling) while only one was used."""
    cover = make_tilt()
    with patch.object(
        AdaptiveTiltCover, "calculate_position", return_value=45.0
    ) as position:
        cover.calculate_percentage()
    assert position.call_count == 1


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("mode1", 50), ("mode2", 25)],  # 45/90*100 and 45/180*100
)
def test_tilt_percentage_scaling_per_mode(mode, expected):
    """Equivalence check: the single-call version keeps both mappings intact."""
    cover = make_tilt(mode=mode)
    with patch.object(AdaptiveTiltCover, "calculate_position", return_value=45.0):
        assert cover.calculate_percentage() == expected


def test_climate_tilt_state_skips_the_normal_branch():
    """For tilt covers normal_type_cover()'s result was computed then thrown away.

    Besides the wasted work it emitted debug lines describing decisions that were
    never applied, which made the logs actively misleading.
    """
    cover = make_tilt()
    state = ClimateCoverState(cover, make_climate(blind_type="cover_tilt"))

    with (
        patch.object(ClimateCoverState, "tilt_state", return_value=42) as tilt_state,
        patch.object(ClimateCoverState, "normal_type_cover") as normal,
        patch(
            "custom_components.adaptive_cover.calculation.get_safe_state",
            return_value="21.0",
        ),
    ):
        assert state.get_state() == 42

    tilt_state.assert_called_once()
    normal.assert_not_called()


def test_climate_non_tilt_state_still_uses_the_normal_branch():
    cover = make_cover()
    state = ClimateCoverState(cover, make_climate(blind_type="cover_blind"))

    with (
        patch.object(ClimateCoverState, "normal_type_cover", return_value=37) as normal,
        patch.object(ClimateCoverState, "tilt_state") as tilt_state,
        patch(
            "custom_components.adaptive_cover.calculation.get_safe_state",
            return_value="21.0",
        ),
    ):
        assert state.get_state() == 37

    normal.assert_called_once()
    tilt_state.assert_not_called()
