# Test Guards: UniFi Network Monitor

Rationale for the guard tests listed under _Tests that will stop you_ in [`AGENTS.md`](../AGENTS.md). `AGENTS.md` states what fails and what to do; this file records why each guard exists. When a guard test is added, its row goes in `AGENTS.md` and its rationale here.

---

## Guards Moved From `AGENTS.md` (2026-09-23)

Each entry is the rationale column of the former `AGENTS.md` table, copied verbatim.

### A sensor with a unit or `state_class`

**Tests:** `test_every_numeric_sensor_has_a_lower_guard_band`

Declare `min_limit`, or add the key to `ALLOWED_NO_MIN_LIMIT` **with a reason**. Then add a row to `docs/value_min_max.md` — §6 wants it to match the code in both directions, and it currently does (0 undocumented). `test_guard_band_allow_lists_have_no_stale_entries` fails if an exemption outlives its sensor.

### A sensor measured in `%`

**Tests:** `test_every_percentage_sensor_has_an_upper_guard_band`

Declare `max_limit`. Scoped to percentages on purpose: a ceiling on a count or a byte total would suppress real data the first time it was crossed, which is why `test_no_accumulating_counter_carries_an_upper_bound` asserts the **absence** of one on every `TOTAL_INCREASING` sensor.

### Any sensor at all

**Tests:** `test_no_sensor_uses_the_total_state_class`

Use `TOTAL_INCREASING`. Plain `TOTAL` needs a changing `last_reset` for the recorder to see a rollover; every counter here resets to zero without publishing one, so `TOTAL` walks long-term statistics backwards on each cycle.

### A sensor whose value is a forecast

**Tests:** `test_a_forecast_never_carries_a_state_class`

Leave `state_class` unset and publish the caveat as an attribute. A revising forecast in long-term statistics corrupts the series.

### Any entity

**Tests:** `test_every_declared_translation_key_has_a_name`, `test_every_declared_key_has_an_icon`

Add entries under **that entity's own platform** in `strings.json`, `translations/en.json` and `icons.json`. Keys are read from **module source**, matching both `translation_key=` in a description and `_attr_translation_key` on a class, so a single-instance entity is covered the same way.

### Removing an entity

**Tests:** `test_no_dead_translation_entries`, `test_no_dead_icon_entries`

Remove its entries too. A dead entry costs nothing at runtime, which is exactly why it is never noticed — and it makes every count in `docs/all_sensors.md` wrong.

### A raised `HomeAssistantError`

**Tests:** `test_every_raised_exception_key_has_a_message`, `test_no_dead_exception_messages`

Add the key to the `exceptions` block in **both** translation files. Checked in both directions.

### An entity attribute

**Tests:** `test_no_entity_publishes_a_recorded_attribute`

Add the key to that class's `_unrecorded_attributes`. **Repeat `"about"` if the class declares its own set** — HA does not merge this across the hierarchy, so a subclass assignment shadows the mixin's entirely.

### A credential field in any config-flow schema

**Tests:** `test_stored_secrets_are_never_pre_filled`, `test_no_field_leaks_a_stored_secret`

Never seed it from stored options — not as `default` and not as `suggested_value`. The failure is silent: the screen looks right and the value is exposed only when someone clicks the eye icon. Two projects in this family have shipped exactly this.

### A new write command in `api.py`

**Tests:** `test_every_write_is_classified`, `test_every_entry_carries_a_written_reason`

Add it to `scripts/write_classification.py` as `SAFE`, `ATTENDED` or `NEVER_AUTOMATED`, **with a written reason**. Classify it `SAFE` and `test_every_safe_write_is_exercised_by_the_hardware_check` additionally requires `scripts/hardware_check.py` to actually send it. The detector keys on the **endpoint, not the verb** — this controller answers queries with `POST`, so five read methods would otherwise be reported as writes.

### A new repair issue

**Tests:** `test_repair_issue_names_cover_both_repairs`

Add the name to `REPAIR_ISSUE_NAMES` in `const.py` and raise it through `repair_issue_id(entry_id, name)`. The list is what `_clear_repair_issues` sweeps on teardown; a repair missing from it survives the integration being deleted, with nothing left that could ever clear it.

### A test with no assertion

**Tests:** the assertion audit (`python .workbench/check_test_assertions.py`)

Assert the observable outcome — nothing cancelled, nothing written, the error logged. It currently reports **0 of 802**, and there is no allow-list file because every case turned out to have one. Report-only, so read the PASSED/FAILED line rather than the exit code.

### **Any new partial branch**

**Tests:** branch coverage (`pytest --cov --cov-branch`)

**The bar is zero.** As of `[1.0.1]` this project is at **100% line and 100% branch, 0 partials** — so a partial is now a signal rather than noise, and "it was already like that" is no longer an answer. Treat each as a missing test until proved otherwise: measured 12-of-12 on WiFi, 11-of-11 on ZTE and 33-of-33 here, with not one dead guard between them. If a branch really is unreachable, **delete it** rather than leaving it to erode the number — the five removed at `[1.0.1]` were `isinstance(x, list)` checks on payloads `_fetch_optional` had already normalized with `list()`. `# pragma: no cover` changes the denominator instead of testing anything; the count stays at 1 unless there is a written reason.

### Any branch in a `for` loop guard

**Tests:** branch coverage (`pytest --cov --cov-branch`)

Use **at least two** items with the unwanted one **first**, and assert the later item was still processed. With one item, "skipped and continued" and "skipped and stopped" are indistinguishable. `--cov-branch` is a flag in `.vscode/tasks.json`, **not** in `pyproject.toml` — a plain `pytest --cov` reports no partials at all and every module looks clean.

---

## Guards Added to the Table (2026-09-23)

Tests that fire on an ordinary change and were not previously listed. Each rationale is the test's docstring.

### `test_health_detail_is_unrecorded`

The health sensor's detail churns with every failure. Kept as a cheap static assertion alongside the sweep: this is the entity whose attributes change most often, and the one whose contract Section 19 pins by name.

### `test_rogue_proximity_rssi_is_unrecorded`

`strongest_rogue_rssi` moves on every poll. Regression guard for a specific miss: the gateway sensor excluded `rogue_aps` for exactly this reason, but the reasoning was never carried across to the proximity sensor, which declared no set of its own.

### `test_gateway_sensor_records_nothing`

Version/build/type were recorded because the set was never extended.

---

## Guards Added in `1.1.1-dev3` (2026-10-15)

Each was verified to fail by breaking what it guards before it was recorded (v1.1.1 plan E28).

### Every entity has a device

`test_every_live_entity_belongs_to_a_device` sweeps the constructed entities, because `device_info` is a property on the entity class and no description can carry it. An entity without a device is not rejected by Home Assistant; it registers and belongs to no device card. `test_device_info_is_declared_once` takes this project's form of the family rule: two device shapes, the entry sub-devices and the monitored network devices, each built once in `helpers.py` (`every_entity_must_have_a_device.md`).

### Icons on live entities and actions

`test_every_live_entity_has_an_icon_or_a_device_class` looks each live entity's key up under its own platform, so a key filed under another platform fails rather than passes; the static key check does not see that. `test_action_icons_use_the_current_nested_form` holds the `{"service": ...}` form Home Assistant documents, which the family shares (`C-031`).

### Suppressions

A suppression hides what a tool would have said. `RUF100` and mypy's `warn_unused_ignores` report one that is unnecessary and say nothing about one that is doing work. In `huawei_router_5g` two such suppressions hid calls to methods the library did not have (`C-004`). The allow-list is keyed on file and directive, so a second identical directive in a listed file passes unseen; that is the family design.

### Device-registry surfaces only in `_compat`

`async_get_device(`, `DeviceEntry.config_entries` and `via_device` are deprecated in Home Assistant 2026.8 and removed in 2027.8 and 2027.10. `1.1.0-dev12` shipped a direct call in `identity.py` that passed every check (`C-038`). The guard reads the syntax tree, so the config-entry manager and comments are not flagged.

### Repair text, firing fixtures and severity vocabulary

The repair text sweeps catch a card that renders its raw key, a translation that drops a placeholder, and text left for a key nothing raises. `test_every_check_has_a_firing_fixture` requires the real code to raise each repair from a fixture, three of them through the HTTP seam in `tests/transport.py`. The severity sweep asserts the published strings, not the constants, because a rename would pass a comparison with the constant while user automations matching on `severity` broke (`C-022` step 8).
