"""Fetch sun data."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_location


class SunData:
    """Access local sun data."""

    def __init__(self, timezone: str, hass: HomeAssistant) -> None:
        """Initialize SunData."""
        self.hass = hass
        location, elevation = get_astral_location(self.hass)
        self.location = location  # astral.location.Location
        self.elevation = elevation
        self.timezone = timezone

    @property
    def times(self) -> pd.DatetimeIndex:
        """Time interval, every 5 min for the next 24h."""
        start_date = date.today()
        end_date = start_date + timedelta(days=1)
        return pd.date_range(
            start=start_date,
            end=end_date,
            freq="5min",
            tz=self.timezone,
            name="time",
        )

    @property
    def solar_azimuth(self) -> list[float]:
        """Solar azimuth at every step in `times`."""
        return [
            self.location.solar_azimuth(t, self.elevation) for t in self.times
        ]

    @property
    def solar_elevation(self) -> list[float]:
        """Solar elevation at every step in `times`."""
        return [
            self.location.solar_elevation(t, self.elevation) for t in self.times
        ]

    def sunset(self) -> datetime:
        """Today's sunset time (UTC)."""
        return self.location.sunset(date.today(), local=False)

    def sunrise(self) -> datetime:
        """Today's sunrise time (UTC)."""
        return self.location.sunrise(date.today(), local=False)
