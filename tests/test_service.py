"""Tests for CoverServiceCaller throttle/position guards.

Covers two regressions:
- check_time_delta must throttle on our own last command (_target_set_at), not on
  the cover entity's last_updated, so chatty devices can't freeze adaptive control.
- check_position must use TARGET_TOLERANCE (matching acknowledge_target), so a motor
  that stops a percent short of a boundary (0/100) isn't re-commanded forever.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.adaptive_cover.coordinator.service import (
    TARGET_TOLERANCE,
    CoverServiceCaller,
)


def make_caller(cover_type="cover_blind") -> CoverServiceCaller:
    return CoverServiceCaller(MagicMock(), MagicMock(), cover_type)


# ------------------------------------------------------------- check_position
def _with_position(value):
    return patch(
        "custom_components.adaptive_cover.coordinator.service.state_attr",
        return_value=value,
    )


def test_check_position_within_tolerance_is_reached():
    """1% short of target counts as reached -> no re-command (boundary spam fix)."""
    caller = make_caller()
    with _with_position(99):
        assert caller.check_position("cover.x", 100) is False


def test_check_position_exact_match_is_reached():
    caller = make_caller()
    with _with_position(100):
        assert caller.check_position("cover.x", 100) is False


def test_check_position_beyond_tolerance_moves():
    caller = make_caller()
    with _with_position(95):
        assert caller.check_position("cover.x", 100) is True


def test_check_position_unavailable_returns_false():
    caller = make_caller()
    with _with_position(None):
        assert caller.check_position("cover.x", 100) is False


# ----------------------------------------------------------- check_time_delta
def test_time_delta_true_when_never_commanded():
    """No prior command -> allowed (and immune to cover telemetry)."""
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    assert caller.check_time_delta("cover.x") is True


def test_time_delta_false_within_threshold():
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    caller._target_set_at["cover.x"] = dt.datetime.now(dt.UTC)
    assert caller.check_time_delta("cover.x") is False


def test_time_delta_true_after_threshold():
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    caller._target_set_at["cover.x"] = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=3)
    assert caller.check_time_delta("cover.x") is True


def test_time_delta_ignores_chatty_entity_last_updated():
    """A cover reporting telemetry every tick must not spoof the throttle."""
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    # hass would report a fresh last_updated; the guard must ignore it entirely.
    caller.hass.states.get.return_value = MagicMock(
        last_updated=dt.datetime.now(dt.UTC)
    )
    assert caller.check_time_delta("cover.x") is True


def test_tolerance_constant_is_one():
    assert TARGET_TOLERANCE == 1


# ------------------------------------------------- failed call rolls the clock back
async def test_failed_service_call_does_not_arm_the_throttle():
    """A command that never ran must not suppress the next one.

    set_manual_position stamps _target_set_at *before* calling the service. On
    failure it used to clear only wait_for_target, so check_time_delta — which
    measures from _target_set_at — blocked adaptive control for time_threshold
    minutes because of a command that never reached the cover.
    """
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    caller.hass.services.async_call = AsyncMock(
        side_effect=HomeAssistantError("cover offline")
    )

    with _with_position(0), pytest.raises(HomeAssistantError):
        await caller.set_manual_position("cover.x", 100)

    assert caller.wait_for_target["cover.x"] is False
    assert "cover.x" not in caller._target_set_at
    assert "cover.x" not in caller.target_call
    assert caller.check_time_delta("cover.x") is True
    assert caller.is_waiting("cover.x") is False


async def test_successful_service_call_arms_the_throttle():
    caller = make_caller()
    caller.configure(min_change=1, time_threshold=2)
    caller.hass.services.async_call = AsyncMock()

    with _with_position(0):
        await caller.set_manual_position("cover.x", 100)

    assert caller.wait_for_target["cover.x"] is True
    assert caller.target_call["cover.x"] == 100
    assert caller.check_time_delta("cover.x") is False
