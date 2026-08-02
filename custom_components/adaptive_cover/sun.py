"""Fetch sun data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import cached_property

from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_location
from homeassistant.util import dt as dt_util

# 5-minute grid spanning a full day. 24h / 5min = 288 intervals; the closing
# midnight boundary is kept to stay inclusive, matching the previous
# ``pandas.date_range(..., freq="5min")`` behaviour (289 points).
_STEP = timedelta(minutes=5)
_STEPS = int(timedelta(days=1) / _STEP) + 1


class SunData:
    """Access local sun data."""

    def __init__(self, timezone: str, hass: HomeAssistant) -> None:
        """Initialize SunData."""
        self.hass = hass
        location, elevation = get_astral_location(self.hass)
        self.location = location  # astral.location.Location
        self.elevation = elevation
        self.timezone = timezone

    @cached_property
    def _tzinfo(self):
        """Resolved tzinfo for the configured timezone."""
        return dt_util.get_time_zone(self.timezone)

    @cached_property
    def _today(self) -> date:
        """Today's date in the *configured* timezone.

        Deliberately not ``date.today()``: that reads the host clock, which is
        not the Home Assistant timezone (HA never calls ``time.tzset()``). With a
        UTC container and a local HA timezone the two disagree for part of every
        day, which would shift the whole grid — and the sunrise/sunset used by
        ``sunset_valid`` — by a full day.
        """
        return dt_util.utcnow().astimezone(self._tzinfo).date()

    @cached_property
    def times(self) -> list[datetime]:
        """Timezone-aware grid, every 5 min over the next 24h.

        Cached for the lifetime of the instance: a fresh ``SunData`` is built on
        every coordinator tick, so the grid is computed at most once per update.
        """
        start = datetime.combine(self._today, time(), tzinfo=self._tzinfo)
        return [start + _STEP * step for step in range(_STEPS)]

    @cached_property
    def solar_azimuth(self) -> list[float]:
        """Solar azimuth at every step in `times`."""
        return [self.location.solar_azimuth(t, self.elevation) for t in self.times]

    @cached_property
    def solar_elevation(self) -> list[float]:
        """Solar elevation at every step in `times`."""
        return [self.location.solar_elevation(t, self.elevation) for t in self.times]

    def sunset(self) -> datetime:
        """Today's sunset time (UTC, timezone-aware)."""
        return self.location.sunset(self._today, local=False)

    def sunrise(self) -> datetime:
        """Today's sunrise time (UTC, timezone-aware)."""
        return self.location.sunrise(self._today, local=False)
