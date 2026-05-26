"""Cover-type dispatch and adaptive cover factory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ..const import (
    CONF_AWNING_ANGLE,
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_BLIND_SPOT_LEFT,
    CONF_BLIND_SPOT_RIGHT,
    CONF_DEFAULT_HEIGHT,
    CONF_DISTANCE,
    CONF_ENABLE_BLIND_SPOT,
    CONF_ENABLE_MAX_POSITION,
    CONF_ENABLE_MIN_POSITION,
    CONF_FOV_LEFT,
    CONF_FOV_RIGHT,
    CONF_HEIGHT_WIN,
    CONF_LENGTH_AWNING,
    CONF_MAX_ELEVATION,
    CONF_MAX_POSITION,
    CONF_MIN_ELEVATION,
    CONF_MIN_POSITION,
    CONF_OBSTACLE_DISTANCE,
    CONF_OBSTACLE_HEIGHT,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TILT_DEPTH,
    CONF_TILT_DISTANCE,
    CONF_TILT_MODE,
)
from ..calculation import (
    AdaptiveHorizontalCover,
    AdaptiveTiltCover,
    AdaptiveVerticalCover,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

COVER_TYPES: frozenset[str] = frozenset(
    {"cover_blind", "cover_awning", "cover_tilt"}
)

COVER_TYPE_LABELS: dict[str, str] = {
    "cover_blind": "Vertical",
    "cover_awning": "Horizontal",
    "cover_tilt": "Tilt",
}


def build_cover(
    cover_type: str,
    options: Mapping[str, Any],
    pos_sun: tuple[float, float] | list[float],
    hass: HomeAssistant,
    logger: Any,
):
    """Return the adaptive cover instance that matches `cover_type`.

    Raises ValueError when `cover_type` is unknown — the config flow validates
    this, so reaching the raise indicates a corrupt config entry.
    """
    sol_azi, sol_elev = pos_sun
    common_kwargs: dict[str, Any] = {
        "hass": hass,
        "logger": logger,
        "sol_azi": sol_azi,
        "sol_elev": sol_elev,
        "sunset_pos": options.get(CONF_SUNSET_POS),
        "sunset_off": options.get(CONF_SUNSET_OFFSET),
        "sunrise_off": options.get(
            CONF_SUNRISE_OFFSET, options.get(CONF_SUNSET_OFFSET)
        ),
        "timezone": hass.config.time_zone,
        "fov_left": options.get(CONF_FOV_LEFT),
        "fov_right": options.get(CONF_FOV_RIGHT),
        "win_azi": options.get(CONF_AZIMUTH),
        "h_def": options.get(CONF_DEFAULT_HEIGHT),
        "max_pos": options.get(CONF_MAX_POSITION),
        "min_pos": options.get(CONF_MIN_POSITION),
        "max_pos_bool": options.get(CONF_ENABLE_MAX_POSITION, False),
        "min_pos_bool": options.get(CONF_ENABLE_MIN_POSITION, False),
        "blind_spot_left": options.get(CONF_BLIND_SPOT_LEFT),
        "blind_spot_right": options.get(CONF_BLIND_SPOT_RIGHT),
        "blind_spot_elevation": options.get(CONF_BLIND_SPOT_ELEVATION),
        "blind_spot_on": options.get(CONF_ENABLE_BLIND_SPOT, False),
        "min_elevation": options.get(CONF_MIN_ELEVATION),
        "max_elevation": options.get(CONF_MAX_ELEVATION),
    }
    vertical_kwargs: dict[str, Any] = {
        "distance": options.get(CONF_DISTANCE),
        "h_win": options.get(CONF_HEIGHT_WIN),
        "obstacle_height": options.get(CONF_OBSTACLE_HEIGHT, 0),
        "obstacle_distance": options.get(CONF_OBSTACLE_DISTANCE, 0),
    }
    if cover_type == "cover_blind":
        return AdaptiveVerticalCover(**common_kwargs, **vertical_kwargs)
    if cover_type == "cover_awning":
        return AdaptiveHorizontalCover(
            **common_kwargs,
            **vertical_kwargs,
            awn_length=options.get(CONF_LENGTH_AWNING),
            awn_angle=options.get(CONF_AWNING_ANGLE),
        )
    if cover_type == "cover_tilt":
        return AdaptiveTiltCover(
            **common_kwargs,
            slat_distance=options.get(CONF_TILT_DISTANCE),
            depth=options.get(CONF_TILT_DEPTH),
            mode=options.get(CONF_TILT_MODE),
        )
    raise ValueError(
        f"Unknown cover type: {cover_type!r}. Expected one of {COVER_TYPES}"
    )
