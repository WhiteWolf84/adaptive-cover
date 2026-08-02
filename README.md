![Version](https://img.shields.io/github/v/release/WhiteWolf84/adaptive-cover?include_prereleases&style=for-the-badge)

![logo](https://github.com/WhiteWolf84/adaptive-cover/blob/main/images/logo.png#gh-light-mode-only)
![logo](https://github.com/WhiteWolf84/adaptive-cover/blob/main/images/dark_logo.png#gh-dark-mode-only)

# Adaptive Cover

This Custom-Integration provides sensors for vertical and horizontal blinds based on the sun's position by calculating the position to filter out direct sunlight.

This integration builds upon the template sensor from this forum post [Automatic Blinds](https://community.home-assistant.io/t/automatic-blinds-sunscreen-control-based-on-sun-platform/)

> **This is a fork** of [basbruss/adaptive-cover](https://github.com/basbruss/adaptive-cover), maintained for recent Home Assistant releases. Requires **Home Assistant 2025.1.0 or newer**. Report issues for this fork on [its own tracker](https://github.com/WhiteWolf84/adaptive-cover/issues).

- [Adaptive Cover](#adaptive-cover)
  - [Features](#features)
  - [Installation](#installation)
    - [HACS (Recommended)](#hacs-recommended)
    - [Manual](#manual)
  - [Setup](#setup)
    - [Finding the Window Azimuth](#finding-the-window-azimuth)
  - [Cover Types](#cover-types)
  - [Modes](#modes)
    - [Basic mode](#basic-mode)
    - [Climate mode](#climate-mode)
      - [Climate strategies](#climate-strategies)
  - [Variables](#variables)
    - [Common](#common)
    - [Vertical](#vertical)
    - [Horizontal](#horizontal)
    - [Tilt](#tilt)
    - [Automation](#automation)
    - [Climate](#climate)
    - [Blindspot](#blindspot)
    - [Interpolation](#interpolation)
  - [Entities](#entities)
  - [Features Planned](#features-planned)
    - [Simulation](#simulation)
    - [Blueprint (deprecated since v1.0.0)](#blueprint-deprecated-since-v100)

## Features

- Individual service devices for `vertical`, `horizontal` and `tilted` covers
- Two mode approach with multiple strategies [Modes(`basic`,`climate`)](#modes)
- Binary Sensor to track when the sun is in front of the window
- Sensors for `start` and `end` time
- Auto manual override detection
- Optional position [interpolation](#interpolation) for covers that do not operate over the full 0-100% range

- **Climate Mode**

  - Weather condition based operation
  - Presence based operation
  - Switch to toggle climate mode
  - Sensor for displaying the operation modus (`winter`,`intermediate`,`summer`)

- **Adaptive Control**

  - Turn control on/off
  - Control multiple covers
  - Set start time to prevent opening blinds while you are asleep
  - Set minimum interval time between position changes
  - set minimum percentage change

## Installation

### HACS (Recommended)

Add <https://github.com/WhiteWolf84/adaptive-cover> as custom repository to HACS.
Search and download Adaptive Cover within HACS.

Restart Home-Assistant and add the integration.

> Releases are published as pre-releases first. If you want those, enable beta releases for this repository in HACS.

### Manual

Download the `adaptive_cover` folder from this github.
Add the folder to `config/custom_components/`.

Restart Home-Assistant and add the integration.

## Setup

Adaptive Cover supports (for now) three types of covers/blinds; `Vertical`, `Horizontal` and `Venetian (Tilted)` blinds.
Each type has its own specific parameters to setup a sensor. To setup the sensor you first need to find out the **azimuth** of your window(s).

### Finding the Window Azimuth

The simplest and most accurate way to find the azimuth of your window is using [SunCalc.org](https://www.suncalc.org/):

1. Go to [suncalc.org](https://www.suncalc.org/) and search for your address.
2. Zoom in on your house as much as possible.
3. Observe the orange line (sun trajectory). Look at the "Time" slider at the top.
4. Move the slider until the line forms an exact 90-degree angle (perpendicular) to your window.
5. Look at the data box on the top left. The **Azimuth** value shown for that specific time is the value you need to input in the configuration.

## Cover Types

|              | Vertical                      | Horizontal                      | Tilted                          |
| ------------ | ----------------------------- | ------------------------------- | ------------------------------- |
|              | ![alt text](images/image.png) | ![alt text](images/image-2.png) | ![alt text](images/image-1.png) |
| **Movement** | Up/Down                       | In/Out                          | Tilting                         |
|              | [variables](#vertical)        | [variables](#horizontal)        | [variables](#tilt)              |

## Modes

This component supports two strategy modes: A `basic` mode and a `climate comfort/energy saving` mode that works with presence and temperature detection.

```mermaid
  graph TD

  A[("fa:fa-sun Sundata")]
  A --> B["Basic Mode"]
  A --> C["Climate Mode"]

  subgraph "Basic Mode"
      B --> BA("Sun within field of view")

      BA --> |No| BC{{Default}}
      BC --> BE("Time between sunset and sunrise?")
      BE --> |Yes| BF["Return default"]
      BE --> |No| BG["Return Sunset default"]

      BA --> |Yes| BD("Elevation above 0?")
      BD --> |Yes| BH{{"Calculated Position"}}
      BD --> |No| BC
  end

  subgraph "Climate Mode"
      C --> CA("Check Presence")
  end

  subgraph "Occupants"
      CA --> |True| CB("Temperature above maximum comfort (summer)?")

      CB --> |Yes| CD("Transparent blind?")
      CB --> |No| CE("Lux/Irradiance below threshold or Weather is not sunny?")

      CD --> |Yes| CF["Return fully closed (0%)"]
      CD --> |No| B

      CE --> |Yes| CG("Temperature below minimum comfort (winter) and sun infront of window and elevation > 0?")
      CE --> |No| B

      CG --> |Yes| CH["Return fully open (100%)"]
      CG --> |No| BC
  end

  subgraph "No Occupants"
      CA --> |False| CC("Sun infront of window and elevation > 0?")
      CC --> |No| BC
      CC --> |Yes| CI("Temperature above maximum comfort (summer)?")
      CI --> |Yes| CF
      CI --> |No| CJ("Temperature below minimum comfort (winter)")
      CJ --> |Yes| CH
      CJ --> |No| BC
  end
```

### Basic mode

This mode uses the calculated position when the sun is within the specified azimuth range of the window. Else it defaults to the default value or after sunset value depending on the time of day.

### Climate mode

This mode calculates the position based on extra parameters for presence, indoor temperature, minimal comfort temperature, maximum comfort temperature and weather (optional).
This mode is split up in two types of strategies; Presence and No Presence, both described below.

#### Climate strategies

- **No Presence**:
  Providing daylight to the room is no objective if there is no presence.

  - **Below minimal comfort temperature**:
    If the sun is above the horizon and the indoor temperature is below the minimal comfort temperature it opens the blind fully or tilt the slats to be parallel with the sun rays to allow for maximum solar radiation to heat up the room.

  - **Above maximum comfort temperature**:
    The objective is to not heat up the room any further by blocking out all possible radiation. All blinds close fully to block out light. <br> <br>
    If the indoor temperature is between both thresholds the position defaults to the set default value based on the time of day.

- **Presence** (or no Presence Entity set):
  The objective is to reduce glare while providing daylight to the room. All calculation is done by the basic model for Horizontal and Vertical blinds. <br> <br>
  If you added a weather entity, it will only use the above calculations if the weather state corresponds with the existence of direct sun rays. These states are `sunny`, `partlycloudy`, `cloudy` and `clear` by default, but you can change the list of states in the weather options. If not equal to these states the position will default to the default value to allow more sunlight entering the room with minimizing the glare due to the weather condition. <br><br>
  Tilted blinds will only deviate from the above approach if the inside temperature is above the maximum comfort temperature. In that case, the slats will be positioned at 45 degrees as this is [found optimal](https://www.mdpi.com/1996-1073/13/7/1731).

## Variables

Defaults and ranges below match the configuration flow. Variables with no default are optional and left unset unless you fill them in.

### Common

| Variables                     | Default | Range | Description                                                                                                               |
| ----------------------------- | ------- | ----- | ------------------------------------------------------------------------------------------------------------------------- |
| Entities                      | []      |       | Denotes entities controllable by the integration                                                                          |
| Window Azimuth                | 180     | 0-359 | The compass direction the window is facing perpendicularly (use [suncalc.org](https://www.suncalc.org/) to find it easily) |
| Default Position              | 60      | 0-100 | Initial position of the cover when no glare or direct sunlight is detected                                                |
| Minimal Position              | _unset_ | 0-99  | Minimal opening position for the cover, suitable for partially closing certain cover types                                 |
| Force minimum only in direct sun | False |     | Apply the minimal position only while sunlight hits the glass directly                                                    |
| Maximum Position              | _unset_ | 1-100 | Maximum opening position for the cover, suitable for partially opening certain cover types                                |
| Force maximum only in direct sun | False |     | Apply the maximum position only while sunlight hits the glass directly                                                    |
| Field of view Left            | 45      | 1-90  | Unobstructed viewing angle from window center to the left, in degrees                                                     |
| Field of view Right           | 45      | 1-90  | Unobstructed viewing angle from window center to the right, in degrees                                                    |
| Minimal Elevation             | _unset_ | 0-90  | Minimal elevation degree of the sun to be considered                                                                      |
| Maximum Elevation             | _unset_ | 0-90  | Maximum elevation degree of the sun to be considered                                                                      |
| Default position after Sunset | 0       | 0-100 | Cover's default position from sunset to sunrise                                                                           |
| Offset Sunset time            | 0       |       | Additional minutes before/after sunset                                                                                    |
| Offset Sunrise time           | 0       |       | Additional minutes before/after sunrise                                                                                   |
| Inverse State                 | False   |       | Calculates inverse state for covers fully closed at 100%                                                                  |
| Climate Mode                  | False   |       | Enables the [climate mode](#climate-mode) options                                                                         |
| Setup Blindspot               | False   |       | Enables the [blindspot](#blindspot) options                                                                               |
| Custom open/close positions   | False   |       | Enables [interpolation](#interpolation)                                                                                   |

### Vertical

| Variables         | Default | Range  | Description                                                                                                                              |
| ----------------- | ------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Window Height     | 2.1     | 0.1-6  | Length of fully extended cover/window, in meters                                                                                          |
| Glare Zone        | 0.5     | 0.1-2  | Objects within this distance of the cover recieve direct sunlight. Measured horizontally from the bottom of the cover when fully extended |
| Obstacle Height   | 0       | 0-10   | Height of an obstacle in front of the window (hedge, wall). 0 disables it                                                                 |
| Obstacle Distance | 0       | 0-10   | Distance from the window to that obstacle, in meters. 0 disables it                                                                      |

When an obstacle is configured, the cover only closes as far as the obstacle's shadow does not already cover the window.

### Horizontal

Horizontal (awning) covers use every Vertical variable above, plus:

| Variables                  | Default | Range | Description                              |
| -------------------------- | ------- | ----- | ---------------------------------------- |
| Awning Length (horizontal) | 2.1     | 0.3-6 | Length of the awning when fully extended |
| Awning Angle               | 0       | 0-45  | Angle of the awning from the wall        |

### Tilt

| Variables     | Default | Range  | Description                                                                                                                  |
| ------------- | ------- | ------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Slat Depth    | 3       | 0.1-15 | Width of each slat (`slat_depth` in cm)                                                                                      |
| Slat Distance | 2       | 0.1-15 | Vertical distance between two slats in horizontal position (`slat_distance` in cm)                                           |
| Tilt Mode     | mode2   |        | `mode1`: single direction (0% = closed / 100% = open) <br> `mode2`: bi-directional (0% = closed / 50% = open / 100% = closed) |

### Automation

| Variables                                  | Default      | Range | Description                                                                                    |
| ------------------------------------------ | ------------ | ----- | ------------------------------------------------------------------------------------------------ |
| Minimum Delta Position                     | 5            | 1-90  | Minimum position change required before another change can occur                               |
| Minimum Delta Time                         | 5            | 2-    | Minimum time gap between position changes, in minutes                                          |
| Start Time                                 | `"00:00:00"` |       | Earliest time a cover can be adjusted after midnight                                           |
| Start Time Entity                          | _unset_      |       | The earliest moment a cover may be changed after midnight. _Overrides the `start_time` value_  |
| Manual Override Duration                   | `60 min`     |       | Minimum duration for manual control status to remain active                                    |
| Manual Override reset Timer                | False        |       | Resets duration timer each time the position changes while the manual control status is active |
| Manual Override Threshold                  | 5            | 0-99  | Minimal position change to be recognized as manual change                                      |
| Manual Override ignore intermediate states | False        |       | Ignore StateChangedEvents that have state `opening` or `closing`                               |
| End Time                                   | `"00:00:00"` |       | Latest time a cover can be adjusted each day. `00:00:00` means end of day                      |
| End Time Entity                            | _unset_      |       | The latest moment a cover may be changed. _Overrides the `end_time` value_                     |
| Adjust at end time                         | `False`      |       | Make sure to always update the position to the default setting at the end time.                |

### Climate

| Variables                     | Default | Range | Example                                       | Description                                                                                                                                         |
| ----------------------------- | ------- | ----- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Indoor Temperature Entity     | _unset_ |       | `climate.living_room` \| `sensor.indoor_temp` |                                                                                                                                                     |
| Minimum Comfort Temperature   | 21      | 0-86  |                                               |                                                                                                                                                     |
| Maximum Comfort Temperature   | 25      | 0-90  |                                               |                                                                                                                                                     |
| Outdoor Temperature Entity    | _unset_ |       | `sensor.outdoor_temp`                         |                                                                                                                                                     |
| Outdoor Temperature Threshold | 0       | 0-100 |                                               | If the minimum outside temperature for summer mode is set and the outside temperature falls below this threshold, summer mode will not be activated. |
| Presence Entity               | _unset_ |       |                                               | Supports `device_tracker`, `zone`, `binary_sensor` and `input_boolean`                                                                              |
| Weather Entity                | _unset_ |       | `weather.home`                                | Can also serve as outdoor temperature sensor                                                                                                        |
| Weather States                | `sunny`, `partlycloudy`, `cloudy`, `clear` | | | States considered to allow direct sun rays                                                                              |
| Transparent/Filtering blind   | False   |       |                                               | Forces fully closed (0%) in summer mode                                                                                                             |
| Lux Entity                    | _unset_ |       | `sensor.lux`                                  | Returns measured lux                                                                                                                                |
| Lux Threshold                 | `1000`  |       |                                               | "In non-summer, above threshold, use optimal position. Otherwise, default position or fully open in winter."                                         |
| Irradiance Entity             | _unset_ |       | `sensor.irradiance`                           | Returns measured irradiance                                                                                                                         |
| Irradiance Threshold          | `300`   |       |                                               | "In non-summer, above threshold, use optimal position. Otherwise, default position or fully open in winter."                                         |

### Blindspot

| Variables            | Default | Range                       | Description                                                                                                        |
| -------------------- | ------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Blind Spot Left      | 0       | 0 to (fov_left + fov_right - 1) | Start point of the blind spot on the predefined field of view, where 0 is equal to the window azimuth - fov left. |
| Blind Spot Right     | 1       | 1 to (fov_left + fov_right)     | End point of the blind spot on the predefined field of view.                                                      |
| Blind Spot Elevation | _unset_ | 0-90                        | Maximum elevation of the sun for the blindspot area to apply.                                                      |

### Interpolation

Some covers do not travel over the full 0-100% range, or report their position on a different scale. Enable **Custom open/close positions** in the cover options to remap the calculated position before it is sent.

| Variables                | Default | Range | Description                                                                     |
| ------------------------ | ------- | ----- | --------------------------------------------------------------------------------- |
| Interpolation Start      | _unset_ | 0-100 | Value the calculated `0` is mapped to                                           |
| Interpolation End        | _unset_ | 0-100 | Value the calculated `100` is mapped to                                         |
| Interpolation List       | []      |       | Source points for a multi-point mapping. Must be whole numbers, strictly ascending, at least two entries |
| New Interpolation List   | []      |       | Target points, same number of entries as the source list                        |

When both lists are filled they take precedence over the start/end pair. A descending target list inverts the state.

## Entities

The integration dynamically adds multiple entities based on the used features.

Each config entry creates one device named after its cover type (`Vertical`, `Horizontal` or `Tilt`), and entity ids are derived from that device name — not from the name you gave the config entry. With several entries of the same type Home Assistant appends `_2`, `_3` and so on. The ids below are shown for a `vertical` entry; rename the entities afterwards if you want your own naming.

These entities are always available:

| Entities                                | Default        | Description                                                                                                                                                  |
| --------------------------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sensor.vertical_cover_position`         |                | Reflects the current state determined by predefined settings and factors such as sun position, weather, and temperature                                      |
| `sensor.vertical_control_method`         | `intermediate` | Indicates the active control strategy based on weather conditions. Options include `winter`, `summer`, and `intermediate`                                     |
| `sensor.vertical_start_sun`              |                | Shows the starting time when the sun enters the window's view, with an interval of every 5 minutes.                                                          |
| `sensor.vertical_end_sun`                |                | Indicates the ending time when the sun exits the window's view, with an interval of every 5 minutes.                                                         |
| `binary_sensor.vertical_manual_override` | `off`          | Indicates if manual override is engaged for any blinds.                                                                                                      |
| `binary_sensor.vertical_sun_infront`     | `off`          | Indicates whether the sun is in front of the window within the designated field of view.                                                                     |
| `switch.vertical_toggle_control`         | `on`           | Activates the adaptive control feature. When enabled, blinds adjust based on calculated position, unless manually overridden.                                 |
| `switch.vertical_manual_override`        | `on`           | Enables detection of manual overrides. A cover is marked if its position differs from the calculated one, resetting to adaptive control after a set duration. |
| `button.vertical_reset_manual_override`  |                | Resets manual override tags for all covers; if the toggle control switch is on, it also restores blinds to their correct positions.                           |

The two switches above and the button are only created when at least one cover entity is assigned to the config entry. The climate switches below do not depend on that.

When climate mode is setup you will also get these entities:

| Entities                              | Default | Condition                                | Description                                                                                                 |
| ------------------------------------- | ------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `switch.vertical_climate_mode`         | `on`    | always, in climate mode                  | Enables climate mode strategy; otherwise, defaults to the standard strategy.                                |
| `switch.vertical_outside_temperature`  | `off`   | a weather or outdoor temperature entity is set | Switches between inside and outside temperatures as the basis for determining the climate control strategy. |
| `switch.vertical_lux`                  | `on`    | a lux entity is set                      | Lets the lux threshold take part in the glare decision.                                                     |
| `switch.vertical_irradiance`           | `on`    | an irradiance entity is set              | Lets the irradiance threshold take part in the glare decision.                                              |

![entities](https://github.com/WhiteWolf84/adaptive-cover/blob/main/images/entities.png)

## Features Planned

- Manual override controls

  - ~~Time to revert back to adaptive control~~
  - ~~Reset button~~
  - Wait until next manual/none adaptive change

- ~~Algorithm to control radiation and/or illumination~~

### Simulation

![combined_simulation](images/sim_plot.png)

### Blueprint (deprecated since v1.0.0)

This integration provides the option to download a blueprint to control the covers automatically by the provide sensor.
By selecting the option the blueprints will be added to your local blueprints folder.
