"""The Coordinator for Adaptive Cover."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

from ..config_context_adapter import ConfigContextAdapter
from ..calculation import ClimateCoverData, ClimateCoverState, NormalCoverState
from ..const import (
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_CLIMATE_MODE,
    CONF_DEFAULT_HEIGHT,
    CONF_DELTA_POSITION,
    CONF_DELTA_TIME,
    CONF_END_ENTITY,
    CONF_END_TIME,
    CONF_ENTITIES,
    CONF_FOV_LEFT,
    CONF_FOV_RIGHT,
    CONF_INTERP,
    CONF_INTERP_END,
    CONF_INTERP_LIST,
    CONF_INTERP_LIST_NEW,
    CONF_INTERP_START,
    CONF_INVERSE_STATE,
    CONF_IRRADIANCE_ENTITY,
    CONF_IRRADIANCE_THRESHOLD,
    CONF_LUX_ENTITY,
    CONF_LUX_THRESHOLD,
    CONF_MANUAL_IGNORE_INTERMEDIATE,
    CONF_MANUAL_OVERRIDE_DURATION,
    CONF_MANUAL_OVERRIDE_RESET,
    CONF_MANUAL_THRESHOLD,
    CONF_OUTSIDE_THRESHOLD,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RETURN_SUNSET,
    CONF_START_ENTITY,
    CONF_START_TIME,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TEMP_ENTITY,
    CONF_TEMP_HIGH,
    CONF_TEMP_LOW,
    CONF_TRANSPARENT_BLIND,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_STATE,
    DOMAIN,
)
from ..helpers import get_datetime_from_str, get_safe_state, state_attr
from .blinds import COVER_TYPE_LABELS, COVER_TYPES, build_cover
from .manager import AdaptiveCoverManager
from .service import CoverServiceCaller

_LOGGER = logging.getLogger(__name__)

# ``async_track_point_in_time`` fires "at or after" the requested instant, so a
# busy event loop delivers the callback late. Anything within this window of the
# instant we scheduled still counts as that firing.
_TIMED_REFRESH_TOLERANCE = dt.timedelta(seconds=1)

__all__ = [
    "AdaptiveCoverData",
    "AdaptiveCoverManager",
    "AdaptiveDataUpdateCoordinator",
    "COVER_TYPES",
    "COVER_TYPE_LABELS",
    "CoverServiceCaller",
    "StateChangedData",
]


@dataclass(slots=True)
class StateChangedData:
    """StateChangedData class."""

    entity_id: str
    old_state: State | None
    new_state: State | None


@dataclass(slots=True)
class AdaptiveCoverData:
    """AdaptiveCoverData class."""

    climate_mode_toggle: bool
    states: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)


def inverse_state(state: int) -> int:
    """Inverse state."""
    return 100 - state


class AdaptiveDataUpdateCoordinator(DataUpdateCoordinator[AdaptiveCoverData]):
    """Adaptive cover data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator.

        Pass `config_entry` explicitly: HA 2024.10+ requires this; relying on the
        descriptor fallback emits a deprecation warning starting from 2025.x.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )

        self.logger = ConfigContextAdapter(_LOGGER)
        self.logger.set_config_name(self.config_entry.data.get("name"))
        self._cover_type = self.config_entry.data.get("sensor_type")
        self._climate_mode = self.config_entry.options.get(CONF_CLIMATE_MODE, False)
        self._switch_mode = bool(self._climate_mode)
        self._inverse_state = self.config_entry.options.get(CONF_INVERSE_STATE, False)
        self._use_interpolation = self.config_entry.options.get(CONF_INTERP, False)
        self._track_end_time = self.config_entry.options.get(CONF_RETURN_SUNSET)
        self._temp_toggle = None
        self._control_toggle = None
        self._manual_toggle = None
        self._lux_toggle = None
        self._irradiance_toggle = None
        self._start_time = None
        self._sun_end_time = None
        self._sun_start_time = None
        self._solar_times_date = None
        self.manual_reset = self.config_entry.options.get(
            CONF_MANUAL_OVERRIDE_RESET, False
        )
        self.manual_duration = self.config_entry.options.get(
            CONF_MANUAL_OVERRIDE_DURATION, {"minutes": 15}
        )
        self.state_change = False
        self.cover_state_change = False
        self.first_refresh = False
        self.timed_refresh = False
        self.climate_state = None
        # Populated by _async_update_data. Declared here so a failed first
        # refresh (e.g. sun.sun unavailable -> UpdateFailed) cannot leave the
        # switch/button platforms hitting AttributeError on coordinator.state.
        self.default_state: int = 0
        self.normal_cover_state: NormalCoverState | None = None
        self._start_after_end_logged = False
        self.control_method = "intermediate"
        self.state_change_data: StateChangedData | None = None
        self.manager = AdaptiveCoverManager(self.manual_duration, self.logger)
        self.service = CoverServiceCaller(self.hass, self.logger, self._cover_type)
        self.ignore_intermediate_states = self.config_entry.options.get(
            CONF_MANUAL_IGNORE_INTERMEDIATE, False
        )
        self._update_listener = None
        self._scheduled_time: dt.datetime | None = None
        # Silver: log-when-unavailable — traccia disponibilita' sun.sun
        self._sun_available: bool = True

    async def async_config_entry_first_refresh(self) -> None:
        """Config entry first refresh."""
        self.first_refresh = True
        await super().async_config_entry_first_refresh()
        self.logger.info("Config entry first refresh completed")

    async def async_timed_refresh(self, event) -> None:
        """Control state at end time.

        Compares against the instant we actually scheduled rather than
        re-reading and re-parsing the end-time option: the option may have been
        edited since, and the previous +-1s window against a freshly parsed
        value silently dropped any firing the event loop delivered late, so the
        end-of-day position was simply never applied.
        """
        scheduled = self._scheduled_time
        if scheduled is None:
            self.logger.debug("Timed refresh skipped: nothing scheduled")
            return

        drift = dt_util.now() - scheduled
        if drift < -_TIMED_REFRESH_TOLERANCE:
            self.logger.debug("Timed refresh fired %s early; ignoring", -drift)
            return

        self.timed_refresh = True
        self.logger.debug("Timed refresh triggered (drift %s)", drift)
        await self.async_refresh()

    async def async_check_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        self.logger.debug("Entity state change")
        self.state_change = True
        await self.async_refresh()

    async def async_check_cover_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        self.logger.debug("Cover state change")
        data = event.data
        if data["old_state"] is None:
            self.logger.debug("Old state is None")
            return
        if data["new_state"] is None:
            # Fired when the entity is removed from the state machine. Every
            # consumer below dereferences new_state (.state, .attributes,
            # .last_updated), so there is nothing to process.
            self.logger.debug("New state is None (entity removed); not processing")
            return
        self.state_change_data = StateChangedData(
            data["entity_id"], data["old_state"], data["new_state"]
        )
        if self.state_change_data.old_state.state != "unknown":
            self.process_entity_state_change()
            if self.service.is_waiting(self.state_change_data.entity_id):
                # Cover is still travelling towards a position we commanded;
                # manual-override detection is suppressed while waiting, so a
                # full refresh would be a no-op until the target is reached.
                self.logger.debug(
                    "Skipping refresh while waiting for target on %s",
                    self.state_change_data.entity_id,
                )
                return
            self.cover_state_change = True
            await self.async_refresh()
        else:
            self.logger.debug("Old state is unknown, not processing")

    def process_entity_state_change(self) -> None:
        """Process state change event."""
        event = self.state_change_data
        self.logger.debug("Processing state change event: %s", event)
        entity_id = event.entity_id
        if self.ignore_intermediate_states and event.new_state.state in [
            "opening",
            "closing",
        ]:
            self.logger.debug("Ignoring intermediate state change for %s", entity_id)
            return
        if self.service.is_waiting(entity_id):
            position = event.new_state.attributes.get(
                "current_position"
                if self._cover_type != "cover_tilt"
                else "current_tilt_position"
            )
            if self.service.acknowledge_target(entity_id, position):
                self.logger.debug("Position %s reached for %s", position, entity_id)
            self.logger.debug("Wait for target: %s", self.service.wait_for_target)
        else:
            self.logger.debug("No wait for target call for %s", entity_id)

    @callback
    def _async_cancel_update_listener(self) -> None:
        """Cancel the scheduled update."""
        if self._update_listener:
            self._update_listener()
            self._update_listener = None

    async def async_timed_end_time(self, end_time: dt.datetime) -> None:
        """Schedule the end-of-window refresh at `end_time`.

        Takes the already-resolved instant instead of re-reading the ``_end_time``
        property: each read parses a datetime string, and the previous version
        read it five times per call.
        """
        self._async_cancel_update_listener()
        self.logger.debug(
            "Scheduling end time update at %s (previously scheduled: %s)",
            end_time,
            self._scheduled_time,
        )
        self._update_listener = async_track_point_in_time(
            self.hass, self.async_timed_refresh, end_time
        )
        self._scheduled_time = end_time

    async def _async_update_data(self) -> AdaptiveCoverData:
        self.logger.debug("Updating data")
        options = self.config_entry.options
        self._update_options(options)

        sun_position = self.pos_sun
        if None in sun_position:
            raise UpdateFailed(
                "Sun entity (sun.sun) is unavailable; cannot calculate cover position"
            )

        cover_data = build_cover(
            self._cover_type, options, sun_position, self.hass, self.logger
        )
        self._update_manager_and_covers()

        if self._climate_mode:
            self.climate_mode_data(options, cover_data)
        else:
            self.logger.debug("Control method is %s", self.control_method)

        self.normal_cover_state = NormalCoverState(cover_data)
        self.logger.debug(
            "Determined normal cover state to be %s", self.normal_cover_state
        )

        self.default_state = round(self.normal_cover_state.get_state())
        self.logger.debug("Determined default state to be %s", self.default_state)
        state = self.state

        await self.manager.reset_if_needed()

        end_time = self._resolve_end_time()
        if (
            end_time
            and self._track_end_time
            and (self._scheduled_time is None or end_time > self._scheduled_time)
        ):
            await self.async_timed_end_time(end_time)

        was_first_refresh = self.first_refresh
        if self.state_change:
            await self.async_handle_state_change(state, options)
        if self.cover_state_change:
            await self.async_handle_cover_state_change(state)
        if self.first_refresh:
            await self.async_handle_first_refresh(state, options)
        if self.timed_refresh:
            await self.async_handle_timed_refresh(options)

        normal_cover = self.normal_cover_state.cover
        # Cache solar_times() for the whole local day. Keying on a stored local
        # date (rather than on ``_sun_start_time`` itself) avoids two per-tick
        # recomputations: when solar_times() returns None (sun never enters the
        # window, e.g. a north-facing cover) and during the pre-dawn hours when
        # now(UTC).date() and a UTC sunrise date disagree.
        current_date = dt_util.now().date()
        if was_first_refresh or self._solar_times_date != current_date:
            self.logger.debug("Calculating solar times")
            loop = asyncio.get_running_loop()
            start, end = await loop.run_in_executor(None, normal_cover.solar_times)
            self._sun_start_time = start
            self._sun_end_time = end
            self._solar_times_date = current_date
            self.logger.debug("Sun start time: %s, Sun end time: %s", start, end)
        else:
            start, end = self._sun_start_time, self._sun_end_time

        return AdaptiveCoverData(
            climate_mode_toggle=self.switch_mode,
            states={
                "state": state,
                "start": start,
                "end": end,
                "control": self.control_method,
                "sun_motion": normal_cover.valid,
                "manual_override": self.manager.binary_cover_manual,
                "manual_list": self.manager.manual_controlled,
            },
            attributes={
                "default": options.get(CONF_DEFAULT_HEIGHT),
                "sunset_default": options.get(CONF_SUNSET_POS),
                "sunset_offset": options.get(CONF_SUNSET_OFFSET),
                "azimuth_window": options.get(CONF_AZIMUTH),
                "field_of_view": [
                    options.get(CONF_FOV_LEFT),
                    options.get(CONF_FOV_RIGHT),
                ],
                "blind_spot": options.get(CONF_BLIND_SPOT_ELEVATION),
            },
        )

    async def async_handle_state_change(self, state: int, options) -> None:
        """Handle state change from tracked entities."""
        if self.control_toggle:
            for cover in self.entities:
                await self.service.handle_call_service(
                    cover,
                    state,
                    options,
                    is_adaptive_time=self.check_adaptive_time,
                    is_cover_manual=self.manager.is_cover_manual,
                )
        else:
            self.logger.debug("State change but control toggle is off")
        self.state_change = False
        self.logger.debug("State change handled")

    async def async_handle_cover_state_change(self, state: int) -> None:
        """Handle state change from assigned covers."""
        if self.manual_toggle and self.control_toggle:
            self.manager.handle_state_change(
                self.state_change_data,
                state,
                self._cover_type,
                self.manual_reset,
                self.service.is_waiting,
                self.manual_threshold,
            )
        self.cover_state_change = False
        self.logger.debug("Cover state change handled")

    async def async_handle_first_refresh(self, state: int, options) -> None:
        """Handle first refresh."""
        if self.control_toggle:
            # Hoisted out of the loop: it is constant for the tick and each read
            # parses two datetime strings.
            is_adaptive_time = self.check_adaptive_time
            for cover in self.entities:
                if (
                    is_adaptive_time
                    and not self.manager.is_cover_manual(cover)
                    and self.service.check_position_delta(cover, state, options)
                ):
                    await self.service.set_position(cover, state)
        else:
            self.logger.debug("First refresh but control toggle is off")
        self.first_refresh = False
        self.logger.debug("First refresh handled")

    async def async_handle_timed_refresh(self, options) -> None:
        """Handle timed refresh."""
        self.logger.debug(
            "This is a timed refresh, using sunset position: %s",
            options.get(CONF_SUNSET_POS),
        )
        if self.control_toggle:
            for cover in self.entities:
                await self.service.set_manual_position(
                    cover,
                    (
                        inverse_state(options.get(CONF_SUNSET_POS))
                        if self._inverse_state
                        else options.get(CONF_SUNSET_POS)
                    ),
                )
        else:
            self.logger.debug("Timed refresh but control toggle is off")
        self.timed_refresh = False
        self.logger.debug("Timed refresh handled")

    def _update_options(self, options) -> None:
        """Update options."""
        self.entities = options.get(CONF_ENTITIES, [])
        self.min_change = options.get(CONF_DELTA_POSITION, 1)
        self.time_threshold = options.get(CONF_DELTA_TIME, 2)
        self.start_time = options.get(CONF_START_TIME)
        self.start_time_entity = options.get(CONF_START_ENTITY)
        self.end_time = options.get(CONF_END_TIME)
        self.end_time_entity = options.get(CONF_END_ENTITY)
        self.manual_reset = options.get(CONF_MANUAL_OVERRIDE_RESET, False)
        self.manual_duration = options.get(
            CONF_MANUAL_OVERRIDE_DURATION, {"minutes": 15}
        )
        # Propagate to the manager: it captured the duration at construction, so
        # assigning only to self.manual_duration had no effect on the reset logic.
        self.manager.set_reset_duration(self.manual_duration)
        self.manual_threshold = options.get(CONF_MANUAL_THRESHOLD)
        self.start_value = options.get(CONF_INTERP_START)
        self.end_value = options.get(CONF_INTERP_END)
        self.normal_list = options.get(CONF_INTERP_LIST)
        self.new_list = options.get(CONF_INTERP_LIST_NEW)
        self.service.configure(
            min_change=self.min_change, time_threshold=self.time_threshold
        )

    def _update_manager_and_covers(self) -> None:
        self.manager.add_covers(self.entities)
        if not self._manual_toggle:
            for entity in self.manager.manual_controlled:
                self.manager.reset(entity)

    def _resolve_start_time(self) -> dt.datetime | None:
        """Resolve the configured start time, entity taking precedence."""
        if self.start_time_entity is not None:
            return get_datetime_from_str(
                get_safe_state(self.hass, self.start_time_entity)
            )
        if self.start_time is not None:
            return get_datetime_from_str(self.start_time)
        return None

    def _resolve_end_time(self) -> dt.datetime | None:
        """Resolve the configured end time, entity taking precedence."""
        if self.end_time_entity is not None:
            return get_datetime_from_str(
                get_safe_state(self.hass, self.end_time_entity)
            )
        if self.end_time is not None:
            end = get_datetime_from_str(self.end_time)
            if end is not None and end.time() == dt.time(0, 0):
                # "00:00" means the end of today, not its start.
                end += dt.timedelta(days=1)
            return end
        return None

    @property
    def check_adaptive_time(self) -> bool:
        """Check if time is within start and end times.

        Resolves both bounds once. The previous version read the ``_end_time``
        property four times and relied on ``after_start_time`` to populate
        ``_start_time`` as a side effect — but compared ``_start_time`` *before*
        that ran, so the start-after-end guard saw the previous tick's value (or
        None on the first tick, skipping the check entirely).
        """
        start = self._resolve_start_time()
        end = self._resolve_end_time()
        self._start_time = start

        if start is not None and end is not None and start > end:
            if not self._start_after_end_logged:
                self.logger.warning(
                    "Start time (%s) is after end time (%s); "
                    "adaptive control is disabled until this is corrected",
                    start,
                    end,
                )
                self._start_after_end_logged = True
            return False
        self._start_after_end_logged = False

        now = dt_util.now()
        within = (end is None or now < end) and (start is None or now >= start)
        self.logger.debug(
            "Adaptive window: start=%s, end=%s, now=%s, within=%s",
            start,
            end,
            now,
            within,
        )
        return within

    @property
    def after_start_time(self) -> bool:
        """Check if time is after start time."""
        start = self._resolve_start_time()
        self._start_time = start
        return start is None or dt_util.now() >= start

    @property
    def _end_time(self) -> dt.datetime | None:
        """Get end time."""
        return self._resolve_end_time()

    @property
    def before_end_time(self) -> bool:
        """Check if time is before end time."""
        end = self._resolve_end_time()
        return end is None or dt_util.now() < end

    @property
    def pos_sun(self) -> list[float | None]:
        """Fetch information for sun position."""
        azimuth = state_attr(self.hass, "sun.sun", "azimuth")
        elevation = state_attr(self.hass, "sun.sun", "elevation")
        # Silver: log-when-unavailable — logga UNA SOLA VOLTA quando sun.sun
        # diventa non disponibile, e UNA SOLA VOLTA quando torna disponibile.
        if azimuth is None or elevation is None:
            if self._sun_available:
                self.logger.warning(
                    "Sun entity (sun.sun) is unavailable; cover position calculation may be inaccurate"
                )
                self._sun_available = False
        elif not self._sun_available:
            self.logger.info("Sun entity (sun.sun) is back available")
            self._sun_available = True
        return [azimuth, elevation]

    def climate_mode_data(self, options, cover_data) -> None:
        """Update climate mode data and control method."""
        climate = ClimateCoverData(
            hass=self.hass,
            logger=self.logger,
            temp_entity=options.get(CONF_TEMP_ENTITY),
            temp_low=options.get(CONF_TEMP_LOW),
            temp_high=options.get(CONF_TEMP_HIGH),
            presence_entity=options.get(CONF_PRESENCE_ENTITY),
            weather_entity=options.get(CONF_WEATHER_ENTITY),
            weather_condition=options.get(CONF_WEATHER_STATE),
            outside_entity=options.get(CONF_OUTSIDETEMP_ENTITY),
            temp_switch=self._temp_toggle,
            blind_type=self._cover_type,
            transparent_blind=options.get(CONF_TRANSPARENT_BLIND),
            lux_entity=options.get(CONF_LUX_ENTITY),
            irradiance_entity=options.get(CONF_IRRADIANCE_ENTITY),
            lux_threshold=options.get(CONF_LUX_THRESHOLD),
            irradiance_threshold=options.get(CONF_IRRADIANCE_THRESHOLD),
            temp_summer_outside=options.get(CONF_OUTSIDE_THRESHOLD),
            _use_lux=self._lux_toggle,
            _use_irradiance=self._irradiance_toggle,
        )
        climate_cover_state = ClimateCoverState(cover_data, climate)
        self.climate_state = round(climate_cover_state.get_state())
        climate_data = climate_cover_state.climate_data
        if climate_data.is_summer and self.switch_mode:
            self.control_method = "summer"
        if climate_data.is_winter and self.switch_mode:
            self.control_method = "winter"
        self.logger.debug(
            "Climate mode control method was set to %s", self.control_method
        )

    @property
    def state(self) -> int:
        """Handle the output of the state based on mode."""
        self.logger.debug(
            "Basic position: %s; Climate position: %s; Using climate position? %s",
            self.default_state,
            self.climate_state,
            self._switch_mode,
        )
        if self._switch_mode:
            state = self.climate_state
        else:
            state = self.default_state

        if self._use_interpolation:
            self.logger.debug("Interpolating position: %s", state)
            state = self.interpolate_states(state)

        if self._inverse_state and self._use_interpolation:
            self.logger.info(
                "Inverse state is not supported with interpolation, you can inverse the state by arranging the list from high to low"
            )

        if self._inverse_state and not self._use_interpolation:
            state = inverse_state(state)
            self.logger.debug("Inversed position: %s", state)

        self.logger.debug("Final position to use: %s", state)
        return state

    def interpolate_states(self, state):
        """Interpolate states."""
        normal_range = [0, 100]
        new_range = []
        # `is not None`, not truthiness: 0 is a valid endpoint (the selector
        # allows min=0) and a descending range such as 20 -> 0 is the documented
        # way to invert the state. Truthiness silently skipped both.
        if self.start_value is not None and self.end_value is not None:
            new_range = [self.start_value, self.end_value]
        if self.normal_list and self.new_list:
            normal_range = list(map(int, self.normal_list))
            new_range = list(map(int, self.new_list))
        if new_range:
            state = round(float(np.interp(state, normal_range, new_range)))
            # At the edges of the mapped range, send the real fully-closed/open
            # values to the cover; min/max (not [0]/[-1]) so a descending list
            # used to inverse the state keeps its endpoints intact.
            if state == min(new_range):
                state = 0
            elif state == max(new_range):
                state = 100
        return state

    @property
    def switch_mode(self) -> bool:
        """Let switch toggle climate mode."""
        return self._switch_mode

    @switch_mode.setter
    def switch_mode(self, value: bool) -> None:
        self._switch_mode = value

    @property
    def temp_toggle(self) -> bool | None:
        """Let switch toggle between inside or outside temperature."""
        return self._temp_toggle

    @temp_toggle.setter
    def temp_toggle(self, value: bool) -> None:
        self._temp_toggle = value

    @property
    def control_toggle(self) -> bool | None:
        """Toggle automation."""
        return self._control_toggle

    @control_toggle.setter
    def control_toggle(self, value: bool) -> None:
        self._control_toggle = value

    @property
    def manual_toggle(self) -> bool | None:
        """Toggle manual override detection."""
        return self._manual_toggle

    @manual_toggle.setter
    def manual_toggle(self, value: bool) -> None:
        self._manual_toggle = value

    @property
    def lux_toggle(self) -> bool | None:
        """Toggle lux."""
        return self._lux_toggle

    @lux_toggle.setter
    def lux_toggle(self, value: bool) -> None:
        self._lux_toggle = value

    @property
    def irradiance_toggle(self) -> bool | None:
        """Toggle irradiance."""
        return self._irradiance_toggle

    @irradiance_toggle.setter
    def irradiance_toggle(self, value: bool) -> None:
        self._irradiance_toggle = value
