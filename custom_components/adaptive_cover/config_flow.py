"""Config flow for Adaptive Cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AWNING_ANGLE,
    CONF_AZIMUTH,
    CONF_BLIND_SPOT_ELEVATION,
    CONF_BLIND_SPOT_LEFT,
    CONF_BLIND_SPOT_RIGHT,
    CONF_CLIMATE_MODE,
    CONF_DEFAULT_HEIGHT,
    CONF_DELTA_POSITION,
    CONF_DELTA_TIME,
    CONF_DISTANCE,
    CONF_ENABLE_BLIND_SPOT,
    CONF_ENABLE_MAX_POSITION,
    CONF_ENABLE_MIN_POSITION,
    CONF_END_ENTITY,
    CONF_END_TIME,
    CONF_ENTITIES,
    CONF_FOV_LEFT,
    CONF_FOV_RIGHT,
    CONF_HEIGHT_WIN,
    CONF_INTERP,
    CONF_INTERP_END,
    CONF_INTERP_LIST,
    CONF_INTERP_LIST_NEW,
    CONF_INTERP_START,
    CONF_INVERSE_STATE,
    CONF_IRRADIANCE_ENTITY,
    CONF_IRRADIANCE_THRESHOLD,
    CONF_LENGTH_AWNING,
    CONF_LUX_ENTITY,
    CONF_LUX_THRESHOLD,
    CONF_MANUAL_IGNORE_INTERMEDIATE,
    CONF_MANUAL_OVERRIDE_DURATION,
    CONF_MANUAL_OVERRIDE_RESET,
    CONF_MANUAL_THRESHOLD,
    CONF_MAX_ELEVATION,
    CONF_MAX_POSITION,
    CONF_MIN_ELEVATION,
    CONF_MIN_POSITION,
    CONF_MODE,
    CONF_OUTSIDE_THRESHOLD,
    CONF_OUTSIDETEMP_ENTITY,
    CONF_PRESENCE_ENTITY,
    CONF_RETURN_SUNSET,
    CONF_SENSOR_TYPE,
    CONF_START_ENTITY,
    CONF_START_TIME,
    CONF_SUNRISE_OFFSET,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_POS,
    CONF_TEMP_ENTITY,
    CONF_TEMP_HIGH,
    CONF_TEMP_LOW,
    CONF_TILT_DEPTH,
    CONF_TILT_DISTANCE,
    CONF_TILT_MODE,
    CONF_TRANSPARENT_BLIND,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_STATE,
    DOMAIN,
    SensorType,
    _LOGGER,
)

SENSOR_TYPE_MENU = [SensorType.BLIND, SensorType.AWNING, SensorType.TILT]

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.TextSelector(),
        vol.Optional(CONF_MODE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SENSOR_TYPE_MENU, translation_key="mode"
            )
        ),
    }
)

CLIMATE_MODE = vol.Schema(
    {
        vol.Optional(CONF_CLIMATE_MODE, default=False): selector.BooleanSelector(),
    }
)

OPTIONS = vol.Schema(
    {
        vol.Required(CONF_AZIMUTH, default=180): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=359, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Required(CONF_DEFAULT_HEIGHT, default=60): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_MAX_POSITION): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_ENABLE_MAX_POSITION, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_MIN_POSITION): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=99, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_ENABLE_MIN_POSITION, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_MIN_ELEVATION): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=90, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Optional(CONF_MAX_ELEVATION): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=90, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Required(CONF_FOV_LEFT, default=90): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=90, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Required(CONF_FOV_RIGHT, default=90): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=90, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Required(CONF_SUNSET_POS, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Required(CONF_SUNSET_OFFSET, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(mode="box", unit_of_measurement="minutes")
        ),
        vol.Required(CONF_SUNRISE_OFFSET, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(mode="box", unit_of_measurement="minutes")
        ),
        vol.Required(CONF_INVERSE_STATE, default=False): selector.BooleanSelector(),
        vol.Required(CONF_ENABLE_BLIND_SPOT, default=False): selector.BooleanSelector(),
        vol.Required(CONF_INTERP, default=False): selector.BooleanSelector(),
    }
)

VERTICAL_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_ENTITIES, default=[]): selector.EntitySelector(
            selector.EntitySelectorConfig(
                multiple=True,
                filter=selector.EntityFilterSelectorConfig(
                    domain="cover",
                    supported_features=["cover.CoverEntityFeature.SET_POSITION"],
                ),
            )
        ),
        vol.Required(CONF_HEIGHT_WIN, default=2.1): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1, max=6, step=0.01, mode="slider", unit_of_measurement="m"
            )
        ),
        vol.Required(CONF_DISTANCE, default=0.5): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1, max=2, step=0.1, mode="slider", unit_of_measurement="m"
            )
        ),
    }
).extend(OPTIONS.schema)


HORIZONTAL_OPTIONS = vol.Schema(
    {
        vol.Required(CONF_LENGTH_AWNING, default=2.1): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.3, max=6, step=0.01, mode="slider", unit_of_measurement="m"
            )
        ),
        vol.Required(CONF_AWNING_ANGLE, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=45, mode="slider", unit_of_measurement="°"
            )
        ),
    }
).extend(VERTICAL_OPTIONS.schema)

TILT_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_ENTITIES, default=[]): selector.EntitySelector(
            selector.EntitySelectorConfig(
                multiple=True,
                filter=selector.EntityFilterSelectorConfig(
                    domain="cover",
                    supported_features=["cover.CoverEntityFeature.SET_TILT_POSITION"],
                ),
            )
        ),
        vol.Required(CONF_TILT_DEPTH, default=3): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1, max=15, step=0.1, mode="slider", unit_of_measurement="cm"
            )
        ),
        vol.Required(CONF_TILT_DISTANCE, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1, max=15, step=0.1, mode="slider", unit_of_measurement="cm"
            )
        ),
        vol.Required(CONF_TILT_MODE, default="mode2"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["mode1", "mode2"], translation_key="tilt_mode"
            )
        ),
    }
).extend(OPTIONS.schema)

CLIMATE_OPTIONS = vol.Schema(
    {
        vol.Required(CONF_TEMP_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(domain=["climate", "sensor"])
        ),
        vol.Required(CONF_TEMP_LOW, default=21): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=86, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Required(CONF_TEMP_HIGH, default=25): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=90, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Optional(CONF_OUTSIDETEMP_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(domain=["sensor"])
        ),
        vol.Optional(CONF_OUTSIDE_THRESHOLD, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode="slider", unit_of_measurement="°"
            )
        ),
        vol.Optional(CONF_PRESENCE_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(
                domain=["device_tracker", "zone", "binary_sensor", "input_boolean"]
            )
        ),
        vol.Optional(CONF_LUX_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(
                domain=["sensor"], device_class="illuminance"
            )
        ),
        vol.Optional(CONF_LUX_THRESHOLD, default=1000): selector.NumberSelector(
            selector.NumberSelectorConfig(mode="box", unit_of_measurement="lux")
        ),
        vol.Optional(CONF_IRRADIANCE_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(
                domain=["sensor"], device_class="irradiance"
            )
        ),
        vol.Optional(CONF_IRRADIANCE_THRESHOLD, default=300): selector.NumberSelector(
            selector.NumberSelectorConfig(mode="box", unit_of_measurement="W/m²")
        ),
        vol.Optional(CONF_TRANSPARENT_BLIND, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
            selector.EntityFilterSelectorConfig(domain="weather")
        ),
    }
)

WEATHER_OPTIONS = vol.Schema(
    {
        vol.Optional(
            CONF_WEATHER_STATE, default=["sunny", "partlycloudy", "cloudy", "clear"]
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True,
                sort=False,
                options=[
                    "clear-night",
                    "clear",
                    "cloudy",
                    "fog",
                    "hail",
                    "lightning",
                    "lightning-rainy",
                    "partlycloudy",
                    "pouring",
                    "rainy",
                    "snowy",
                    "snowy-rainy",
                    "sunny",
                    "windy",
                    "windy-variant",
                    "exceptional",
                ],
            )
        )
    }
)

AUTOMATION_CONFIG = vol.Schema(
    {
        vol.Required(CONF_DELTA_POSITION, default=1): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=90, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_DELTA_TIME, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=2, mode="box", unit_of_measurement="minutes"
            )
        ),
        vol.Optional(CONF_START_TIME, default="00:00:00"): selector.TimeSelector(),
        vol.Optional(CONF_START_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_datetime"])
        ),
        vol.Required(
            CONF_MANUAL_OVERRIDE_DURATION, default={"minutes": 15}
        ): selector.DurationSelector(),
        vol.Required(CONF_MANUAL_OVERRIDE_RESET, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_MANUAL_THRESHOLD): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=99, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_MANUAL_IGNORE_INTERMEDIATE, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_END_TIME, default="00:00:00"): selector.TimeSelector(),
        vol.Optional(CONF_END_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_datetime"])
        ),
        vol.Optional(CONF_RETURN_SUNSET, default=False): selector.BooleanSelector(),
    }
)

INTERPOLATION_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_INTERP_START): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_INTERP_END): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, mode="slider", unit_of_measurement="%"
            )
        ),
        vol.Optional(CONF_INTERP_LIST, default=[]): selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True, custom_value=True, options=["0", "50", "100"]
            )
        ),
        vol.Optional(CONF_INTERP_LIST_NEW, default=[]): selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True, custom_value=True, options=["0", "50", "100"]
            )
        ),
    }
)


def _get_azimuth_edges(data: dict[str, Any]) -> int:
    """Return total azimuth field of view in degrees."""
    return data[CONF_FOV_LEFT] + data[CONF_FOV_RIGHT]


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle ConfigFlow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.type_blind: str | None = None
        self.config: dict[str, Any] = {}
        self.mode: str = "basic"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        _LOGGER.debug("Starting user setup step with input: %s", user_input)
        if user_input:
            self.config = user_input
            if self.config[CONF_MODE] == SensorType.BLIND:
                return await self.async_step_vertical()
            if self.config[CONF_MODE] == SensorType.AWNING:
                return await self.async_step_horizontal()
            if self.config[CONF_MODE] == SensorType.TILT:
                return await self.async_step_tilt()
        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

    async def async_step_vertical(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for vertical blinds."""
        self.type_blind = SensorType.BLIND
        if user_input is not None:
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="vertical",
                        data_schema=CLIMATE_MODE.extend(VERTICAL_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.config.update(user_input)
            if self.config[CONF_INTERP]:
                return await self.async_step_interp()
            if self.config[CONF_ENABLE_BLIND_SPOT]:
                return await self.async_step_blind_spot()
            return await self.async_step_automation()
        return self.async_show_form(
            step_id="vertical",
            data_schema=CLIMATE_MODE.extend(VERTICAL_OPTIONS.schema),
        )

    async def async_step_horizontal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for horizontal blinds."""
        self.type_blind = SensorType.AWNING
        if user_input is not None:
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="horizontal",
                        data_schema=CLIMATE_MODE.extend(HORIZONTAL_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.config.update(user_input)
            if self.config[CONF_INTERP]:
                return await self.async_step_interp()
            if self.config[CONF_ENABLE_BLIND_SPOT]:
                return await self.async_step_blind_spot()
            return await self.async_step_automation()
        return self.async_show_form(
            step_id="horizontal",
            data_schema=CLIMATE_MODE.extend(HORIZONTAL_OPTIONS.schema),
        )

    async def async_step_tilt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for tilted blinds."""
        self.type_blind = SensorType.TILT
        if user_input is not None:
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="tilt",
                        data_schema=CLIMATE_MODE.extend(TILT_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.config.update(user_input)
            if self.config[CONF_INTERP]:
                return await self.async_step_interp()
            if self.config[CONF_ENABLE_BLIND_SPOT]:
                return await self.async_step_blind_spot()
            return await self.async_step_automation()
        return self.async_show_form(
            step_id="tilt", data_schema=CLIMATE_MODE.extend(TILT_OPTIONS.schema)
        )

    async def async_step_interp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show interpolation options."""
        if user_input is not None:
            if len(user_input[CONF_INTERP_LIST]) != len(user_input[CONF_INTERP_LIST_NEW]):
                return self.async_show_form(
                    step_id="interp",
                    data_schema=INTERPOLATION_OPTIONS,
                    errors={CONF_INTERP_LIST_NEW: "interp_list_length"},
                )
            self.config.update(user_input)
            if self.config[CONF_ENABLE_BLIND_SPOT]:
                return await self.async_step_blind_spot()
            return await self.async_step_automation()
        return self.async_show_form(step_id="interp", data_schema=INTERPOLATION_OPTIONS)

    async def async_step_blind_spot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add blindspot to data."""
        edges = _get_azimuth_edges(self.config)
        schema = vol.Schema(
            {
                vol.Required(CONF_BLIND_SPOT_LEFT, default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="slider", unit_of_measurement="°", min=0, max=edges - 1
                    )
                ),
                vol.Required(CONF_BLIND_SPOT_RIGHT, default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="slider", unit_of_measurement="°", min=1, max=edges
                    )
                ),
                vol.Optional(CONF_BLIND_SPOT_ELEVATION): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=90)
                ),
            }
        )
        if user_input is not None:
            if user_input[CONF_BLIND_SPOT_RIGHT] <= user_input[CONF_BLIND_SPOT_LEFT]:
                return self.async_show_form(
                    step_id="blind_spot",
                    data_schema=schema,
                    errors={CONF_BLIND_SPOT_RIGHT: "blind_spot_range"},
                )
            self.config.update(user_input)
            return await self.async_step_automation()
        return self.async_show_form(step_id="blind_spot", data_schema=schema)

    async def async_step_automation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage automation options."""
        if user_input is not None:
            self.config.update(user_input)
            if self.config[CONF_CLIMATE_MODE] is True:
                return await self.async_step_climate()
            return await self.async_step_update()
        return self.async_show_form(step_id="automation", data_schema=AUTOMATION_CONFIG)

    async def async_step_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage climate options."""
        if user_input is not None:
            self.config.update(user_input)
            if self.config.get(CONF_WEATHER_ENTITY):
                return await self.async_step_weather()
            return await self.async_step_update()
        return self.async_show_form(step_id="climate", data_schema=CLIMATE_OPTIONS)

    async def async_step_weather(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage weather conditions."""
        if user_input is not None:
            self.config.update(user_input)
            return await self.async_step_update()
        return self.async_show_form(step_id="weather", data_schema=WEATHER_OPTIONS)

    async def async_step_update(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create entry."""
        cover_type_labels = {
            "cover_blind": "Vertical",
            "cover_awning": "Horizontal",
            "cover_tilt": "Tilt",
        }
        
        _LOGGER.info(
            "Creating Adaptive Cover configuration entry for %s (%s)",
            self.config["name"],
            cover_type_labels[self.type_blind],
        )
        _LOGGER.debug("Configuration data initialized: %s", self.config)
        
        return self.async_create_entry(
            title=f"{cover_type_labels[self.type_blind]} {self.config['name']}",
            data={
                "name": self.config["name"],
                CONF_SENSOR_TYPE: self.type_blind,
            },
            options={
                CONF_MODE: self.mode,
                CONF_AZIMUTH: self.config.get(CONF_AZIMUTH),
                CONF_HEIGHT_WIN: self.config.get(CONF_HEIGHT_WIN),
                CONF_DISTANCE: self.config.get(CONF_DISTANCE),
                CONF_DEFAULT_HEIGHT: self.config.get(CONF_DEFAULT_HEIGHT),
                CONF_MAX_POSITION: self.config.get(CONF_MAX_POSITION),
                CONF_ENABLE_MAX_POSITION: self.config.get(CONF_ENABLE_MAX_POSITION, False),
                CONF_MIN_POSITION: self.config.get(CONF_MIN_POSITION),
                CONF_ENABLE_MIN_POSITION: self.config.get(CONF_ENABLE_MIN_POSITION, False),
                CONF_FOV_LEFT: self.config.get(CONF_FOV_LEFT),
                CONF_FOV_RIGHT: self.config.get(CONF_FOV_RIGHT),
                CONF_ENTITIES: self.config.get(CONF_ENTITIES),
                CONF_INVERSE_STATE: self.config.get(CONF_INVERSE_STATE),
                CONF_SUNSET_POS: self.config.get(CONF_SUNSET_POS),
                CONF_SUNSET_OFFSET: self.config.get(CONF_SUNSET_OFFSET),
                CONF_SUNRISE_OFFSET: self.config.get(CONF_SUNRISE_OFFSET),
                CONF_LENGTH_AWNING: self.config.get(CONF_LENGTH_AWNING),
                CONF_AWNING_ANGLE: self.config.get(CONF_AWNING_ANGLE),
                CONF_TILT_DISTANCE: self.config.get(CONF_TILT_DISTANCE),
                CONF_TILT_DEPTH: self.config.get(CONF_TILT_DEPTH),
                CONF_TILT_MODE: self.config.get(CONF_TILT_MODE),
                CONF_TEMP_ENTITY: self.config.get(CONF_TEMP_ENTITY),
                CONF_PRESENCE_ENTITY: self.config.get(CONF_PRESENCE_ENTITY),
                CONF_WEATHER_ENTITY: self.config.get(CONF_WEATHER_ENTITY),
                CONF_TEMP_LOW: self.config.get(CONF_TEMP_LOW),
                CONF_TEMP_HIGH: self.config.get(CONF_TEMP_HIGH),
                CONF_OUTSIDETEMP_ENTITY: self.config.get(CONF_OUTSIDETEMP_ENTITY),
                CONF_CLIMATE_MODE: self.config.get(CONF_CLIMATE_MODE),
                CONF_WEATHER_STATE: self.config.get(CONF_WEATHER_STATE),
                CONF_DELTA_POSITION: self.config.get(CONF_DELTA_POSITION),
                CONF_DELTA_TIME: self.config.get(CONF_DELTA_TIME),
                CONF_START_TIME: self.config.get(CONF_START_TIME),
                CONF_START_ENTITY: self.config.get(CONF_START_ENTITY),
                CONF_END_TIME: self.config.get(CONF_END_TIME),
                CONF_END_ENTITY: self.config.get(CONF_END_ENTITY),
                CONF_RETURN_SUNSET: self.config.get(CONF_RETURN_SUNSET, False),
                CONF_MANUAL_OVERRIDE_DURATION: self.config.get(CONF_MANUAL_OVERRIDE_DURATION),
                CONF_MANUAL_OVERRIDE_RESET: self.config.get(CONF_MANUAL_OVERRIDE_RESET),
                CONF_MANUAL_THRESHOLD: self.config.get(CONF_MANUAL_THRESHOLD),
                CONF_MANUAL_IGNORE_INTERMEDIATE: self.config.get(CONF_MANUAL_IGNORE_INTERMEDIATE),
                CONF_BLIND_SPOT_RIGHT: self.config.get(CONF_BLIND_SPOT_RIGHT),
                CONF_BLIND_SPOT_LEFT: self.config.get(CONF_BLIND_SPOT_LEFT),
                CONF_BLIND_SPOT_ELEVATION: self.config.get(CONF_BLIND_SPOT_ELEVATION),
                CONF_ENABLE_BLIND_SPOT: self.config.get(CONF_ENABLE_BLIND_SPOT),
                CONF_MIN_ELEVATION: self.config.get(CONF_MIN_ELEVATION),
                CONF_MAX_ELEVATION: self.config.get(CONF_MAX_ELEVATION),
                CONF_TRANSPARENT_BLIND: self.config.get(CONF_TRANSPARENT_BLIND, False),
                CONF_INTERP: self.config.get(CONF_INTERP),
                CONF_INTERP_START: self.config.get(CONF_INTERP_START),
                CONF_INTERP_END: self.config.get(CONF_INTERP_END),
                CONF_INTERP_LIST: self.config.get(CONF_INTERP_LIST, []),
                CONF_INTERP_LIST_NEW: self.config.get(CONF_INTERP_LIST_NEW, []),
                CONF_LUX_ENTITY: self.config.get(CONF_LUX_ENTITY),
                CONF_LUX_THRESHOLD: self.config.get(CONF_LUX_THRESHOLD),
                CONF_IRRADIANCE_ENTITY: self.config.get(CONF_IRRADIANCE_ENTITY),
                CONF_IRRADIANCE_THRESHOLD: self.config.get(CONF_IRRADIANCE_THRESHOLD),
                CONF_OUTSIDE_THRESHOLD: self.config.get(CONF_OUTSIDE_THRESHOLD),
            },
        )


class OptionsFlowHandler(OptionsFlow):
    """Options to adjust parameters."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options.

        self.config_entry is injected automatically by HA since 2024.3.
        Instance state (options, sensor_type) is initialised here because
        async_step_init is always the entry-point of every options flow run.
        """
        _LOGGER.debug("Initializing options flow for %s", self.config_entry.title)
        self.options: dict[str, Any] = dict(self.config_entry.options)
        self.sensor_type: SensorType = (
            self.config_entry.data.get(CONF_SENSOR_TYPE) or SensorType.BLIND
        )
        menu_options = ["automation", "blind"]
        if self.options.get(CONF_CLIMATE_MODE, False):
            menu_options.append("climate")
        if self.options.get(CONF_WEATHER_ENTITY):
            menu_options.append("weather")
        if self.options.get(CONF_ENABLE_BLIND_SPOT):
            menu_options.append("blind_spot")
        if self.options.get(CONF_INTERP):
            menu_options.append("interp")
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_automation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage automation options."""
        if user_input is not None:
            self._set_optional_to_none(
                [CONF_START_ENTITY, CONF_END_ENTITY, CONF_MANUAL_THRESHOLD], user_input
            )
            self.options.update(user_input)
            return await self._update_options()
        return self.async_show_form(
            step_id="automation",
            data_schema=self.add_suggested_values_to_schema(
                AUTOMATION_CONFIG, user_input or self.options
            ),
        )

    async def async_step_blind(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Adjust blind parameters."""
        if self.sensor_type == SensorType.BLIND:
            return await self.async_step_vertical()
        if self.sensor_type == SensorType.AWNING:
            return await self.async_step_horizontal()
        return await self.async_step_tilt()

    async def async_step_vertical(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for vertical blinds."""
        schema = CLIMATE_MODE.extend(VERTICAL_OPTIONS.schema)
        if self.options.get(CONF_CLIMATE_MODE, False):
            schema = VERTICAL_OPTIONS
        if user_input is not None:
            self._set_optional_to_none([CONF_MIN_ELEVATION, CONF_MAX_ELEVATION], user_input)
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="vertical",
                        data_schema=CLIMATE_MODE.extend(VERTICAL_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.options.update(user_input)
            if self.options.get(CONF_INTERP, False):
                return await self.async_step_interp()
            if self.options.get(CONF_ENABLE_BLIND_SPOT, False):
                return await self.async_step_blind_spot()
            if self.options.get(CONF_CLIMATE_MODE, False):
                return await self.async_step_climate()
            return await self._update_options()
        return self.async_show_form(
            step_id="vertical",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self.options
            ),
        )

    async def async_step_horizontal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for horizontal blinds."""
        schema = CLIMATE_MODE.extend(HORIZONTAL_OPTIONS.schema)
        if self.options.get(CONF_CLIMATE_MODE, False):
            schema = HORIZONTAL_OPTIONS
        if user_input is not None:
            self._set_optional_to_none([CONF_MIN_ELEVATION, CONF_MAX_ELEVATION], user_input)
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="horizontal",
                        data_schema=CLIMATE_MODE.extend(HORIZONTAL_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.options.update(user_input)
            if self.options.get(CONF_CLIMATE_MODE, False):
                return await self.async_step_climate()
            return await self._update_options()
        return self.async_show_form(
            step_id="horizontal",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self.options
            ),
        )

    async def async_step_tilt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show basic config for tilted blinds."""
        schema = CLIMATE_MODE.extend(TILT_OPTIONS.schema)
        if self.options.get(CONF_CLIMATE_MODE, False):
            schema = TILT_OPTIONS
        if user_input is not None:
            self._set_optional_to_none([CONF_MIN_ELEVATION, CONF_MAX_ELEVATION], user_input)
            if (
                user_input.get(CONF_MAX_ELEVATION) is not None
                and user_input.get(CONF_MIN_ELEVATION) is not None
            ):
                if user_input[CONF_MAX_ELEVATION] <= user_input[CONF_MIN_ELEVATION]:
                    _LOGGER.warning(
                        "Max elevation (%s) is <= min elevation (%s). Showing error.",
                        user_input[CONF_MAX_ELEVATION],
                        user_input[CONF_MIN_ELEVATION],
                    )
                    return self.async_show_form(
                        step_id="tilt",
                        data_schema=CLIMATE_MODE.extend(TILT_OPTIONS.schema),
                        errors={CONF_MAX_ELEVATION: "elevation_range"},
                    )
            self.options.update(user_input)
            if self.options.get(CONF_CLIMATE_MODE, False):
                return await self.async_step_climate()
            return await self._update_options()
        return self.async_show_form(
            step_id="tilt",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self.options
            ),
        )

    async def async_step_interp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show interpolation options."""
        if user_input is not None:
            if len(user_input[CONF_INTERP_LIST]) != len(user_input[CONF_INTERP_LIST_NEW]):
                return self.async_show_form(
                    step_id="interp",
                    data_schema=INTERPOLATION_OPTIONS,
                    errors={CONF_INTERP_LIST_NEW: "interp_list_length"},
                )
            self.options.update(user_input)
            return await self._update_options()
        return self.async_show_form(
            step_id="interp",
            data_schema=self.add_suggested_values_to_schema(
                INTERPOLATION_OPTIONS, user_input or self.options
            ),
        )

    async def async_step_blind_spot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add blindspot to data."""
        edges = _get_azimuth_edges(self.options)
        schema = vol.Schema(
            {
                vol.Required(CONF_BLIND_SPOT_LEFT, default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="slider", unit_of_measurement="°", min=0, max=edges - 1
                    )
                ),
                vol.Required(CONF_BLIND_SPOT_RIGHT, default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode="slider", unit_of_measurement="°", min=1, max=edges
                    )
                ),
                vol.Optional(CONF_BLIND_SPOT_ELEVATION): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=90)
                ),
            }
        )
        if user_input is not None:
            if user_input[CONF_BLIND_SPOT_RIGHT] <= user_input[CONF_BLIND_SPOT_LEFT]:
                return self.async_show_form(
                    step_id="blind_spot",
                    data_schema=schema,
                    errors={CONF_BLIND_SPOT_RIGHT: "blind_spot_range"},
                )
            self.options.update(user_input)
            return await self._update_options()
        return self.async_show_form(
            step_id="blind_spot",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self.options
            ),
        )

    async def async_step_climate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage climate options."""
        if user_input is not None:
            self._set_optional_to_none(
                [
                    CONF_OUTSIDETEMP_ENTITY,
                    CONF_WEATHER_ENTITY,
                    CONF_PRESENCE_ENTITY,
                    CONF_LUX_ENTITY,
                    CONF_IRRADIANCE_ENTITY,
                ],
                user_input,
            )
            self.options.update(user_input)
            if self.options.get(CONF_WEATHER_ENTITY):
                return await self.async_step_weather()
            return await self._update_options()
        return self.async_show_form(
            step_id="climate",
            data_schema=self.add_suggested_values_to_schema(
                CLIMATE_OPTIONS, user_input or self.options
            ),
        )

    async def async_step_weather(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage weather conditions."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()
        return self.async_show_form(
            step_id="weather",
            data_schema=self.add_suggested_values_to_schema(
                WEATHER_OPTIONS, user_input or self.options
            ),
        )

    async def _update_options(self) -> ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(data=self.options)

    @staticmethod
    def _set_optional_to_none(
        keys: list[str], user_input: dict[str, Any]
    ) -> None:
        """Set missing optional keys to None in user_input."""
        for key in keys:
            if key not in user_input:
                user_input[key] = None
