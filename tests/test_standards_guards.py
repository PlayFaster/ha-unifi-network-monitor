"""Standards guards — the sweeps that fail when a *new* entity forgets something.

Phase 2 of the August 2026 plan (§M), items 15, 17, 18 and 19. Every test here
is a sweep with a named allow-list rather than a check of one entity, because
the failure each one guards is an omission in code not yet written. A test that
inspects today's entities passes forever and catches nothing.

The allow-lists are empty by design. Adding an entry is a visible, reviewable
act; forgetting a guard band or typing ``TOTAL`` into a new description is not.
That asymmetry is the whole point.
"""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, PERCENTAGE

from custom_components.unifi_network_monitor.config_flow import (
    _edit_schema,
    _settings_schema,
    _user_schema,
)
from custom_components.unifi_network_monitor.const import CONF_API_KEY, CONF_SITE
from custom_components.unifi_network_monitor.sensor import (
    AP_SENSORS,
    GATEWAY_SENSORS,
    HEALTH_SENSORS,
    SWITCH_SENSORS,
    UnifiSensorEntityDescription,
)

_ALL_SENSORS: tuple[UnifiSensorEntityDescription, ...] = (
    GATEWAY_SENSORS + HEALTH_SENSORS + AP_SENSORS + SWITCH_SENSORS
)


# ---------------------------------------------------------------------------
# item 15 — guard-band coverage sweep
# ---------------------------------------------------------------------------

# Numeric sensors deliberately shipped without a lower bound, with the reason
# this sweep demands. Empty by design.
#
# NOTE the sweep is **static**, not runtime. A guard band is never published as
# entity state or an attribute — it only ever suppresses an out-of-range value —
# so no amount of live querying can see whether one exists. Reading the
# descriptions is the only place the question can be asked.
ALLOWED_NO_MIN_LIMIT: frozenset[str] = frozenset()

# Sensors measured in percent must declare an upper bound: the domain really is
# closed at 100, so a value above it is bad data rather than a big number.
# Everything else — counts, byte totals, uptimes — is genuinely unbounded, and
# an invented ceiling there would suppress a legitimate reading. Empty by
# design; a percentage sensor that truly exceeds 100 belongs here with a reason.
ALLOWED_PERCENT_NO_MAX: frozenset[str] = frozenset()


def _is_numeric(desc: UnifiSensorEntityDescription) -> bool:
    """Report whether a sensor publishes a number: it carries a unit or a state class."""
    return bool(desc.native_unit_of_measurement) or desc.state_class is not None


def test_every_numeric_sensor_has_a_lower_guard_band() -> None:
    """A numeric sensor must declare ``min_limit`` or be named in the allow-list.

    The failure is silent and looks like data. A controller returning ``-1`` for
    "not computed", or a counter briefly reporting a negative delta, publishes a
    number that charts, triggers automations and enters long-term statistics.
    Guard bands turn that into ``unknown``, which is honest.
    """
    offenders = [
        d.key
        for d in _ALL_SENSORS
        if _is_numeric(d) and d.min_limit is None and d.key not in ALLOWED_NO_MIN_LIMIT
    ]
    assert not offenders, (
        "numeric sensors with no min_limit — add a band, or add the key to "
        "ALLOWED_NO_MIN_LIMIT with a written reason:\n" + "\n".join(sorted(offenders))
    )


def test_every_percentage_sensor_has_an_upper_guard_band() -> None:
    """A percentage has a real ceiling, so it gets one.

    Deliberately scoped to percentages rather than "every numeric sensor". A
    count of rogue APs or a byte total has no credible maximum, and demanding
    one would push the next author into inventing a number that silently
    suppresses real data — the opposite of what a guard band is for.
    """
    offenders = [
        d.key
        for d in _ALL_SENSORS
        if d.native_unit_of_measurement == PERCENTAGE
        and d.max_limit is None
        and d.key not in ALLOWED_PERCENT_NO_MAX
    ]
    assert not offenders, "percentage sensors with no max_limit:\n" + "\n".join(
        sorted(offenders)
    )


def test_no_accumulating_counter_carries_an_upper_bound() -> None:
    """A ceiling on a total is a data-loss bug, not a safety net.

    ``dev_std_review`` F-11 measured this clean at 67 of 67 and it must stay
    that way: a byte counter that crosses its invented ceiling would go
    ``unknown`` and stay there for the rest of the cycle.
    """
    offenders = [
        d.key
        for d in _ALL_SENSORS
        if d.state_class is SensorStateClass.TOTAL_INCREASING
        and d.max_limit is not None
    ]
    assert not offenders, "accumulating counters with a max_limit:\n" + "\n".join(
        sorted(offenders)
    )


def test_guard_band_allow_lists_have_no_stale_entries() -> None:
    """An allow-list entry that no longer matches anything must be removed.

    Without this the lists rot: a key is listed, the sensor is later renamed or
    deleted, and the entry silently keeps excusing nothing while reading as
    though a known exception still exists.
    """
    keys = {d.key for d in _ALL_SENSORS}
    stale_min = ALLOWED_NO_MIN_LIMIT - keys
    stale_max = ALLOWED_PERCENT_NO_MAX - keys
    assert not stale_min, (
        f"ALLOWED_NO_MIN_LIMIT names sensors that do not exist: {stale_min}"
    )
    assert not stale_max, (
        f"ALLOWED_PERCENT_NO_MAX names sensors that do not exist: {stale_max}"
    )


def test_guard_band_sweep_is_not_vacuous() -> None:
    """Guard the guard: an empty description tuple would pass every sweep above."""
    numeric = [d for d in _ALL_SENSORS if _is_numeric(d)]
    assert len(numeric) >= 50, (
        f"only {len(numeric)} numeric sensors found — imports stale"
    )


def test_min_limit_is_never_above_max_limit() -> None:
    """A transposed pair suppresses every reading, which looks like a dead sensor."""
    offenders = [
        d.key
        for d in _ALL_SENSORS
        if d.min_limit is not None
        and d.max_limit is not None
        and d.min_limit > d.max_limit
    ]
    assert not offenders, f"transposed guard bands: {offenders}"


# ---------------------------------------------------------------------------
# item 19 — ban SensorStateClass.TOTAL
# ---------------------------------------------------------------------------

# Sensors allowed to use ``SensorStateClass.TOTAL``. Empty by design, and free
# to adopt: there are zero today.
ALLOWED_TOTAL_STATE_CLASS: frozenset[str] = frozenset()


def test_no_sensor_uses_the_total_state_class() -> None:
    """``TOTAL`` and ``TOTAL_INCREASING`` look interchangeable and are not.

    Under ``TOTAL`` the recorder recognises a new cycle *only* from a changing
    ``last_reset`` attribute; a counter that simply drops to zero is not treated
    as having reset, so the drop is recorded as negative consumption. Every
    counter this integration exposes resets to zero without publishing
    ``last_reset``, so ``TOTAL_INCREASING`` is always right here. Nothing fails
    at runtime when it is wrong, which is why this is a test.

    **If this fails, justify the ``TOTAL`` — do not silence it.** A genuine
    ``TOTAL`` sensor is one whose value can legitimately fall without that being
    a reset, and it must publish ``last_reset``.
    """
    offenders = [
        d.key
        for d in _ALL_SENSORS
        if d.state_class is SensorStateClass.TOTAL
        and d.key not in ALLOWED_TOTAL_STATE_CLASS
    ]
    assert not offenders, (
        "sensors using SensorStateClass.TOTAL — use TOTAL_INCREASING for a "
        "counter that resets to zero:\n" + "\n".join(sorted(offenders))
    )


def test_total_allow_list_has_no_stale_entries() -> None:
    """The TOTAL allow-list must not outlive the sensors it excuses."""
    assert not ALLOWED_TOTAL_STATE_CLASS - {d.key for d in _ALL_SENSORS}


def test_a_forecast_never_carries_a_state_class() -> None:
    """Projections must stay out of statistics and long-term storage."""
    for desc in _ALL_SENSORS:
        if desc.key.endswith("_month_projected"):
            assert desc.state_class is None, desc.key


# ---------------------------------------------------------------------------
# item 17 — a stored secret is never pre-filled into a rebuilt schema
# ---------------------------------------------------------------------------

# Distinctive enough that finding it anywhere in a rendered schema is
# unambiguous evidence the stored credential leaked into the form.
_STORED_SECRET = "s3cr3t-stored-do-not-render"
_STORED_KEY = "aPiKeY-stored-do-not-render"

_SECRET_KEYS = {CONF_PASSWORD, CONF_API_KEY}

_STORED_OPTIONS: dict[str, Any] = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: _STORED_SECRET,
    CONF_API_KEY: _STORED_KEY,
    CONF_SITE: "default",
}


def _markers(schema: vol.Schema) -> list[Any]:
    return list(schema.schema)


def _resolved_default(marker: Any) -> Any:
    """Return a marker's default, or None.

    Defaults are wrapped in a callable factory, so ``marker.default`` is not the
    value — calling it is what reveals what the form would actually show.
    """
    default = getattr(marker, "default", vol.UNDEFINED)
    if default is vol.UNDEFINED:
        return None
    return default() if callable(default) else default


def _build(name: str) -> vol.Schema:
    if name == "settings":
        return _settings_schema(_STORED_OPTIONS, False)
    return {"user": _user_schema, "edit": _edit_schema}[name](_STORED_OPTIONS)


@pytest.mark.parametrize("build", ["user", "edit", "settings"])
def test_stored_secrets_are_never_pre_filled(build: str) -> None:
    """A stored credential must not be rendered back into a form.

    The failure is silent: the screen looks correct and the value is exposed
    only when someone clicks the eye icon. Two projects in this family have
    shipped exactly this.
    """
    for marker in _markers(_build(build)):
        if marker.schema not in _SECRET_KEYS:
            continue
        assert _resolved_default(marker) in (None, ""), (
            f"{build}: {marker.schema} is pre-filled with the stored value"
        )
        description = getattr(marker, "description", None) or {}
        assert "suggested_value" not in description, (
            f"{build}: {marker.schema} carries the stored value as suggested_value"
        )


@pytest.mark.parametrize("build", ["user", "edit", "settings"])
def test_no_field_leaks_a_stored_secret(build: str) -> None:
    """Belt and braces: neither secret may appear in *any* field.

    The per-field check above only inspects keys already known to be secret.
    This catches the other shape — a credential copied into some non-secret
    field's default, where the eye icon is not even needed.
    """
    schema = _build(build)
    rendered = (
        repr(schema.schema)
        + "".join(repr(_resolved_default(m)) for m in _markers(schema))
        + "".join(repr(getattr(m, "description", None)) for m in _markers(schema))
    )
    assert _STORED_SECRET not in rendered, f"{build} leaks the stored password"
    assert _STORED_KEY not in rendered, f"{build} leaks the stored API key"


def test_secret_sweep_actually_sees_the_secret_fields() -> None:
    """Guard the guard: a schema that stopped offering credentials passes vacuously."""
    found = {m.schema for m in _markers(_build("edit")) if m.schema in _SECRET_KEYS}
    assert found == _SECRET_KEYS, f"edit schema no longer offers {_SECRET_KEYS - found}"
