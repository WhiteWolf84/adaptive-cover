"""Test configuration for the Adaptive Cover integration.

The unit tests below exercise only pure logic (solar-window scanning, sunset
offset comparison, per-tick caching). They need the integration package to be
importable but do not require a running Home Assistant.

When the full ``homeassistant`` package is installed (e.g. in the dev/CI
environment defined by ``requirements-dev.txt``) it is used as-is. When it is
not, a minimal stub exposing just the symbols the integration imports at module
load time is injected, so the suite stays runnable standalone.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
import types
from pathlib import Path
from zoneinfo import ZoneInfo

# Make ``custom_components`` importable from the repository root.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _install_homeassistant_stub() -> None:
    """Register a minimal ``homeassistant`` stub sufficient for imports."""

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []  # mark as package

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # noqa: D401 - stub
        """Stub HomeAssistant type used purely for annotations."""

    def split_entity_id(entity_id: str) -> list[str]:
        return entity_id.split(".", 1)

    core.HomeAssistant = HomeAssistant
    core.split_entity_id = split_entity_id

    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.utcnow = lambda: _dt.datetime.now(_dt.UTC)
    dt_mod.get_time_zone = lambda name: ZoneInfo(name)

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sun = types.ModuleType("homeassistant.helpers.sun")

    def _get_astral_observer(hass):
        from astral import Observer

        return Observer(0.0, 0.0, 0.0)

    # Only the modern name: get_astral_location is deprecated upstream and the
    # integration must never reach for it when the new helper exists.
    sun.get_astral_observer = _get_astral_observer

    # Minimal surface used by the coordinator service layer (service.py).
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    cover = types.ModuleType("homeassistant.components.cover")
    cover.DOMAIN = "cover"

    const = types.ModuleType("homeassistant.const")
    const.ATTR_ENTITY_ID = "entity_id"
    const.SERVICE_SET_COVER_POSITION = "set_cover_position"
    const.SERVICE_SET_COVER_TILT_POSITION = "set_cover_tilt_position"

    exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Stub HomeAssistantError."""

    class ServiceNotFound(HomeAssistantError):
        """Stub ServiceNotFound."""

    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ServiceNotFound = ServiceNotFound

    sys.modules.update(
        {
            "homeassistant": ha,
            "homeassistant.core": core,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt_mod,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.sun": sun,
            "homeassistant.components": components,
            "homeassistant.components.cover": cover,
            "homeassistant.const": const,
            "homeassistant.exceptions": exceptions,
        }
    )


if importlib.util.find_spec("homeassistant") is None:
    _install_homeassistant_stub()
