"""Cover service-call layer for AdaptiveDataUpdateCoordinator.

Extracted so the service-call surface (set_position, position/time-delta guards,
wait_for_target bookkeeping) is independently testable. The coordinator passes
in `is_adaptive_time` and `is_cover_manual` so this layer holds no coordinator
state beyond its own dicts and a few thresholds.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

from ..const import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CONF_DEFAULT_HEIGHT,
    CONF_SUNSET_POS,
)
from ..helpers import get_last_updated, state_attr

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Position tolerance when acknowledging a target: many cover motors stop a
# percent off the requested value, which must still count as "reached".
TARGET_TOLERANCE = 1
# Safety net: a wait that was never acknowledged expires after this long, so a
# cover that stalls mid-travel cannot suppress manual-override detection forever.
TARGET_WAIT_TIMEOUT = dt.timedelta(minutes=2)


class CoverServiceCaller:
    """Issue cover service calls and track target/throttle state."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Any,
        cover_type: str,
    ) -> None:
        """Initialize the service caller."""
        self.hass = hass
        self.logger = logger
        self._cover_type = cover_type
        self.wait_for_target: dict[str, bool] = {}
        self.target_call: dict[str, int] = {}
        self._target_set_at: dict[str, dt.datetime] = {}
        self.min_change: int = 1
        self.time_threshold: int = 2

    def configure(self, *, min_change: int, time_threshold: int) -> None:
        """Update throttling thresholds from current options."""
        self.min_change = min_change
        self.time_threshold = time_threshold

    @property
    def cover_type(self) -> str:
        """Current cover type (cover_blind / cover_awning / cover_tilt)."""
        return self._cover_type

    async def handle_call_service(
        self,
        entity: str,
        state: int,
        options: dict[str, Any],
        *,
        is_adaptive_time: bool,
        is_cover_manual: Callable[[str], bool],
    ) -> None:
        """Apply guards and call set_position if all pass."""
        if (
            is_adaptive_time
            and self.check_position_delta(entity, state, options)
            and self.check_time_delta(entity)
            and not is_cover_manual(entity)
        ):
            await self.set_position(entity, state)

    async def set_position(self, entity: str, state: int) -> None:
        """Set cover position."""
        await self.set_manual_position(entity, state)

    async def set_manual_position(self, entity: str, state: int) -> None:
        """Call the cover service to move `entity` to `state`."""
        if not self.check_position(entity, state):
            return

        service = SERVICE_SET_COVER_POSITION
        service_data: dict[str, Any] = {ATTR_ENTITY_ID: entity}

        if self._cover_type == "cover_tilt":
            service = SERVICE_SET_COVER_TILT_POSITION
            service_data[ATTR_TILT_POSITION] = state
        else:
            service_data[ATTR_POSITION] = state

        self.wait_for_target[entity] = True
        self.target_call[entity] = state
        self._target_set_at[entity] = dt.datetime.now(dt.UTC)
        self.logger.debug(
            "Set wait for target %s and target call %s",
            self.wait_for_target,
            self.target_call,
        )
        self.logger.debug("Run %s with data %s", service, service_data)
        try:
            await self.hass.services.async_call(
                COVER_DOMAIN, service, service_data, blocking=False
            )
        except (HomeAssistantError, ServiceNotFound, ValueError) as err:
            self.wait_for_target[entity] = False
            self.logger.error("Failed to set position for %s: %s", entity, err)
            raise HomeAssistantError(
                f"Failed to set cover position for {entity}: {err}"
            ) from err

    def acknowledge_target(self, entity: str, position: int | None) -> bool:
        """Mark target reached if `position` is within tolerance. Returns True when reached."""
        target = self.target_call.get(entity)
        if position is None or target is None:
            return False
        if abs(position - target) > TARGET_TOLERANCE:
            return False
        self.wait_for_target[entity] = False
        return True

    def is_waiting(self, entity: str) -> bool:
        """Return True while a recent set_position call is awaiting its target."""
        if not self.wait_for_target.get(entity):
            return False
        set_at = self._target_set_at.get(entity)
        if set_at is None or dt.datetime.now(dt.UTC) - set_at > TARGET_WAIT_TIMEOUT:
            self.wait_for_target[entity] = False
            self.logger.debug(
                "Target wait for %s expired without acknowledgement", entity
            )
            return False
        return True

    def _get_current_position(self, entity: str) -> int | None:
        """Get current position of cover (or tilt position for tilt covers)."""
        if self._cover_type == "cover_tilt":
            return state_attr(self.hass, entity, "current_tilt_position")
        return state_attr(self.hass, entity, "current_position")

    def check_position(self, entity: str, state: int) -> bool:
        """Return True iff cover's current position differs from desired state."""
        position = self._get_current_position(entity)
        if position is not None:
            return position != state
        self.logger.debug(
            "Cannot check position for %s: current position is unavailable", entity
        )
        return False

    def check_position_delta(
        self, entity: str, state: int, options: dict[str, Any]
    ) -> bool:
        """Return True iff the desired state moves the cover beyond min_change."""
        position = self._get_current_position(entity)
        if position is None:
            return True
        condition = abs(position - state) >= self.min_change
        self.logger.debug(
            "Entity: %s,  position: %s, state: %s, delta position: %s, min_change: %s, condition: %s",
            entity,
            position,
            state,
            abs(position - state),
            self.min_change,
            condition,
        )
        if state in [
            options.get(CONF_SUNSET_POS),
            options.get(CONF_DEFAULT_HEIGHT),
            0,
            100,
        ]:
            condition = True
        return condition

    def check_time_delta(self, entity: str) -> bool:
        """Return True iff enough time has passed since the last update."""
        now = dt.datetime.now(dt.UTC)
        last_updated = get_last_updated(entity, self.hass)
        if last_updated is None:
            return True
        condition = now - last_updated >= dt.timedelta(minutes=self.time_threshold)
        self.logger.debug(
            "Entity: %s, time delta: %s, threshold: %s, condition: %s",
            entity,
            now - last_updated,
            self.time_threshold,
            condition,
        )
        return condition
