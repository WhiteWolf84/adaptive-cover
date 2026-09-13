"""Tests for the switch side effects that must move covers immediately."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

pytest.importorskip("homeassistant.components.switch")

from custom_components.adaptive_cover.switch import AdaptiveCoverSwitch  # noqa: E402


def make_switch(key: str, *, security_active=(False, False)) -> AdaptiveCoverSwitch:
    """Build a switch whose coordinator reports `security_active` before/after."""
    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.async_apply_target_now = AsyncMock()
    coordinator.control_toggle = True
    type(coordinator).security_active = PropertyMock(side_effect=list(security_active))

    switch = AdaptiveCoverSwitch.__new__(AdaptiveCoverSwitch)
    switch._key = key
    switch.coordinator = coordinator
    switch.async_write_ha_state = MagicMock()
    return switch


@pytest.fixture(autouse=True)
def _no_entity_name():
    with patch.object(AdaptiveCoverSwitch, "name", new_callable=PropertyMock):
        yield


async def test_security_on_while_away_moves_covers_now():
    switch = make_switch("security_toggle", security_active=(False, True))

    await switch._async_set_state(True)

    assert switch.coordinator.security_toggle is True
    switch.coordinator.async_apply_target_now.assert_awaited_once()


async def test_security_off_while_away_restores_adaptive_position_now():
    switch = make_switch("security_toggle", security_active=(True, False))

    await switch._async_set_state(False)

    switch.coordinator.async_apply_target_now.assert_awaited_once()


async def test_security_toggle_while_home_does_not_move_covers():
    switch = make_switch("security_toggle", security_active=(False, False))

    await switch._async_set_state(True)

    switch.coordinator.async_apply_target_now.assert_not_awaited()


async def test_security_restore_does_not_move_covers():
    switch = make_switch("security_toggle", security_active=(False, True))

    await switch._async_set_state(True, from_restore=True)

    switch.coordinator.async_apply_target_now.assert_not_awaited()


async def test_security_ignored_when_control_toggle_off():
    switch = make_switch("security_toggle", security_active=(False, True))
    switch.coordinator.control_toggle = False

    await switch._async_set_state(True)

    switch.coordinator.async_apply_target_now.assert_not_awaited()


async def test_control_toggle_on_applies_current_target():
    switch = make_switch("control_toggle")

    await switch._async_set_state(True)

    switch.coordinator.async_apply_target_now.assert_awaited_once()
