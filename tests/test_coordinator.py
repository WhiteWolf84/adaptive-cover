"""Regression tests for AdaptiveDataUpdateCoordinator logic.

The coordinator is instantiated via ``__new__`` so these stay pure unit tests: a real
``__init__`` needs a running Home Assistant, but every behaviour under test here is
plain Python over a handful of attributes.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.adaptive_cover.coordinator import AdaptiveDataUpdateCoordinator

ROME = ZoneInfo("Europe/Rome")


def make_coordinator(**overrides) -> AdaptiveDataUpdateCoordinator:
    """Build a coordinator with only the attributes the tested paths touch."""
    coordinator = AdaptiveDataUpdateCoordinator.__new__(AdaptiveDataUpdateCoordinator)
    defaults = {
        "logger": MagicMock(),
        "hass": MagicMock(),
        "service": MagicMock(),
        "state_change_data": None,
        "_cover_type": "cover_blind",
        "ignore_intermediate_states": False,
        "cover_state_change": False,
        "start_time": None,
        "start_time_entity": None,
        "end_time": None,
        "end_time_entity": None,
        "_start_time": None,
        "_start_after_end_logged": False,
        "_scheduled_time": None,
        "timed_refresh": False,
        "start_value": None,
        "end_value": None,
        "normal_list": None,
        "new_list": None,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(coordinator, key, value)
    return coordinator


def _now(moment: dt.datetime):
    """Patch dt_util.now() in both the coordinator and the helper module."""
    return patch(
        "custom_components.adaptive_cover.coordinator.dt_util.now",
        return_value=moment,
    ), patch(
        "custom_components.adaptive_cover.helpers.dt_util.now", return_value=moment
    )


# ------------------------------------------------- removed entity (new_state None)
async def test_cover_state_change_ignores_removed_entity():
    """Entity removal fires state_changed with new_state=None -> used to crash.

    Every consumer downstream dereferences new_state (.state, .attributes,
    .last_updated), so the event must be dropped before that happens.
    """
    coordinator = make_coordinator()
    event = MagicMock()
    event.data = {
        "entity_id": "cover.x",
        "old_state": MagicMock(state="open"),
        "new_state": None,
    }

    await coordinator.async_check_cover_state_change(event)

    assert coordinator.state_change_data is None
    assert coordinator.cover_state_change is False


async def test_cover_state_change_still_ignores_missing_old_state():
    coordinator = make_coordinator()
    event = MagicMock()
    event.data = {
        "entity_id": "cover.x",
        "old_state": None,
        "new_state": MagicMock(state="open"),
    }

    await coordinator.async_check_cover_state_change(event)

    assert coordinator.state_change_data is None


# ------------------------------------------------------------ check_adaptive_time
def test_start_after_end_is_caught_on_the_very_first_call():
    """_start_time used to be populated only as a side effect of after_start_time.

    check_adaptive_time read it *before* that ran, so on the first tick it was None
    and the guard was skipped entirely — adaptive control stayed enabled with an
    inverted window.
    """
    coordinator = make_coordinator(start_time="20:00:00", end_time="08:00:00")
    now_patch, helper_patch = _now(dt.datetime(2026, 8, 2, 12, 0, tzinfo=ROME))
    with now_patch, helper_patch:
        assert coordinator.check_adaptive_time is False

    assert coordinator._start_after_end_logged is True
    coordinator.logger.warning.assert_called_once()


def test_start_after_end_warns_only_once():
    coordinator = make_coordinator(start_time="20:00:00", end_time="08:00:00")
    now_patch, helper_patch = _now(dt.datetime(2026, 8, 2, 12, 0, tzinfo=ROME))
    with now_patch, helper_patch:
        assert coordinator.check_adaptive_time is False
        assert coordinator.check_adaptive_time is False

    assert coordinator.logger.warning.call_count == 1


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(7, False), (9, True), (12, True), (21, False)],
)
def test_window_bounds(hour, expected):
    coordinator = make_coordinator(start_time="08:00:00", end_time="20:00:00")
    now_patch, helper_patch = _now(dt.datetime(2026, 8, 2, hour, 0, tzinfo=ROME))
    with now_patch, helper_patch:
        assert coordinator.check_adaptive_time is expected


def test_no_bounds_configured_is_always_within():
    coordinator = make_coordinator()
    now_patch, helper_patch = _now(dt.datetime(2026, 8, 2, 3, 0, tzinfo=ROME))
    with now_patch, helper_patch:
        assert coordinator.check_adaptive_time is True


def test_midnight_end_time_rolls_to_next_day():
    """A midnight end time means the end of today, not its start."""
    coordinator = make_coordinator(end_time="00:00:00")
    now_patch, helper_patch = _now(dt.datetime(2026, 8, 2, 22, 0, tzinfo=ROME))
    with now_patch, helper_patch:
        end = coordinator._resolve_end_time()
        assert coordinator.check_adaptive_time is True
    assert end.date() == dt.date(2026, 8, 3)


# --------------------------------------------------------------- timed refresh
async def test_timed_refresh_skipped_when_nothing_scheduled():
    coordinator = make_coordinator()
    coordinator.async_refresh = AsyncMock()

    await coordinator.async_timed_refresh(None)

    assert coordinator.timed_refresh is False
    coordinator.async_refresh.assert_not_awaited()


async def test_timed_refresh_survives_a_late_callback():
    """async_track_point_in_time fires "at or after"; a 30s-late firing must count.

    The previous +-1s window against a freshly parsed end time dropped those, so
    the end-of-day position was never applied.
    """
    scheduled = dt.datetime(2026, 8, 2, 20, 0, tzinfo=ROME)
    coordinator = make_coordinator(_scheduled_time=scheduled)
    coordinator.async_refresh = AsyncMock()

    now_patch, helper_patch = _now(scheduled + dt.timedelta(seconds=30))
    with now_patch, helper_patch:
        await coordinator.async_timed_refresh(None)

    assert coordinator.timed_refresh is True
    coordinator.async_refresh.assert_awaited_once()


async def test_timed_refresh_ignores_an_early_callback():
    scheduled = dt.datetime(2026, 8, 2, 20, 0, tzinfo=ROME)
    coordinator = make_coordinator(_scheduled_time=scheduled)
    coordinator.async_refresh = AsyncMock()

    now_patch, helper_patch = _now(scheduled - dt.timedelta(minutes=5))
    with now_patch, helper_patch:
        await coordinator.async_timed_refresh(None)

    assert coordinator.timed_refresh is False
    coordinator.async_refresh.assert_not_awaited()


# ------------------------------------------------------------ interpolate_states
def test_interpolation_applies_with_a_zero_start():
    """0 is a selectable endpoint (selector min=0); truthiness skipped the mapping."""
    coordinator = make_coordinator(start_value=0, end_value=90)
    assert coordinator.interpolate_states(70) == 63


def test_interpolation_applies_with_a_zero_end():
    """A descending range is the documented way to invert the state."""
    coordinator = make_coordinator(start_value=20, end_value=0)
    assert coordinator.interpolate_states(30) == 14


def test_interpolation_untouched_for_non_zero_endpoints():
    coordinator = make_coordinator(start_value=10, end_value=90)
    assert [coordinator.interpolate_states(s) for s in (0, 25, 70, 100)] == [
        0,
        30,
        66,
        100,
    ]


def test_no_interpolation_configured_is_identity():
    coordinator = make_coordinator()
    assert coordinator.interpolate_states(42) == 42


def test_explicit_lists_take_precedence():
    """The list pair overrides start/end, and endpoints snap to 0/100."""
    coordinator = make_coordinator(
        start_value=10,
        end_value=90,
        normal_list=["0", "50", "100"],
        new_list=["0", "20", "100"],
    )
    assert coordinator.interpolate_states(50) == 20
    assert coordinator.interpolate_states(75) == 60
    # Hitting min/max of the mapped range sends the real fully-closed/open value.
    assert coordinator.interpolate_states(0) == 0
    assert coordinator.interpolate_states(100) == 100
