"""Manual-override tracker for adaptive cover entities."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any


class AdaptiveCoverManager:
    """Track position changes that look like manual overrides."""

    def __init__(self, reset_duration: dict[str, int], logger: Any) -> None:
        """Initialize the AdaptiveCoverManager."""
        self.covers: set[str] = set()
        self.manual_control: dict[str, bool] = {}
        self.manual_control_time: dict[str, dt.datetime] = {}
        self.reset_duration = dt.timedelta(**reset_duration)
        self.logger = logger

    def add_covers(self, entity: list[str]) -> None:
        """Update set with entities."""
        self.covers.update(entity)

    def handle_state_change(
        self,
        states_data,
        our_state: int,
        blind_type: str,
        allow_reset: bool,
        is_waiting: Callable[[str], bool],
        manual_threshold: int | None,
    ) -> None:
        """Process state change event."""
        event = states_data
        if event is None:
            return
        entity_id = event.entity_id
        if entity_id not in self.covers:
            return
        if is_waiting(entity_id):
            return

        new_state = event.new_state

        old_state = event.old_state
        if blind_type == "cover_tilt":
            attr = "current_tilt_position"
        else:
            attr = "current_position"
        new_position = new_state.attributes.get(attr)
        old_position = old_state.attributes.get(attr) if old_state else None

        if new_position is None:
            self.logger.debug(
                "No position attribute for %s; skipping manual detection", entity_id
            )
            return

        # Only treat this as a possible manual override when the cover actually
        # moved. Routine attribute-only updates (battery, linkquality, ...) fire a
        # state-change event with the position unchanged; without this guard a
        # throttled cover whose ideal state has drifted would be flagged as
        # manually overridden by unrelated telemetry.
        if old_position is not None and new_position == old_position:
            self.logger.debug(
                "Position unchanged for %s (%s); not a manual move", entity_id, new_position
            )
            return

        if new_position != our_state:
            if (
                manual_threshold is not None
                and abs(our_state - new_position) < manual_threshold
            ):
                self.logger.debug(
                    "Position change is less than threshold %s for %s",
                    manual_threshold,
                    entity_id,
                )
                return
            self.logger.debug(
                "Manual change detected for %s. Our state: %s, new state: %s",
                entity_id,
                our_state,
                new_position,
            )
            self.logger.debug(
                "Set manual control for %s, for at least %s seconds, reset_allowed: %s",
                entity_id,
                self.reset_duration.total_seconds(),
                allow_reset,
            )
            self.mark_manual_control(entity_id)
            self.set_last_updated(entity_id, new_state, allow_reset)

    def set_last_updated(self, entity_id: str, new_state, allow_reset: bool) -> None:
        """Set last updated time for manual control."""
        if entity_id not in self.manual_control_time or allow_reset:
            last_updated = new_state.last_updated
            self.manual_control_time[entity_id] = last_updated
            self.logger.debug(
                "Updating last updated for manual control to %s for %s. Allow reset:%s",
                last_updated,
                entity_id,
                allow_reset,
            )
        elif not allow_reset:
            self.logger.debug(
                "Already manual control time specified for %s, reset is not allowed by user setting:%s",
                entity_id,
                allow_reset,
            )

    def mark_manual_control(self, cover: str) -> None:
        """Mark cover as under manual control."""
        self.manual_control[cover] = True

    async def reset_if_needed(self) -> None:
        """Reset manual control state of the covers."""
        current_time = dt.datetime.now(dt.UTC)
        for entity_id, last_updated in dict(self.manual_control_time).items():
            if current_time - last_updated > self.reset_duration:
                self.logger.debug(
                    "Resetting manual override for %s, because duration has elapsed",
                    entity_id,
                )
                self.reset(entity_id)

    def reset(self, entity_id: str) -> None:
        """Reset manual control for a cover."""
        self.manual_control[entity_id] = False
        self.manual_control_time.pop(entity_id, None)
        self.logger.debug("Reset manual override for %s", entity_id)

    def is_cover_manual(self, entity_id: str) -> bool:
        """Check if a cover is under manual control."""
        return self.manual_control.get(entity_id, False)

    @property
    def binary_cover_manual(self) -> bool:
        """Check if any cover is under manual control."""
        return any(value for value in self.manual_control.values())

    @property
    def manual_controlled(self) -> list[str]:
        """Get the list of covers under manual control."""
        return [k for k, v in self.manual_control.items() if v]
