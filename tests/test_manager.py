"""Tests for manual-override detection in AdaptiveCoverManager.

Regression coverage for the spurious-lock bug: routine attribute-only updates
(battery, linkquality, ...) must not be mistaken for a manual move when the
cover's ideal position has drifted from its physical position.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.adaptive_cover.coordinator.manager import AdaptiveCoverManager


def make_manager() -> AdaptiveCoverManager:
    manager = AdaptiveCoverManager({"minutes": 15}, MagicMock())
    manager.add_covers(["cover.x"])
    return manager


def make_event(entity, new_pos, old_pos, attr="current_position"):
    new_state = SimpleNamespace(
        attributes={attr: new_pos} if new_pos is not None else {},
        last_updated=datetime.now(UTC),
    )
    old_state = (
        SimpleNamespace(attributes={attr: old_pos}, state="open")
        if old_pos is not None
        else None
    )
    return SimpleNamespace(entity_id=entity, new_state=new_state, old_state=old_state)


def _handle(manager, event, our_state, *, threshold=5, blind_type="cover_blind"):
    manager.handle_state_change(
        event,
        our_state,
        blind_type,
        allow_reset=True,
        is_waiting=lambda _e: False,
        manual_threshold=threshold,
    )


def test_attribute_only_update_does_not_lock():
    """Position unchanged (telemetry noise) must not trigger manual override."""
    manager = make_manager()
    # Physical stays at 50, ideal drifted to 55; a battery report re-emits 50.
    _handle(manager, make_event("cover.x", new_pos=50, old_pos=50), our_state=55)
    assert manager.is_cover_manual("cover.x") is False


def test_real_move_beyond_threshold_locks():
    """An actual position change away from ideal is a manual override."""
    manager = make_manager()
    _handle(manager, make_event("cover.x", new_pos=30, old_pos=50), our_state=55)
    assert manager.is_cover_manual("cover.x") is True


def test_real_move_within_threshold_does_not_lock():
    """A move smaller than manual_threshold is still ignored (existing logic)."""
    manager = make_manager()
    _handle(manager, make_event("cover.x", new_pos=53, old_pos=50), our_state=55)
    assert manager.is_cover_manual("cover.x") is False


def test_tilt_attribute_only_update_does_not_lock():
    manager = make_manager()
    event = make_event("cover.x", new_pos=50, old_pos=50, attr="current_tilt_position")
    _handle(manager, event, our_state=55, blind_type="cover_tilt")
    assert manager.is_cover_manual("cover.x") is False
