"""Tests for the config-flow validation helpers.

The interpolation selectors use ``custom_value=True``, so anything the user types is
stored verbatim. ``interpolate_states`` then runs ``map(int, ...)`` over those lists on
every coordinator tick and feeds the first one to ``np.interp`` as ``xp``:

* a non-numeric entry raised ValueError inside ``_async_update_data``, taking the whole
  integration down on every update;
* a non-ascending list made ``np.interp`` return silently wrong positions, because
  numpy does not verify that ``xp`` is sorted;
* a single-element list mapped every input to one constant.

None of that was validated before the entry was written.
"""

from __future__ import annotations

import pytest

from custom_components.adaptive_cover.config_flow import (
    _get_interp_list_error,
    _has_elevation_range_error,
)
from custom_components.adaptive_cover.const import (
    CONF_INTERP_LIST,
    CONF_INTERP_LIST_NEW,
    CONF_MAX_ELEVATION,
    CONF_MIN_ELEVATION,
)


def _lists(normal, new):
    return {CONF_INTERP_LIST: normal, CONF_INTERP_LIST_NEW: new}


# ---------------------------------------------------------------- interp lists
def test_empty_lists_are_accepted():
    """Interpolation then falls back to the start/end values."""
    assert _get_interp_list_error(_lists([], [])) is None


def test_missing_keys_are_accepted():
    assert _get_interp_list_error({}) is None


def test_valid_lists_are_accepted():
    assert (
        _get_interp_list_error(_lists(["0", "50", "100"], ["10", "40", "90"])) is None
    )


def test_descending_target_list_is_accepted():
    """Only the source list must ascend; a descending target inverts the state."""
    assert (
        _get_interp_list_error(_lists(["0", "50", "100"], ["100", "40", "0"])) is None
    )


def test_length_mismatch():
    assert _get_interp_list_error(_lists(["0", "100"], ["0"])) == "interp_list_length"


def test_non_numeric_entry():
    assert (
        _get_interp_list_error(_lists(["0", "abc"], ["0", "100"]))
        == "interp_list_not_numeric"
    )


def test_non_numeric_entry_in_target_list():
    assert (
        _get_interp_list_error(_lists(["0", "100"], ["0", "oops"]))
        == "interp_list_not_numeric"
    )


def test_single_entry_is_too_short():
    assert _get_interp_list_error(_lists(["50"], ["80"])) == "interp_list_too_short"


@pytest.mark.parametrize("normal", [["100", "0"], ["0", "50", "20"], ["0", "50", "50"]])
def test_source_list_must_strictly_ascend(normal):
    new = ["0"] * len(normal)
    assert _get_interp_list_error(_lists(normal, new)) == "interp_list_not_ascending"


# ------------------------------------------------------------- elevation range
def test_elevation_ok_when_max_above_min():
    assert (
        _has_elevation_range_error({CONF_MIN_ELEVATION: 10, CONF_MAX_ELEVATION: 80})
        is False
    )


@pytest.mark.parametrize(
    "payload",
    [
        {CONF_MIN_ELEVATION: 80, CONF_MAX_ELEVATION: 10},
        {CONF_MIN_ELEVATION: 45, CONF_MAX_ELEVATION: 45},
    ],
)
def test_elevation_error_when_max_not_above_min(payload):
    assert _has_elevation_range_error(payload) is True


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {CONF_MIN_ELEVATION: 10},
        {CONF_MAX_ELEVATION: 80},
        {CONF_MIN_ELEVATION: None, CONF_MAX_ELEVATION: 80},
    ],
)
def test_elevation_unset_bounds_are_not_an_error(payload):
    assert _has_elevation_range_error(payload) is False
