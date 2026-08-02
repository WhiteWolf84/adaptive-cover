"""Fetch sun data."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import cached_property

import astral.sun as astral_sun
from astral import Observer
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun as sun_helper
from homeassistant.util import dt as dt_util

# 5-minute grid spanning a full day. 24h / 5min = 288 intervals; the closing
# midnight boundary is kept to stay inclusive, matching the previous
# ``pandas.date_range(..., freq="5min")`` behaviour (289 points).
_STEP = timedelta(minutes=5)
_STEPS = int(timedelta(days=1) / _STEP) + 1


def get_observer(hass: HomeAssistant) -> Observer:
    """Return an astral Observer for the Home Assistant location.

    ``get_astral_observer`` is the supported helper; ``get_astral_location`` is
    deprecated and disappears in HA Core 2027.7. The new helper is not present on
    every release this integration supports, so fall back to assembling the
    Observer from the deprecated helper's return value -- which is exactly what
    the new helper does internally. The fallback is only *called* when the new
    name is missing, so no deprecation warning is logged on modern cores.
    """
    if (
        get_astral_observer := getattr(sun_helper, "get_astral_observer", None)
    ) is not None:
        return get_astral_observer(hass)
    location, elevation = sun_helper.get_astral_location(hass)
    return Observer(location.latitude, location.longitude, elevation)


class SunData:
    """Access local sun data."""

    def __init__(self, timezone: str, hass: HomeAssistant) -> None:
        """Initialize SunData."""
        self.hass = hass
        self.observer = get_observer(hass)
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
        day, which would shift the whole grid -- and the sunrise/sunset used by
        ``sunset_valid`` -- by a full day.
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
        return [astral_sun.azimuth(self.observer, t) for t in self.times]

    @cached_property
    def solar_elevation(self) -> list[float]:
        """Solar elevation at every step in `times`."""
        return [astral_sun.elevation(self.observer, t) for t in self.times]

    def sunset(self) -> datetime:
        """Today's sunset time (UTC, timezone-aware)."""
        return astral_sun.sunset(self.observer, self._today)

    def sunrise(self) -> datetime:
        """Today's sunrise time (UTC, timezone-aware)."""
        return astral_sun.sunrise(self.observer, self._today)
