# flow-review M3 (Mobile, Maestro) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Each task names its executor model; dispatch it pinned to that model, never `inherit`. Opus reviews every checkpoint.

**Goal:** Drive Android apps under Expo Go through Maestro, reusing the M1 `drive`/`replay` verb set and finding rules so the explorer, lens and cold-eyes agents work on mobile the same way they work on web.
**Architecture:** A new `mobile/` package implements the M3-introduced `Driver` protocol (`flow_review/driver.py`) the same way `web/driver.py::WebDriver` does; `DriveSession` and `replay` gain one dispatch point each keyed on `surface.driver`. The engine never boots an emulator or installs Maestro (A-38); it only shells out to `adb`/`maestro` and parses their output.
**Tech Stack:** Python 3, `subprocess` (no new dependency), Maestro CLI + `adb` (user-installed), Expo (fixture app only).
**Spec:** `docs/superpowers/specs/2026-09-23-flow-review-v2-design.md` §3, §5, §6, §7, §9, §10, §12, §13.

## Global Constraints

- The engine never calls an LLM API. flow-review never edits product code. Agents drive a surface only through engine CLI verbs (A-24 `drive` pattern).
- Executor tags: **haiku** = mechanical, **sonnet** = standard TDD feature, **opus** = cross-cutting/high-judgment. Opus reviews the checkpoint.
- Every task that adds code states its ponytail rung (1 skip / 2 stdlib / 3 native platform / 4 installed dep / 5 one line / 6 minimum code). Deliberate shortcuts carry a `# ponytail:` comment naming the ceiling.
- No tests require a real device or a real Maestro/adb install: every test mocks `subprocess.run` with a recorded output string kept in the test file.
- Distribution stays GitHub-only (A-27); nothing here changes install.
- Parallel lanes: tasks with disjoint file sets may run at once, at most 3 lanes per phase. Never parallelize tasks sharing a file.
- Run tests from the repo root: `python -m pytest -q -m "web or not web"`.

## File Structure (target)

```
plugins/flow-review/engine/flow_review/
  driver.py                 # NEW: Driver protocol (A-47)
  config.py                 # + maestro driver, MAESTRO_OPTION_KEYS
  audit.py                  # _from_expo promotes to driver "maestro"
  drift.py                  # unchanged (RUNNABLE_DRIVERS already includes "maestro" post-M2)
  envsetup.py               # + maestro/adb setup-env checks
  prove.py                  # + maestro proof branch
  plan.py                   # unchanged (unit template reused as-is)
  mobile/
    __init__.py
    maestro.py               # NEW: hierarchy, run_flow, screenshot, density, devices
    driver.py                 # NEW: MobileDriver (Driver protocol)
    measure.py                 # NEW: check_hierarchy, screen_route
    yaml.py                     # NEW: to_maestro
    test_maestro.py
    test_driver.py
    test_measure.py
    test_yaml.py
  web/
    drive.py                  # DriveSession dispatches measure hook by driver
    replay.py                 # replay() dispatches maestro flows
  fixtures/
    mobileapp/                 # NEW: Expo fixture app + planted.json + README
plugins/flow-review/skills/flow-review/
  references/testing.md        # mobile section
  references/evidence.md       # mobile evidence bundle
  references/surfaces.md       # driver: maestro replaces the adb stub
  SKILL.md                     # mobile prerequisite checklist
plugins/flow-review/agents/
  fr-explorer.md
  fr-lens.md
```

## Task Skeleton

| id | goal (one line) | deps | wave | owner | exec |
|---|---|---|---|---|---|
| T1 | Config + detection: driver `maestro`, `MAESTRO_OPTION_KEYS`, `audit._from_expo` promotes to `maestro` (M2's `RUNNABLE_DRIVERS` already includes it) | — | 1 | D1 | sonnet |
| T2 | Mobile fixture `engine/fixtures/mobileapp` + `planted.json` + existence test | — | 1 | D1 | haiku |
| T3 | `mobile/maestro.py`: `hierarchy`, `run_flow`, `screenshot`, `density`, `devices`, all via mocked `subprocess.run` | — | 1 | D2 | sonnet |
| T4 | Setup + prove: `setup-env` Maestro/adb gaps; `prove` for `maestro` = device + `hierarchy` | T1, T3 | 2 | D1 | sonnet |
| T5 | `flow_review/driver.py::Driver` Protocol (A-47); `WebDriver` conformance test; `DRIVER_FACTORIES["maestro"]` | T1 | 2 | D2 | sonnet |
| T6 | `mobile/driver.py::MobileDriver` (A-47 methods over generated single-step YAML) | T3, T5 | 3 | D2 | sonnet |
| T7 | `mobile/measure.py::check_hierarchy` + `DriveSession` dispatch by driver | T6 | 4 | D2 | sonnet |
| T8 | Recording + replay: `mobile/yaml.py::to_maestro`, `flow-end` writes `.yaml`, `replay` runs `maestro test` for maestro surfaces | T7 | 5 | D2 | opus |
| T9 | Agent briefs + references: `testing.md`, `evidence.md`, `surfaces.md`, `fr-explorer.md`, `fr-lens.md`; `test_cli_parity` green | T8 | 6 | D3 | haiku |
| T10 | SKILL.md mobile prerequisites + `plan.py` GO-gate gap `device-missing` | T9 | 7 | D3 | sonnet |
| CP1 | M3 checkpoint | T1-T10 | 8 | — | opus |

## Lanes

Phase 1 (wave 1): lane A = T1, lane B = T2, lane C = T3. Disjoint files (`config.py`+`audit.py`+`drift.py` / `fixtures/mobileapp/` / `mobile/maestro.py`).
Lanes merge here: T4 and T5 both depend on wave 1 output.

Phase 2 (wave 2): lane A = T4 (`envsetup.py`, `prove.py`), lane B = T5 (`flow_review/driver.py`, `web/driver.py`, `web/drive.py`'s factory dict). Disjoint files.
Lanes merge here: T6 needs both T3 (maestro.py) and T5 (Driver protocol + factory).

Phase 3 (wave 3-5): T6 -> T7 -> T8, sequential (each edits `mobile/driver.py`/`mobile/measure.py`/`web/drive.py`/`web/replay.py` in turn; T7 depends on T6's `MobileDriver`, T8 depends on T7's `check_hierarchy`).

Phase 4 (wave 6-7): T9 -> T10, sequential (T10's SKILL.md edit follows T9's references so both stay consistent).

CP1 after T1-T10.

## Canonical Interfaces

Reused from the shared cross-milestone list (do not rename):
- `flow_review/driver.py::Driver` (typing.Protocol): `launch(base_url)`, `close()`, `goto(path)`, `click(locator)`, `fill(locator, value, secret)`, `press(key)`, `screenshot(path)`, `snapshot()`, `is_password(locator)`, `begin_step(i)`, `end_step()`, `console_errors_since_check()`, `network_log_since_check()`.
- `mobile/driver.py::MobileDriver(app_id, device, run_dir)` implements `Driver`.
- `config.VALID_DRIVERS` gains `maestro`; `MAESTRO_OPTION_KEYS = ("app_id", "device", "start_cmd")`.
- `drift.RUNNABLE_DRIVERS` (already `("playwright", "tauri", "maestro", "http", "shell")` post-M2; unchanged here).
- `DRIVER_FACTORIES["maestro"]` in `web/drive.py`.
- `web/drive.py::serve(surface_id, run_dir, project_root, base_url, *, driver_name="playwright", options=None, ...)` and `cmd_start`'s `--driver`/`--driver-options` flags (M2-introduced, canonical through M4).

New in this plan:
- `mobile/maestro.py::hierarchy(device: str | None) -> dict`, `run_flow(yaml_path: Path, device: str | None, env: dict | None = None, runner=subprocess.run) -> MaestroResult` (`TypedDict: ok: bool, failed_step: int | None, output: str`; `env` becomes `-e KEY=VALUE` pairs on the `maestro` command line, used to pass a secret fill value without ever writing it into the flow YAML), `screenshot(path, device) -> Path`.
- `mobile/maestro.py::density(device: str | None) -> int` -- pixels-per-dp for the given device (`adb shell wm density`); default `160` (1 dp = 1 px) when the device reports nothing parseable.
- `mobile/maestro.py::devices() -> list[str]` -- serials from `adb devices` with state `device` (skips `offline`/`unauthorized`).
- `mobile/yaml.py::locator_to_maestro(locator: dict) -> dict` -- the M1 semantic locator (`{"role","name"}` / `{"testid"}` / `{"css"}`) mapped to a Maestro selector (`{"text": name}` / `{"id": testid}`); raises `flow_review.web.driver.LocatorNotFound` for `{"css": ...}`.
- `mobile/yaml.py::to_maestro(log: dict, app_id: str) -> str` -- `app_id` is always the surface's `options["app_id"]` (a package id like `com.example.app`), never `log["surface_id"]` (a flow-review surface id like `"mobile"`); a `from_env` fill step is written as `inputText: ${<ENV_NAME>}`, never the resolved value.
- `mobile/measure.py::check_hierarchy(tree: dict, surface_id: str, flow_id: str, route: str, density: int = 160) -> list[Finding]` -- `rect.target-size` is computed over clickable nodes only; `rect.overlap` is computed over every node that has parseable `bounds`, clickable or not (a non-interactive badge sitting on top of a button is still an overlap defect).
- `mobile/measure.py::screen_route(tree: dict, app_id: str) -> str` -- the current screen's route label for a maestro surface: the first node with non-empty `text` and parseable `bounds`, ordered top-left first (`(y, x)` ascending); `app_id` if the tree has no such node.
- Mobile evidence refs (extends the shared cross-milestone "Evidence refs" entry): `mobile/<flow_id>/<step>.png` (a screenshot via `MobileDriver.screenshot`) and `mobile/<flow_id>/<step>.json` (the hierarchy tree at that step, `json.dumps` truncated to its first 4000 characters) -- both are written once per drive step on a maestro session and appended to the `evidence` list of every finding filed on that step, before the finding is written to `events.jsonl` (evidence cannot be added to an event after `events.append` -- the JSONL line is already on disk).

## Tasks

### Task T1: Config + detection for the `maestro` driver

**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/config.py`, `plugins/flow-review/engine/flow_review/test_config.py`, `plugins/flow-review/engine/flow_review/audit.py`, `plugins/flow-review/engine/flow_review/test_audit.py`, `plugins/flow-review/engine/flow_review/test_drift.py` (regression check only; `drift.py` itself is not edited)
**Interfaces:** Consumes: `config.Surface`, `audit.Candidate` (both already carry the fields this task needs: M2 added `Candidate.options: dict` for the `tauri` candidate), `drift.RUNNABLE_DRIVERS` (already includes `maestro` post-M2 T4; read-only here). Produces: `config.VALID_DRIVERS` (+ `maestro`), `config.MAESTRO_OPTION_KEYS`, `audit._from_expo` (promotes to `maestro`).
**Ponytail rung:** 6 (minimum code: three small, independent additions, no new abstraction).

- [ ] Write the failing tests.

```python
# plugins/flow-review/engine/flow_review/test_config.py -- append
def test_maestro_driver_accepts_its_option_keys():
    surface = Surface(
        id="mobile", name="Mobile", kind="ui", driver="maestro", launch="",
        options={"app_id": "com.example.app", "device": "emulator-5554",
                 "start_cmd": "npx expo start --android"},
    )
    _validate_surface(surface)  # must not raise


def test_maestro_driver_rejects_an_unknown_option_key():
    surface = Surface(id="mobile", name="Mobile", kind="ui", driver="maestro", launch="",
                       options={"bogus": 1})
    with pytest.raises(ConfigKeyError):
        _validate_surface(surface)


def test_valid_drivers_includes_maestro():
    assert "maestro" in VALID_DRIVERS
```

```python
# plugins/flow-review/engine/flow_review/test_audit.py -- append
def test_expo_app_json_promotes_to_maestro_driver_with_android_package(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({
        "expo": {"name": "demo", "android": {"package": "com.example.demo"}},
    }), encoding="utf-8")
    found = [c for c in audit.detect(tmp_path) if c.name == "mobile"]
    assert len(found) == 1
    candidate = found[0]
    assert candidate.driver == "maestro"
    assert candidate.launch == "npx expo start --android"
    assert candidate.options == {
        "app_id": "com.example.demo", "start_cmd": "npx expo start --android",
    }


def test_expo_app_json_without_android_package_falls_back_to_expo_go_id(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"expo": {"name": "demo"}}), encoding="utf-8")
    found = [c for c in audit.detect(tmp_path) if c.name == "mobile"]
    assert found[0].options["app_id"] == "host.exp.exponent"


def test_a_plain_app_json_with_no_expo_key_is_not_detected(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")
    found = audit.detect(tmp_path)
    assert not any(c.name == "mobile" for c in found)
```

```python
# plugins/flow-review/engine/flow_review/test_drift.py -- append
def test_runnable_drivers_already_includes_maestro():
    assert "maestro" in RUNNABLE_DRIVERS
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/test_drift.py`
      Expected FAIL: `test_maestro_driver_accepts_its_option_keys` and `test_valid_drivers_includes_maestro` fail (`maestro` not a valid driver / `MAESTRO_OPTION_KEYS` undefined); `test_expo_app_json_promotes_to_maestro_driver_with_android_package` fails (`candidate.driver == "pending"`); `test_runnable_drivers_already_includes_maestro` should already pass against the landed M2 `RUNNABLE_DRIVERS` -- if it fails, `drift.py` has drifted from the M2 plan and that is a stop-the-line finding for this task, not something to patch around here.

- [ ] Implement (complete).

In `config.py`, replace:
```python
VALID_DRIVERS = ("cdp", "playwright", "tauri", "adb", "ios-sim", "shell", "http", "custom", "pending")
```
with:
```python
VALID_DRIVERS = (
    "cdp", "playwright", "tauri", "maestro", "adb", "ios-sim", "shell", "http", "custom", "pending",
)
```
Add, next to `WEB_OPTION_KEYS`:
```python
MAESTRO_OPTION_KEYS = ("app_id", "device", "start_cmd")
```
`_validate_options` already dispatches by driver (M2); add the `maestro` branch so the function reads:
```python
_OPTION_KEYS_BY_DRIVER = {
    "playwright": WEB_OPTION_KEYS,
    "tauri": TAURI_OPTION_KEYS,
    "maestro": MAESTRO_OPTION_KEYS,
}


def _validate_options(surface: Surface) -> None:
    where = f"surfaces[{surface.id!r}].options"
    allowed = _OPTION_KEYS_BY_DRIVER.get(surface.driver)
    if allowed is not None:
        _check_keys(surface.options, set(allowed), where)
    elif surface.options:
        _check_keys(surface.options, set(), where)
```

In `audit.py`, `Candidate` already carries `options: dict` (M2, default `field(default_factory=dict)`); replace `_from_expo`:
```python
_EXPO_GO_APP_ID = "host.exp.exponent"
_EXPO_START_CMD = "npx expo start --android"


def _from_expo(root: Path) -> list[Candidate]:
    path = root / "app.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    expo = data.get("expo")
    if not isinstance(expo, dict):
        return []
    app_id = ((expo.get("android") or {}).get("package")) or _EXPO_GO_APP_ID
    return [Candidate(
        name="mobile", kind="ui", driver="maestro", launch=_EXPO_START_CMD,
        evidence=_evidence(path, root, None, ""),
        options={"app_id": app_id, "start_cmd": _EXPO_START_CMD},
    )]
```
Update the now-obsolete `test_expo_app_json_is_pending_driver` in `test_audit.py`: delete it (superseded by the two new tests above, which assert `driver == "maestro"` for the same fixture shape).

`drift.RUNNABLE_DRIVERS` is already `("playwright", "tauri", "maestro", "http", "shell")` after M2 T4 and `runnable_surfaces` already reads:
```python
def runnable_surfaces(cfg: Config) -> list[Surface]:
    return [s for s in cfg.surfaces if not s.declined and s.driver in RUNNABLE_DRIVERS]
```
No change to `drift.py` in this task; the `test_runnable_surfaces_includes_a_maestro_surface` test above (a one-line `"maestro" in RUNNABLE_DRIVERS` assertion) is a passing regression check, not new behavior.

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/test_drift.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/audit.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/test_drift.py && git commit -m "feat(config): promote Expo app.json to the maestro driver"`

### Task T2: Mobile fixture app

**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/fixtures/mobileapp/` (new directory: `app.json`, `package.json`, `App.js`, `screens/Home.js`, `screens/List.js`, `screens/Detail.js`, `README.md`, `planted.json`), `plugins/flow-review/engine/flow_review/test_fixtures.py`
**Interfaces:** Consumes: none. Produces: the fixture `planted.json` shape the M5 bench harness will read later (`[{"rule", "route", "locator"}]`, per the cross-milestone Canonical Interfaces "Bench" entry) -- M3 only needs the file to exist and parse.
**Ponytail rung:** 5 (one small React Native app, no build tooling beyond what Expo itself needs).

- [ ] Write the failing test.

```python
# plugins/flow-review/engine/flow_review/test_fixtures.py -- new file
import json
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures" / "mobileapp"


def test_mobileapp_fixture_files_exist():
    for name in ("app.json", "package.json", "App.js", "planted.json", "README.md"):
        assert (FIXTURE / name).is_file(), name


def test_mobileapp_app_json_declares_expo_and_android_package():
    data = json.loads((FIXTURE / "app.json").read_text(encoding="utf-8"))
    assert data["expo"]["android"]["package"] == "dev.flowreview.mobileapp"


def test_mobileapp_planted_json_lists_the_two_benchmarked_defects():
    # The dead "Refresh" button is a judgment finding (README), never benchmarked, so it is not
    # in planted.json: bench (M5) can only score a rule id it can look up mechanically.
    planted = json.loads((FIXTURE / "planted.json").read_text(encoding="utf-8"))
    rules = {p["rule"] for p in planted}
    assert rules == {"rect.target-size", "rect.overlap"}
    for entry in planted:
        assert {"rule", "route", "locator"} <= entry.keys()
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_fixtures.py`
      Expected FAIL: `FileNotFoundError`/`ModuleNotFoundError` collection error -- the fixture directory does not exist.

- [ ] Implement (complete).

```json
// plugins/flow-review/engine/fixtures/mobileapp/app.json
{
  "expo": {
    "name": "mobileapp",
    "slug": "mobileapp",
    "version": "1.0.0",
    "orientation": "portrait",
    "android": {
      "package": "dev.flowreview.mobileapp"
    }
  }
}
```

`package.json`'s dependency versions are never hand-picked: they come from running the Expo CLI's
own resolver, which pins whatever versions are current and mutually compatible for the installed
Expo SDK. Generate the fixture with:
```
npx create-expo-app@latest mobileapp --template blank
cd mobileapp
npx expo install react-native-screens react-native-safe-area-context \
  @react-navigation/native @react-navigation/native-stack
```
then replace the generated `App.js` and add `screens/` as shown below, and commit the resulting
`package.json` verbatim -- do not hand-edit any version number in it. The shape below is what
those commands produce as of the current Expo SDK; if a real run of the commands resolves
different exact versions, commit those instead of the ones shown here.
```json
// plugins/flow-review/engine/fixtures/mobileapp/package.json
{
  "name": "mobileapp",
  "version": "1.0.0",
  "private": true,
  "main": "App.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android"
  },
  "dependencies": {
    "expo": "~51.0.0",
    "expo-status-bar": "~1.12.1",
    "react": "18.2.0",
    "react-native": "0.74.0",
    "react-native-screens": "~3.31.1",
    "react-native-safe-area-context": "4.10.5",
    "@react-navigation/native": "^6.1.0",
    "@react-navigation/native-stack": "^6.9.0"
  }
}
```

```javascript
// plugins/flow-review/engine/fixtures/mobileapp/App.js
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import Home from './screens/Home';
import List from './screens/List';
import Detail from './screens/Detail';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Home">
        <Stack.Screen name="Home" component={Home} />
        <Stack.Screen name="List" component={List} />
        <Stack.Screen name="Detail" component={Detail} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

```javascript
// plugins/flow-review/engine/fixtures/mobileapp/screens/Home.js
import { View, Text, Pressable, StyleSheet } from 'react-native';

// Planted defect 1 (rect.target-size, benchmarked in planted.json): a 32x32dp icon button,
// below the 48dp minimum. "Refresh" is a judgment finding only (README): wired to nothing, but
// not mechanically checkable, so it is deliberately absent from planted.json (A-59 dead-control
// note). The "Home" heading is the screen's first visible text, top-left -- mobile/measure.py's
// screen_route() reads it as this screen's route, so it must stay first in this file's layout
// and its literal text must stay exactly "Home" to match planted.json's route.
export default function Home({ navigation }) {
  return (
    <View style={styles.container} testID="home-screen">
      <Text style={styles.title}>Home</Text>
      <Pressable
        testID="open-list"
        onPress={() => navigation.navigate('List')}
        style={styles.bigButton}
      >
        <Text>Open list</Text>
      </Pressable>
      <Pressable testID="icon-button" style={styles.tinyIcon}>
        <Text>i</Text>
      </Pressable>
      <Pressable testID="refresh-button" onPress={() => {}} style={styles.bigButton}>
        <Text>Refresh</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  title: { fontSize: 20, fontWeight: 'bold' },
  bigButton: { width: 160, height: 48, alignItems: 'center', justifyContent: 'center' },
  tinyIcon: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
});
```

```javascript
// plugins/flow-review/engine/fixtures/mobileapp/screens/List.js
import { View, Text, FlatList, Pressable, StyleSheet } from 'react-native';

const ITEMS = [
  { id: '1', title: 'Item 1' },
  { id: '2', title: 'Item 2' },
  { id: '3', title: 'Item 3' },
];

// Planted defect 2 (rect.overlap, benchmarked in planted.json): the badge sits on top of the
// row's own button. The badge is a Pressable (not a plain View) even though it does nothing on
// tap, specifically so a real Maestro run's hierarchy marks it clickable="true" the same way a
// real "new" chip that swallowed a tap gesture would -- rect.overlap is computed over every
// bounded node regardless of clickability (mobile/measure.py), so this only affects realism, not
// whether the rule fires; it exists so a manual run against the real emulator sees the same
// interactive-looking element a tester would tap by mistake. "List" is this screen's first
// visible text, top-left, matching planted.json's route and screen_route()'s heuristic.
export default function List({ navigation }) {
  return (
    <View style={styles.container} testID="list-screen">
      <Text style={styles.heading}>List</Text>
      <FlatList
        data={ITEMS}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Pressable
              testID={`row-${item.id}`}
              onPress={() => navigation.navigate('Detail', { id: item.id })}
              style={styles.rowButton}
            >
              <Text>{item.title}</Text>
            </Pressable>
            <Pressable style={styles.badge} testID={`badge-${item.id}`}>
              <Text>new</Text>
            </Pressable>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  heading: { fontSize: 20, fontWeight: 'bold', padding: 12 },
  row: { height: 56, justifyContent: 'center' },
  rowButton: { position: 'absolute', left: 0, right: 0, top: 0, height: 56 },
  badge: { position: 'absolute', right: 8, top: 16, width: 40, height: 24 },
});
```

```javascript
// plugins/flow-review/engine/fixtures/mobileapp/screens/Detail.js
import { View, Text, StyleSheet } from 'react-native';

// "Detail" (not "Detail for item N") is this screen's first visible text, top-left, so
// screen_route() reads exactly "Detail" -- matching planted.json's route, if a defect is ever
// planted on this screen in a later fixture revision.
export default function Detail({ route }) {
  return (
    <View style={styles.container} testID="detail-screen">
      <Text style={styles.title}>Detail</Text>
      <Text>Detail for item {route.params?.id}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: 'bold' },
});
```

```json
// plugins/flow-review/engine/fixtures/mobileapp/planted.json
[
  {"rule": "rect.target-size", "route": "Home", "locator": "testid:icon-button"},
  {"rule": "rect.overlap", "route": "List", "locator": "testid:row-1"}
]
```

```markdown
<!-- plugins/flow-review/engine/fixtures/mobileapp/README.md -->
# mobileapp fixture (M3)

A minimal Expo app (Home, List, Detail) used to exercise the `maestro` driver.

## Run it

    cd plugins/flow-review/engine/fixtures/mobileapp
    npm install
    npx expo start --android

Requires an already-running Android emulator (`adb devices` shows one `device` line)
and Expo Go installed in it.

## Planted defects (see `planted.json`)

1. `icon-button` on Home is 32x32dp -- below the 48dp minimum tap target (`rect.target-size`).
2. `row-1`'s badge on List overlaps its own row button (`rect.overlap`).

## Expected judgment finding (not in `planted.json`)

`refresh-button` on Home is wired to nothing ("looks actionable, does nothing"). This is not a
rule the engine checks mechanically, so it is deliberately absent from `planted.json` -- a lens
or cold-eyes agent is expected to notice it and file a judgment finding, or the run reports it as
`not-exercised`; either is a pass, a silent miss is not.
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_fixtures.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/fixtures/mobileapp plugins/flow-review/engine/flow_review/test_fixtures.py && git commit -m "test(fixtures): add the mobileapp Expo fixture for M3"`

### Task T3: `mobile/maestro.py` -- Maestro/adb subprocess wrapper

**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/mobile/__init__.py`, `plugins/flow-review/engine/flow_review/mobile/maestro.py`, `plugins/flow-review/engine/flow_review/mobile/test_maestro.py`
**Interfaces:** Consumes: `subprocess.run` (injected as `runner` for testability, matching `envsetup.py`'s pattern). Produces: `mobile/maestro.py::hierarchy`, `run_flow`, `screenshot`, `density`, `devices`, `MaestroResult`.
**Ponytail rung:** 4 (installed dep: the Maestro/adb CLIs the user already installed per A-38; no Python wrapper library).

- [ ] Write the failing test.

```python
# plugins/flow-review/engine/flow_review/mobile/test_maestro.py -- new file
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow_review.mobile import maestro

ADB_DEVICES_OUTPUT = (
    "List of devices attached\n"
    "emulator-5554\tdevice\n"
    "emulator-5556\toffline\n"
    "\n"
)

WM_DENSITY_OUTPUT = "Physical density: 420\n"

HIERARCHY_JSON = json.dumps({
    "attributes": {"text": "", "resource-id": "", "bounds": "[0,0][1080,2280]",
                    "clickable": "false", "enabled": "true", "focused": "false"},
    "children": [
        {"attributes": {"text": "Open list", "resource-id": "open-list",
                         "bounds": "[100,200][400,300]", "clickable": "true",
                         "enabled": "true", "focused": "false"},
         "children": []},
    ],
})

MAESTRO_TEST_FAILURE_OUTPUT = (
    "Running flow.yaml\n"
    " -  Launch app\n"
    " -  Tap on \"Open list\"\n"
    " -  [3] Tap on \"Missing\"\n"
    "    FAILED: Element not found\n"
)


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _RecordingRunner:
    def __init__(self, outputs: dict[tuple[str, ...], _FakeCompleted]):
        self.outputs = outputs
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return self.outputs[tuple(cmd)]


def test_devices_lists_only_device_state_serials():
    runner = _RecordingRunner({
        ("adb", "devices"): _FakeCompleted(0, ADB_DEVICES_OUTPUT),
    })
    assert maestro.devices(runner=runner) == ["emulator-5554"]


def test_density_parses_physical_density_line():
    runner = _RecordingRunner({
        ("adb", "-s", "emulator-5554", "shell", "wm", "density"):
            _FakeCompleted(0, WM_DENSITY_OUTPUT),
    })
    assert maestro.density("emulator-5554", runner=runner) == 420


def test_density_defaults_to_160_when_unparseable():
    runner = _RecordingRunner({
        ("adb", "-s", "emulator-5554", "shell", "wm", "density"): _FakeCompleted(0, ""),
    })
    assert maestro.density("emulator-5554", runner=runner) == 160


def test_hierarchy_parses_maestro_json_output():
    runner = _RecordingRunner({
        ("maestro", "--device", "emulator-5554", "hierarchy"):
            _FakeCompleted(0, HIERARCHY_JSON),
    })
    tree = maestro.hierarchy("emulator-5554", runner=runner)
    assert tree["children"][0]["attributes"]["text"] == "Open list"


def test_run_flow_ok_when_maestro_exits_zero(tmp_path):
    flow = tmp_path / "flow.yaml"
    flow.write_text("appId: com.example\n---\n- launchApp\n", encoding="utf-8")
    runner = _RecordingRunner({
        ("maestro", "--device", "emulator-5554", "test", str(flow)):
            _FakeCompleted(0, "Running flow.yaml\n -  Launch app\n"),
    })
    result = maestro.run_flow(flow, "emulator-5554", runner=runner)
    assert result == {"ok": True, "failed_step": None, "output": "Running flow.yaml\n -  Launch app\n"}


def test_run_flow_passes_env_as_dash_e_pairs(tmp_path):
    flow = tmp_path / "flow.yaml"
    flow.write_text("appId: com.example\n---\n- launchApp\n", encoding="utf-8")
    runner = _RecordingRunner({
        ("maestro", "--device", "emulator-5554", "-e", "FR_SECRET=hunter2", "test", str(flow)):
            _FakeCompleted(0, ""),
    })
    result = maestro.run_flow(flow, "emulator-5554", env={"FR_SECRET": "hunter2"}, runner=runner)
    assert result["ok"] is True


def test_run_flow_reports_the_failed_step_index():
    flow = Path("flow.yaml")
    runner = _RecordingRunner({
        ("maestro", "--device", "emulator-5554", "test", str(flow)):
            _FakeCompleted(1, MAESTRO_TEST_FAILURE_OUTPUT),
    })
    result = maestro.run_flow(flow, "emulator-5554", runner=runner)
    assert result["ok"] is False
    assert result["failed_step"] == 3


def test_screenshot_calls_maestro_and_returns_the_path(tmp_path):
    out = tmp_path / "shot.png"
    runner = _RecordingRunner({
        ("maestro", "--device", "emulator-5554", "screenshot", str(out)): _FakeCompleted(0, ""),
    })
    assert maestro.screenshot(out, "emulator-5554", runner=runner) == out
    assert runner.calls == [["maestro", "--device", "emulator-5554", "screenshot", str(out)]]
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_maestro.py`
      Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.mobile'`.

- [ ] Implement (complete).

```python
# plugins/flow-review/engine/flow_review/mobile/__init__.py
```

```python
# plugins/flow-review/engine/flow_review/mobile/maestro.py
"""Thin wrapper over the user-installed Maestro/adb CLIs (A-38). Every function takes an
injectable `runner` (default `subprocess.run`) so the whole module is testable without a real
device -- the same pattern as `flow_review.envsetup`."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import TypedDict

DEFAULT_DENSITY = 160


class MaestroResult(TypedDict):
    ok: bool
    failed_step: int | None
    output: str


def _run(cmd: list[str], runner) -> subprocess.CompletedProcess:
    return runner(cmd, capture_output=True, text=True)


def devices(runner=subprocess.run) -> list[str]:
    result = _run(["adb", "devices"], runner)
    out = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":
            out.append(parts[0])
    return out


def density(device: str | None, runner=subprocess.run) -> int:
    cmd = ["adb"] + (["-s", device] if device else []) + ["shell", "wm", "density"]
    result = _run(cmd, runner)
    match = re.search(r"density:\s*(\d+)", result.stdout, re.IGNORECASE)
    return int(match.group(1)) if match else DEFAULT_DENSITY


def hierarchy(device: str | None, runner=subprocess.run) -> dict:
    cmd = ["maestro"] + (["--device", device] if device else []) + ["hierarchy"]
    result = _run(cmd, runner)
    return json.loads(result.stdout)


# ponytail: best-effort text parse of `maestro test`'s human-readable output ("[<n>] ... FAILED");
# upgrade path is a `--format json` flag if/when Maestro ships one.
_FAILED_STEP_RE = re.compile(r"\[(\d+)\][^\n]*\n\s*FAILED", re.MULTILINE)


def run_flow(yaml_path: Path, device: str | None, env: dict | None = None,
             runner=subprocess.run) -> MaestroResult:
    env_args = []
    for key, value in (env or {}).items():
        env_args += ["-e", f"{key}={value}"]
    cmd = ["maestro"] + (["--device", device] if device else []) + env_args + ["test", str(yaml_path)]
    result = _run(cmd, runner)
    if result.returncode == 0:
        return MaestroResult(ok=True, failed_step=None, output=result.stdout)
    match = _FAILED_STEP_RE.search(result.stdout)
    failed_step = int(match.group(1)) if match else None
    return MaestroResult(ok=False, failed_step=failed_step, output=result.stdout)


def screenshot(path: Path, device: str | None, runner=subprocess.run) -> Path:
    cmd = ["maestro"] + (["--device", device] if device else []) + ["screenshot", str(path)]
    _run(cmd, runner)
    return path
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_maestro.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/mobile/__init__.py plugins/flow-review/engine/flow_review/mobile/maestro.py plugins/flow-review/engine/flow_review/mobile/test_maestro.py && git commit -m "feat(mobile): add the Maestro/adb subprocess wrapper"`

### Task T4: `setup-env` and `prove` for `maestro`

**Executor:** sonnet · **Depends:** T1, T3 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/envsetup.py`, `plugins/flow-review/engine/flow_review/test_envsetup.py`, `plugins/flow-review/engine/flow_review/prove.py`, `plugins/flow-review/engine/flow_review/test_prove.py`
**Interfaces:** Consumes: `mobile.maestro.devices`, `mobile.maestro.hierarchy` (T3), `audit.Candidate` (T1). Produces: `envsetup.check_mobile_tools(runner, which) -> list[str]` (gap messages), `prove.prove_maestro(candidate, device: str | None, runner) -> Proof`-shaped result folded into `prove.prove` via a `candidate.driver == "maestro"` branch.
**Ponytail rung:** 3 (native platform: shells out to the CLIs the platform already provides; no new dependency).

- [ ] Write the failing tests.

```python
# plugins/flow-review/engine/flow_review/test_envsetup.py -- append
def test_check_mobile_tools_reports_missing_maestro_and_adb(monkeypatch):
    def which(name):
        return None
    runner = _RecordingRunner(returncode=1)
    gaps = envsetup.check_mobile_tools(runner=runner, which=which)
    assert any("maestro" in g and "curl -Ls" in g for g in gaps)
    assert any("adb" in g for g in gaps)


def test_check_mobile_tools_reports_no_device_when_adb_devices_is_empty():
    def which(name):
        return f"/usr/bin/{name}"
    runner = _RecordingRunner(returncode=0)
    runner.stdout = "List of devices attached\n\n"
    gaps = envsetup.check_mobile_tools(runner=runner, which=which)
    assert any("no device" in g.lower() for g in gaps)


def test_check_mobile_tools_reports_nothing_when_everything_is_present():
    def which(name):
        return f"/usr/bin/{name}"
    runner = _RecordingRunner(returncode=0)
    runner.stdout = "List of devices attached\nemulator-5554\tdevice\n\n"
    assert envsetup.check_mobile_tools(runner=runner, which=which) == []
```

`_RecordingRunner` in `test_envsetup.py` needs a `stdout` attribute for this task; extend the existing fixture class in place (it is only used by this file's tests):

```python
# plugins/flow-review/engine/flow_review/test_envsetup.py -- replace the existing _FakeCompleted/_RecordingRunner
class _FakeCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class _RecordingRunner:
    def __init__(self, returncode=0, stdout=""):
        self.calls: list[list[str]] = []
        self.returncode = returncode
        self.stdout = stdout

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return _FakeCompleted(self.returncode, self.stdout)
```

```python
# plugins/flow-review/engine/flow_review/test_prove.py -- append
from flow_review.audit import Candidate


class _FakeCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def _mobile_candidate():
    return Candidate(name="mobile", kind="ui", driver="maestro", launch="npx expo start --android",
                      evidence="app.json (file present)",
                      options={"app_id": "dev.flowreview.mobileapp"})


def test_prove_maestro_running_ready_when_device_and_hierarchy_present():
    def runner(cmd, **kwargs):
        if cmd[:2] == ["adb", "devices"]:
            return _FakeCompleted(0, "List of devices attached\nemulator-5554\tdevice\n\n")
        if cmd[0] == "maestro":
            return _FakeCompleted(0, '{"attributes": {}, "children": []}')
        raise AssertionError(cmd)

    result = prove(_mobile_candidate(), Path("."), runner=runner)
    assert result.outcome == RUNNING_READY
    assert result.precondition == "emulator-5554"


def test_prove_maestro_not_proven_when_no_device():
    def runner(cmd, **kwargs):
        if cmd[:2] == ["adb", "devices"]:
            return _FakeCompleted(0, "List of devices attached\n\n")
        raise AssertionError(cmd)

    result = prove(_mobile_candidate(), Path("."), runner=runner)
    assert result.outcome == NOT_PROVEN
    assert "no device" in result.reason.lower()
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_envsetup.py plugins/flow-review/engine/flow_review/test_prove.py`
      Expected FAIL: `AttributeError: module 'flow_review.envsetup' has no attribute 'check_mobile_tools'`; `TypeError: prove() got an unexpected keyword argument 'runner'` (or a `driver_evidence`/`reason` mismatch once `runner` is accepted positionally by an older signature).

- [ ] Implement (complete).

In `envsetup.py`, add (near `find_uv`):
```python
MAESTRO_INSTALL_LINE = (
    'curl -Ls "https://get.maestro.mobile.dev" | bash   '
    '# Windows: iwr -useb "https://get.maestro.mobile.dev" | iex'
)


def check_mobile_tools(runner=subprocess.run, which=shutil.which) -> list[str]:
    """Gaps `setup-env` reports for the maestro driver (A-38). Never installs or launches
    anything; a gap is a line telling the user what to run themselves."""
    gaps: list[str] = []
    if which("maestro") is None:
        gaps.append(f"Maestro is not on PATH. Install it: {MAESTRO_INSTALL_LINE}")
    if which("adb") is None:
        gaps.append(
            "adb is not on PATH. Install the Android SDK platform-tools and add them to PATH."
        )
        return gaps  # the device check below needs adb; nothing more to say without it
    result = runner(["adb", "devices"], capture_output=True, text=True)
    lines = [ln for ln in result.stdout.splitlines()[1:] if ln.strip()]
    if not any(ln.split()[1] == "device" for ln in lines if len(ln.split()) == 2):
        gaps.append(
            "adb reports no device in state 'device'. Start the emulator "
            "(e.g. Pixel_API_35) and wait for it to finish booting."
        )
    return gaps
```

In `prove.py`, add the import `from flow_review.mobile import maestro as mobile_maestro` (local import inside the branch, matching the module's existing style of deferring optional-surface imports), and add a branch parallel to the existing `api` branch inside `prove(...)` -- insert it directly above the `if candidate.kind == "api"` check, and add `runner=subprocess.run` as a keyword parameter of `prove`:

```python
def prove(
    candidate: Candidate,
    root: Path,
    preconditions=(),
    ready_timeout_s: float = 15,
    exit_timeout_s: float = 60,
    runner=subprocess.run,
) -> Proof:
    started = time.monotonic()

    preconditions = list(preconditions)
    validate_preconditions(preconditions)

    if candidate.driver == "maestro":
        from flow_review.mobile import maestro as mobile_maestro
        device_list = mobile_maestro.devices(runner=runner)
        if not device_list:
            return Proof(
                candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
                "no device in state 'device' (adb devices); start the emulator first",
            )
        device = candidate.options.get("device") or device_list[0]
        try:
            tree = mobile_maestro.hierarchy(device, runner=runner)
        except (ValueError, KeyError) as exc:
            return Proof(
                candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
                f"maestro hierarchy did not return a tree: {exc}",
            )
        if not isinstance(tree, dict):
            return Proof(
                candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
                "maestro hierarchy did not return a tree",
            )
        return Proof(
            candidate, RUNNING_READY, None, time.monotonic() - started, "", "", device, True,
            "device attached and maestro hierarchy returned a tree; nothing was launched",
        )
```
Insert the block above immediately after `validate_preconditions(preconditions)` and before the line that currently reads `if candidate.kind == "api" and not candidate.launch.strip():` -- that line, its body, and every line of `prove()` below it are unchanged by this task; only the new `if candidate.driver == "maestro":` block and the new `runner=subprocess.run` parameter on the signature are added. Nothing else in the function moves or is rewritten.

`Proof` is a dataclass with fields, in order: `candidate, outcome, exit_code, duration_s, output_head, output_tail, precondition, teardown_ok, reason`; the positional calls above match it (the device serial goes in `precondition`, as the api branch stores the passing precondition name there).

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_envsetup.py plugins/flow-review/engine/flow_review/test_prove.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/envsetup.py plugins/flow-review/engine/flow_review/test_envsetup.py plugins/flow-review/engine/flow_review/prove.py plugins/flow-review/engine/flow_review/test_prove.py && git commit -m "feat(setup): check Maestro/adb and prove a maestro surface by hierarchy"`

### Task T5: `Driver` Protocol + `DRIVER_FACTORIES["maestro"]`

**Executor:** sonnet · **Depends:** T1 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/driver.py` (new), `plugins/flow-review/engine/flow_review/test_driver_protocol.py` (new), `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/test_drive.py`
**Interfaces:** Consumes: `web/driver.py::WebDriver` (unchanged), `web/drive.py::DRIVER_FACTORIES` and `_default_driver_factory`/`_tauri_driver_factory` (already landed by M2; read/extend only, never redefined). Produces: `flow_review/driver.py::Driver` (A-47 Protocol), `web/drive.py::_maestro_driver_factory` + the `"maestro"` entry in `DRIVER_FACTORIES`, `web/drive.py::build_driver`.
**Ponytail rung:** 2 (stdlib: `typing.Protocol`, no runtime enforcement library).

- [ ] Write the failing tests.

```python
# plugins/flow-review/engine/flow_review/test_driver_protocol.py -- new file
from flow_review.driver import Driver
from flow_review.web.driver import WebDriver


def test_web_driver_conforms_to_the_driver_protocol():
    driver = WebDriver()
    assert isinstance(driver, Driver)


def test_driver_protocol_declares_exactly_the_methods_drivesession_calls():
    expected = {
        "launch", "close", "goto", "click", "fill", "press", "screenshot", "snapshot",
        "is_password", "begin_step", "end_step", "console_errors_since_check",
        "network_log_since_check",
    }
    assert set(Driver.__protocol_attrs__) == expected
```

```python
# plugins/flow-review/engine/flow_review/web/test_drive.py -- append
def test_driver_factories_has_playwright_tauri_and_maestro_entries():
    from flow_review.web.drive import DRIVER_FACTORIES
    assert set(DRIVER_FACTORIES) >= {"playwright", "tauri", "maestro"}


def test_build_driver_dispatches_maestro(monkeypatch):
    from flow_review.web import drive

    created = {}

    def fake_mobile_factory(headless, viewport, options=None):
        created["options"] = options
        return object()

    monkeypatch.setitem(drive.DRIVER_FACTORIES, "maestro", fake_mobile_factory)
    drive.build_driver("maestro", headless=True, viewport=None,
                        options={"app_id": "com.example", "device": "emulator-5554"})
    assert created["options"]["app_id"] == "com.example"


def test_build_driver_dispatches_playwright_uniformly(monkeypatch):
    from flow_review.web import drive

    created = {}

    def fake_playwright_factory(headless, viewport, options=None):
        created["called"] = (headless, viewport, options)
        return object()

    monkeypatch.setitem(drive.DRIVER_FACTORIES, "playwright", fake_playwright_factory)
    drive.build_driver("playwright", headless=True, viewport=None, options={})
    assert created["called"] == (True, None, {})


def test_build_driver_rejects_an_unknown_driver():
    from flow_review.web import drive
    import pytest
    with pytest.raises(ValueError, match="unknown driver"):
        drive.build_driver("bogus", headless=True, viewport=None, options={})
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_driver_protocol.py plugins/flow-review/engine/flow_review/web/test_drive.py`
      Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.driver'`; `AttributeError: module 'flow_review.web.drive' has no attribute 'build_driver'`; `KeyError: 'maestro'` from `DRIVER_FACTORIES`.

- [ ] Implement (complete).

```python
# plugins/flow-review/engine/flow_review/driver.py
"""The M3-introduced Driver Protocol (A-47): the exact surface `DriveSession` and `replay_one`
call. `WebDriver` (M1) already implements every method with this shape; a `maestro` (M3) or
`http`/`shell` (M4) driver implements the same names so `DriveSession` never branches on driver
type -- one call site per verb, dispatched through `DRIVER_FACTORIES` at construction time."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Driver(Protocol):
    def launch(self, base_url: str) -> None: ...
    def close(self) -> None: ...
    def goto(self, path: str) -> None: ...
    def click(self, locator: dict) -> None: ...
    def fill(self, locator: dict, value: str, secret: bool = False) -> None: ...
    def press(self, key: str) -> None: ...
    def screenshot(self, path: Path) -> Path: ...
    def snapshot(self) -> dict: ...
    def is_password(self, locator: dict) -> bool: ...
    def begin_step(self, step_index: int) -> None: ...
    def end_step(self) -> None: ...
    def console_errors_since_check(self) -> list[dict]: ...
    def network_log_since_check(self) -> list[dict]: ...
```

`web/drive.py` already has, from M2, `_default_driver_factory(headless, viewport)`, `_tauri_driver_factory(headless, viewport, options=None)` (builds a `WebDriver` and installs the Tauri mocks init script) and:
```python
DRIVER_FACTORIES = {
    "playwright": lambda headless, viewport, options=None: _default_driver_factory(headless, viewport),
    "tauri": _tauri_driver_factory,
}
```
This task does not redefine any of that. It only adds the `maestro` factory and registers it:
```python
def _maestro_driver_factory(headless: bool, viewport: dict | None, options: dict | None = None):
    from flow_review.mobile.driver import MobileDriver
    options = options or {}
    return MobileDriver(app_id=options["app_id"], device=options.get("device"))


DRIVER_FACTORIES["maestro"] = _maestro_driver_factory
```
and adds `build_driver`, called uniformly (no playwright special case -- every factory in the dict already takes `(headless, viewport, options=None)`):
```python
def build_driver(driver_name: str, *, headless: bool, viewport: dict | None, options: dict):
    factory = DRIVER_FACTORIES.get(driver_name)
    if factory is None:
        raise ValueError(f"unknown driver {driver_name!r}; expected one of {sorted(DRIVER_FACTORIES)}")
    return factory(headless, viewport, options or {})
```

`serve(...)`'s `driver_name: str = "playwright"` / `options: dict | None = None` parameters and its call to `build_driver(...)`, and `cmd_start`'s `--driver`/`--driver-options` flags passed through to the spawned `serve` subprocess, are already in place from M2 (M2 introduced this design so M4's http/shell drivers could reuse it); this task adds no new parameter to `serve`/`cmd_start`/`cmd_serve` beyond what M2 already shipped. If `serve`/`cmd_start` do not yet have `driver_name`/`options` when this task starts, add them exactly as specified: `serve(surface_id, run_dir, project_root, base_url, *, driver_name="playwright", options=None, record_enabled=False, headless=True, viewport=None, tokens=None)` calling `build_driver(driver_name, headless=headless, viewport=viewport, options=options or {})`; `cmd_serve` reads a `--driver` (default `"playwright"`) and `--driver-options` (JSON string) argument and passes them through; `cmd_start` reads `surface.driver` and passes `--driver`/`--driver-options` (`json.dumps(surface.options)`) to the spawned `serve` subprocess alongside the existing `--base-url`/`--viewport-*`/`--tokens-file` flags.

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_driver_protocol.py plugins/flow-review/engine/flow_review/web/test_drive.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/driver.py plugins/flow-review/engine/flow_review/test_driver_protocol.py plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py && git commit -m "feat(driver): introduce the Driver protocol and a DRIVER_FACTORIES registry"`

### Task T6: `mobile/driver.py::MobileDriver`

**Executor:** sonnet · **Depends:** T3, T5 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/mobile/driver.py` (new), `plugins/flow-review/engine/flow_review/mobile/test_driver.py` (new), `plugins/flow-review/engine/flow_review/mobile/yaml.py` (new, minimal: only `locator_to_maestro` and `single_step_yaml`; `to_maestro` for the full action log is T8's job)
**Interfaces:** Consumes: `mobile.maestro.run_flow/screenshot/hierarchy/density` (T3, `run_flow` now takes `env`), `flow_review.driver.Driver` (T5), `web.driver.LocatorNotFound` (M1). Produces: `mobile.driver.MobileDriver` (A-47), `mobile.yaml.locator_to_maestro`, `mobile.yaml.single_step_yaml`.
**Ponytail rung:** 6 (minimum code: each verb is one generated single-step flow file + `run_flow`; no persistent Maestro session).

- [ ] Write the failing test.

```python
# plugins/flow-review/engine/flow_review/mobile/test_yaml.py -- new file
import pytest

from flow_review.mobile.yaml import locator_to_maestro, single_step_yaml
from flow_review.web.driver import LocatorNotFound


def test_locator_to_maestro_maps_role_and_name_to_text():
    assert locator_to_maestro({"role": "button", "name": "Open list"}) == {"text": "Open list"}


def test_locator_to_maestro_maps_testid_to_id():
    assert locator_to_maestro({"testid": "open-list"}) == {"id": "open-list"}


def test_locator_to_maestro_raises_for_css():
    with pytest.raises(LocatorNotFound):
        locator_to_maestro({"css": "#foo"})


def test_single_step_yaml_tap_on():
    text = single_step_yaml("com.example", {"tapOn": {"text": "Open list"}})
    assert text == "appId: com.example\n---\n- tapOn:\n    text: Open list\n"


def test_single_step_yaml_launch_app():
    text = single_step_yaml("com.example", "launchApp")
    assert text == "appId: com.example\n---\n- launchApp\n"
```

```python
# plugins/flow-review/engine/flow_review/mobile/test_driver.py -- new file
from pathlib import Path

import pytest

from flow_review.driver import Driver
from flow_review.mobile.driver import MobileDriver
from flow_review.web.driver import LocatorNotFound


def test_mobile_driver_conforms_to_the_driver_protocol():
    assert isinstance(MobileDriver(app_id="com.example", device=None, run_dir=None), Driver)


def test_launch_writes_a_launchapp_flow_and_runs_it(tmp_path, monkeypatch):
    calls = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        calls.append(yaml_path.read_text(encoding="utf-8"))
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.launch(base_url=str(tmp_path))
    assert calls == ["appId: com.example\n---\n- launchApp\n"]


def test_launch_writes_the_flow_under_run_dir_maestro_setup_and_deletes_it_after(tmp_path, monkeypatch):
    seen_paths = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        seen_paths.append(yaml_path)
        assert yaml_path.is_file()  # the file must exist WHILE run_flow runs
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.launch(base_url=str(tmp_path))
    flow_path = seen_paths[0]
    assert flow_path == tmp_path / "maestro" / "_setup" / "launch.yaml"
    assert not flow_path.exists()  # deleted in _run's finally, after run_flow returned


def test_click_resolves_locator_and_runs_tap_on(tmp_path, monkeypatch):
    calls = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        calls.append(yaml_path.read_text(encoding="utf-8"))
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.launch(base_url=str(tmp_path))
    d.click({"testid": "open-list"})
    assert calls[-1] == "appId: com.example\n---\n- tapOn:\n    id: open-list\n"


def test_click_raises_locator_not_found_when_the_tap_step_fails(tmp_path, monkeypatch):
    def fake_run_flow(yaml_path, device, env=None, runner=None):
        return {"ok": False, "failed_step": 1, "output": "FAILED: Element not found"}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    with pytest.raises(LocatorNotFound):
        d.click({"testid": "missing"})


def test_press_raises_runtime_error_when_a_non_interactive_step_fails(tmp_path, monkeypatch):
    def fake_run_flow(yaml_path, device, env=None, runner=None):
        return {"ok": False, "failed_step": 1, "output": "boom: adb not responding"}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    with pytest.raises(RuntimeError, match="boom"):
        d.press("Enter")


def test_fill_uses_input_text_after_tapping_the_field(tmp_path, monkeypatch):
    calls = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        calls.append(yaml_path.read_text(encoding="utf-8"))
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.launch(base_url=str(tmp_path))
    d.fill({"testid": "search"}, "hello", secret=False)
    assert calls[-1] == (
        "appId: com.example\n---\n"
        "- tapOn:\n    id: search\n"
        "- inputText: hello\n"
    )


def test_fill_secret_writes_an_env_placeholder_and_passes_the_value_via_env(tmp_path, monkeypatch):
    written = []
    envs = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        written.append(yaml_path.read_text(encoding="utf-8"))
        envs.append(env)
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.fill({"testid": "password"}, "hunter2", secret=True)
    assert written[-1] == "appId: com.example\n---\n- inputText: ${FR_SECRET}\n"
    assert "hunter2" not in written[-1]
    assert envs[-1] == {"FR_SECRET": "hunter2"}


def test_press_maps_escape_to_back(tmp_path, monkeypatch):
    calls = []

    def fake_run_flow(yaml_path, device, env=None, runner=None):
        calls.append(yaml_path.read_text(encoding="utf-8"))
        return {"ok": True, "failed_step": None, "output": ""}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.run_flow", fake_run_flow)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    d.launch(base_url=str(tmp_path))
    d.press("Escape")
    assert calls[-1] == "appId: com.example\n---\n- pressKey: Back\n"


def test_snapshot_flattens_hierarchy_text(tmp_path, monkeypatch):
    def fake_hierarchy(device, runner=None):
        return {"attributes": {"text": "Root"}, "children": [
            {"attributes": {"text": "Open list"}, "children": []},
        ]}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.hierarchy", fake_hierarchy)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    snap = d.snapshot()
    assert "Open list" in snap["aria"]


def test_is_password_reads_the_hierarchy_node_password_flag(tmp_path, monkeypatch):
    def fake_hierarchy(device, runner=None):
        return {"attributes": {}, "children": [
            {"attributes": {"resource-id": "pw", "password": "true"}, "children": []},
        ]}

    monkeypatch.setattr("flow_review.mobile.driver.maestro.hierarchy", fake_hierarchy)
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    assert d.is_password({"testid": "pw"}) is True
    assert d.is_password({"testid": "missing"}) is False


def test_console_and_network_since_check_are_always_empty():
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=None)
    assert d.console_errors_since_check() == []
    assert d.network_log_since_check() == []


def test_begin_step_and_end_step_are_a_no_op_step_counter():
    d = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=None)
    d.begin_step(3)
    d.end_step()  # must not raise
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/mobile/test_driver.py`
      Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.mobile.yaml'` / `'flow_review.mobile.driver'`.

- [ ] Implement (complete).

```python
# plugins/flow-review/engine/flow_review/mobile/yaml.py
"""Maestro flow-file generation (A-47/M3 Canonical Interfaces). `single_step_yaml` builds the
one-command flow each `MobileDriver` action runs; `to_maestro` (T8) builds the full recorded
flow from an action log for replay."""
from __future__ import annotations

from flow_review.web.driver import LocatorNotFound

_PRESS_KEY_MAP = {"Escape": "Back", "Back": "Back", "Enter": "Enter", "Home": "Home"}


def locator_to_maestro(locator: dict) -> dict:
    if locator.get("role"):
        return {"text": locator.get("name") or ""}
    if locator.get("testid"):
        return {"id": locator["testid"]}
    raise LocatorNotFound(locator)


def press_key_to_maestro(key: str) -> str:
    return _PRESS_KEY_MAP.get(key, key)


def _dump_command(command) -> list[str]:
    if isinstance(command, str):
        return [f"- {command}"]
    (verb, args), = command.items()
    lines = [f"- {verb}:"]
    for key, value in args.items():
        lines.append(f"    {key}: {value}")
    return lines


def single_step_yaml(app_id: str, command) -> str:
    lines = [f"appId: {app_id}", "---"] + _dump_command(command)
    return "\n".join(lines) + "\n"
```

```python
# plugins/flow-review/engine/flow_review/mobile/driver.py
"""MobileDriver: the Driver protocol (A-47) implemented over Maestro. Every action writes one
single-step flow file under `<run_dir>/maestro/<flow_id>/<step>.yaml`, runs it, and deletes it
(rung 6 -- no persistent Maestro session, no batching, and no stray flow files left in the run
directory). A secret fill never writes its value into the YAML: the file holds an env
placeholder (`${FR_SECRET}`) and the value travels only as a `maestro -e` argument
(`mobile/maestro.py::run_flow`'s `env`), matching the "secrets never touch a file the run
directory would keep" rule the web driver's screenshot masking already upholds.

`run_dir` and `flow_id` are set by `DriveSession` (T7): `run_dir` at construction (there is
always one -- a drive session always has a run directory), `flow_id` on `flow_begin`/`flow_end`
via a plain attribute assignment (not part of the `Driver` protocol; `DriveSession` already
`isinstance`-checks for `MobileDriver` to dispatch measurement, so setting one more attribute
there costs nothing new)."""
from __future__ import annotations

from pathlib import Path

from flow_review.mobile import maestro
from flow_review.mobile.yaml import locator_to_maestro, press_key_to_maestro, single_step_yaml
from flow_review.web.driver import LocatorNotFound

_INTERACTIVE_VERBS = ("tapOn", "inputText")


def _verb_of(command) -> str:
    if isinstance(command, str):
        return command.split(":", 1)[0].strip()
    return next(iter(command))


class MobileDriver:
    def __init__(self, app_id: str, device: str | None, run_dir: str | Path | None = None):
        self.app_id = app_id
        self.device = device
        self.run_dir = Path(run_dir) if run_dir is not None else Path(".flow-review-mobile-tmp")
        self.flow_id = "_setup"
        self._current_step: int | None = None

    def launch(self, base_url: str) -> None:
        # base_url is unused (a mobile surface has no URL); the M1 signature is kept so
        # DriveSession never branches on driver kind to call it.
        self._run("launchApp")

    def close(self) -> None:
        pass  # nothing to tear down; Maestro owns the emulator connection per invocation

    def goto(self, path: str) -> None:
        self._run("launchApp")  # A-40: path is ignored, recorded as "/" by DriveSession's route

    def click(self, locator: dict) -> None:
        self._run({"tapOn": locator_to_maestro(locator)}, locator=locator)

    def fill(self, locator: dict, value: str, secret: bool = False) -> None:
        self._run({"tapOn": locator_to_maestro(locator)}, locator=locator)
        if secret:
            self._run("inputText: ${FR_SECRET}", locator=locator, env={"FR_SECRET": value})
        else:
            self._run(f"inputText: {value}", locator=locator)

    def press(self, key: str) -> None:
        self._run(f"pressKey: {press_key_to_maestro(key)}")

    def screenshot(self, path: Path) -> Path:
        return maestro.screenshot(path, self.device)

    def snapshot(self) -> dict:
        tree = maestro.hierarchy(self.device)
        return {"aria": "\n".join(self._flatten_text(tree))}

    def is_password(self, locator: dict) -> bool:
        try:
            node = self._find_node(maestro.hierarchy(self.device), locator)
        except LocatorNotFound:
            return False
        if node is None:
            return False
        return str(node.get("attributes", {}).get("password", "")).lower() == "true"

    def begin_step(self, step_index: int) -> None:
        self._current_step = step_index

    def end_step(self) -> None:
        self._current_step = None

    def console_errors_since_check(self) -> list[dict]:
        return []  # no console concept on a native app; console.error never fires here

    def network_log_since_check(self) -> list[dict]:
        return []  # no network interception on this driver; http.5xx never fires here

    def _run(self, command, locator: dict | None = None, env: dict | None = None) -> dict:
        flow_dir = self.run_dir / "maestro" / self.flow_id
        flow_dir.mkdir(parents=True, exist_ok=True)
        step_name = str(self._current_step) if self._current_step is not None else "launch"
        flow_path = flow_dir / f"{step_name}.yaml"
        flow_path.write_text(single_step_yaml(self.app_id, command), encoding="utf-8")
        try:
            result = maestro.run_flow(flow_path, self.device, env=env)
        finally:
            flow_path.unlink(missing_ok=True)
        if not result["ok"]:
            if _verb_of(command) in _INTERACTIVE_VERBS and locator is not None:
                raise LocatorNotFound(locator)
            raise RuntimeError(result["output"][-500:])
        return result

    def _flatten_text(self, node: dict) -> list[str]:
        out = []
        text = (node.get("attributes") or {}).get("text")
        if text:
            out.append(text)
        for child in node.get("children") or []:
            out.extend(self._flatten_text(child))
        return out

    def _find_node(self, node: dict, locator: dict) -> dict | None:
        target = locator_to_maestro(locator)
        attrs = node.get("attributes") or {}
        if "id" in target and attrs.get("resource-id") == target["id"]:
            return node
        if "text" in target and attrs.get("text") == target["text"]:
            return node
        for child in node.get("children") or []:
            found = self._find_node(child, locator)
            if found is not None:
                return found
        return None
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/mobile/test_driver.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/mobile/driver.py plugins/flow-review/engine/flow_review/mobile/yaml.py plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/mobile/test_driver.py && git commit -m "feat(mobile): implement MobileDriver over generated single-step Maestro flows"`

### Task T7: `mobile/measure.py::check_hierarchy`/`screen_route` + `DriveSession` dispatch

**Executor:** sonnet · **Depends:** T6 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/mobile/measure.py` (new), `plugins/flow-review/engine/flow_review/mobile/test_measure.py` (new), `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/test_drive.py`
**Interfaces:** Consumes: `web.measure.check_rects`/`Finding` (M1, reused verbatim), `mobile.maestro.density`/`hierarchy` (T3), `mobile.driver.MobileDriver` (T6). Produces: `mobile.measure.check_hierarchy(tree, surface_id, flow_id, route, density=160) -> list[dict]`, `mobile.measure.screen_route(tree, app_id) -> str`, the mobile evidence refs (`mobile/<flow_id>/<step>.json`/`.png`).
**Ponytail rung:** 6 (minimum code: one `isinstance` dispatch in `DriveSession._run_checks`, `# ponytail:` comment).

- [ ] Write the failing test.

```python
# plugins/flow-review/engine/flow_review/mobile/test_measure.py -- new file
from flow_review.mobile.measure import check_hierarchy, screen_route

# row-1 (clickable) and badge-1 (NOT clickable) genuinely overlap: row-1 spans
# x:[0,1080] y:[100,156], badge-1 spans x:[900,1000] y:[116,140] -- badge-1 sits fully inside
# row-1's rect. icon-button (clickable, 32x32) does not overlap anything.
DENSE_TREE = {
    "attributes": {},
    "children": [
        {"attributes": {"text": "i", "resource-id": "icon-button",
                         "bounds": "[0,0][32,32]", "clickable": "true"}, "children": []},
        {"attributes": {"text": "row1", "resource-id": "row-1",
                         "bounds": "[0,100][1080,156]", "clickable": "true"}, "children": []},
        {"attributes": {"text": "new", "resource-id": "badge-1",
                         "bounds": "[900,116][1000,140]", "clickable": "false"}, "children": []},
    ],
}


def test_check_hierarchy_flags_a_small_clickable_target():
    findings = check_hierarchy(DENSE_TREE, "mobile", "home", "Home", density=160)
    small = [f for f in findings if f["rule"] == "rect.target-size" and f["locator"] == "testid:icon-button"]
    assert len(small) == 1


def test_check_hierarchy_flags_overlap_even_though_the_badge_is_not_clickable():
    findings = check_hierarchy(DENSE_TREE, "mobile", "list", "List", density=160)
    overlap = [f for f in findings if f["rule"] == "rect.overlap"]
    assert len(overlap) == 1
    assert overlap[0]["locator"] in ("testid:row-1", "testid:badge-1")


def test_check_hierarchy_never_flags_target_size_for_a_non_clickable_node():
    tree = {"attributes": {}, "children": [
        {"attributes": {"text": "label", "bounds": "[0,0][10,10]", "clickable": "false"},
         "children": []},
    ]}
    findings = check_hierarchy(tree, "mobile", "home", "Home", density=160)
    assert findings == []  # a single bounded node can never overlap anything either


def test_check_hierarchy_scales_bounds_by_density():
    # 420dpi device: 96x96px == 96*(160/420) ~= 36.6dp, still below the 48dp minimum.
    tree = {"attributes": {}, "children": [
        {"attributes": {"text": "i", "resource-id": "icon", "bounds": "[0,0][96,96]",
                         "clickable": "true"}, "children": []},
    ]}
    findings = check_hierarchy(tree, "mobile", "home", "Home", density=420)
    assert any(f["rule"] == "rect.target-size" for f in findings)


def test_screen_route_returns_the_first_top_left_text_node():
    tree = {"attributes": {}, "children": [
        {"attributes": {"text": "Item 1", "bounds": "[0,60][200,90]"}, "children": []},
        {"attributes": {"text": "List", "bounds": "[0,0][100,30]"}, "children": []},
    ]}
    assert screen_route(tree, "com.example") == "List"


def test_screen_route_falls_back_to_app_id_when_no_text_node_has_bounds():
    tree = {"attributes": {}, "children": []}
    assert screen_route(tree, "com.example") == "com.example"
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_measure.py`
      Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.mobile.measure'`.

- [ ] Implement (complete).

```python
# plugins/flow-review/engine/flow_review/mobile/measure.py
"""Rect rules on Maestro hierarchy bounds (A-40), dp-scaled from px via the caller-supplied
`density` (never fetched here -- `DriveSession`/`replay_maestro_flow` fetch it once per step via
`maestro.density` and pass it in, so this module has no subprocess dependency of its own).
`rect.target-size` is clickable-only (a label can't be tapped, so its size is not a defect);
`rect.overlap` is computed over every node with parseable bounds, clickable or not -- a
non-interactive badge sitting on top of a real button is exactly the overlap a screenshot review
would flag, and restricting overlap to clickables only would silently miss it. Reuses
`web.measure.check_rects` and its rule ids verbatim -- the threshold (24x24 for web's CSS px) is
doubled to 48x48 by scaling every rect INTO an "effective 24px-equivalent" space at 2x before
calling it, rather than forking the rule."""
from __future__ import annotations

import re

from flow_review.web import measure as web_measure
from flow_review.web import actionlog

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")

# web's check_rects flags anything under 24x24 CSS px; a mobile 48dp minimum is reached by
# halving every dp measurement before calling it, so "24" in that function reads as "48dp" here.
_DP_TO_HALF_DP = 0.5


def _parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    match = _BOUNDS_RE.match(bounds or "")
    if not match:
        return None
    x0, y0, x1, y1 = (int(g) for g in match.groups())
    return x0, y0, x1 - x0, y1 - y0


def _locator_for(attrs: dict) -> dict:
    resource_id = attrs.get("resource-id") or ""
    if resource_id:
        return {"testid": resource_id}
    return {"role": "button", "name": attrs.get("text", "")}


def _collect_bounded(node: dict, out: list[dict], *, clickable_only: bool) -> None:
    attrs = node.get("attributes") or {}
    is_clickable = str(attrs.get("clickable", "")).lower() == "true"
    if not clickable_only or is_clickable:
        parsed = _parse_bounds(attrs.get("bounds", ""))
        if parsed is not None:
            x, y, w, h = parsed
            out.append({"locator": _locator_for(attrs), "x": x, "y": y, "w": w, "h": h})
    for child in node.get("children") or []:
        _collect_bounded(child, out, clickable_only=clickable_only)


def _scaled(rects_px: list[dict], density: int) -> list[dict]:
    scale = (160.0 / density) * _DP_TO_HALF_DP
    return [
        {"locator": r["locator"], "x": r["x"] * scale, "y": r["y"] * scale,
         "w": r["w"] * scale, "h": r["h"] * scale}
        for r in rects_px
    ]


def _payload(f: dict, surface_id: str, flow_id: str, route: str) -> dict:
    loc = f["locator"]
    return {
        "surface_id": surface_id, "flow_id": flow_id, "rule": f["rule"], "route": route,
        "locator": actionlog.locator_key(loc) if loc else "", "sev": f["sev"],
        "text": f["text"], "evidence": f["evidence"], "disposition": "engine",
    }


def check_hierarchy(tree: dict, surface_id: str, flow_id: str, route: str,
                     density: int = 160) -> list[dict]:
    clickable_px: list[dict] = []
    _collect_bounded(tree, clickable_px, clickable_only=True)
    all_px: list[dict] = []
    _collect_bounded(tree, all_px, clickable_only=False)

    target_size = [
        f for f in web_measure.check_rects(_scaled(clickable_px, density), route)
        if f["rule"] == "rect.target-size"
    ]
    overlap = [
        f for f in web_measure.check_rects(_scaled(all_px, density), route)
        if f["rule"] == "rect.overlap"
    ]
    return [_payload(f, surface_id, flow_id, route) for f in target_size + overlap]


def screen_route(tree: dict, app_id: str) -> str:
    """The current screen's route label for a maestro surface (M3 Canonical Interfaces): the
    first node with non-empty text and parseable bounds, ordered top-left first; `app_id` if the
    tree has none. Mirrors web's "route is a stable label, not a screenshot" rule -- a screen's
    heading text is expected to stay put across a run the way a URL path does on web."""
    candidates: list[tuple[int, int, str]] = []

    def _walk(node: dict) -> None:
        attrs = node.get("attributes") or {}
        text = attrs.get("text")
        bounds = _parse_bounds(attrs.get("bounds", ""))
        if text and bounds is not None:
            x, y, _w, _h = bounds
            candidates.append((y, x, text))
        for child in node.get("children") or []:
            _walk(child)

    _walk(tree)
    if not candidates:
        return app_id
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]
```

`DriveSession` needs two small additions in `web/drive.py`: `__init__` hands the drive session's `run_dir` to a `MobileDriver` (the driver is built by `DRIVER_FACTORIES` before `DriveSession` exists, so it never receives one otherwise), and `flow_begin` tells the driver which flow it is in (so `MobileDriver._run`, T6, writes each step's flow file under the right `<run_dir>/maestro/<flow_id>/` folder). `_run_checks` dispatches to `check_hierarchy`/`screen_route` and writes the mobile evidence. Add the import `from flow_review.mobile import measure as mobile_measure, maestro` at the top of `web/drive.py`, and change exactly these three methods:

```python
    def __init__(self, driver, surface_id: str, run_dir, project_root, record_enabled: bool,
                 tokens: dict | None = None):
        self.driver = driver
        self.surface_id = surface_id
        self.run_dir = Path(run_dir)
        self.project_root = Path(project_root)
        self.record_enabled = record_enabled
        self.tokens = tokens
        self.log = None
        self.flow_id = None
        self.step_index = 0
        self._offline_active = False
        self._active_5xx_patterns: list[str] = []
        self._seen_fingerprints: set[str] = set()
        from flow_review.mobile.driver import MobileDriver  # local: mobile is optional at import time
        if isinstance(self.driver, MobileDriver):
            self.driver.run_dir = self.run_dir
```

```python
    def flow_begin(self, flow_id: str) -> dict:
        self.flow_id = flow_id
        self.log = actionlog.new_log(self.surface_id, flow_id)
        self.step_index = 0
        # The fingerprint includes flow_id anyway, so a new flow must re-report a finding that
        # looked identical in an earlier flow -- reset the seen-set here, not per-run.
        self._seen_fingerprints = set()
        # A fault injected during an earlier flow must not leak into this one.
        self.clear_faults()
        from flow_review.mobile.driver import MobileDriver
        if isinstance(self.driver, MobileDriver):
            self.driver.flow_id = flow_id
        events.append(self.run_dir, {
            "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
            "step": "flow-begin",
        })
        return {"flow_id": flow_id}
```

```python
    def _run_checks(self, step_index) -> list:
        # ponytail: one isinstance check rather than a MeasureHook-per-driver abstraction -- a
        # third driver kind (M4's http/shell) files no rect/contrast findings at all, so this
        # never grows past two branches.
        from flow_review.mobile.driver import MobileDriver
        if isinstance(self.driver, MobileDriver):
            tree = maestro.hierarchy(self.driver.device)
            density = maestro.density(self.driver.device)
            route = mobile_measure.screen_route(tree, self.driver.app_id)
            findings = mobile_measure.check_hierarchy(
                tree, self.surface_id, self.flow_id, route, density,
            )
            self._attach_mobile_evidence(tree, step_index, findings)
        else:
            # A-6: the route is the URL path only, so fingerprints match replay's and survive a
            # port change between runs.
            route = urlparse(self._current_url() or "").path or "/"
            findings = measure.check_page(
                self.driver, self.surface_id, self.flow_id, route, self.tokens, step_index,
            )
        new_ids = []
        for finding in findings:
            if self._is_self_inflicted(finding):
                continue
            fp = ledger.fingerprint(self.flow_id or "", finding.get("rule") or "",
                                     finding.get("route") or "", finding.get("locator") or "")
            seen_key = (fp, finding.get("sev"), finding.get("text"))
            if seen_key in self._seen_fingerprints:
                continue
            self._seen_fingerprints.add(seen_key)
            event = events.append(self.run_dir, {
                "type": "finding", "surface_id": self.surface_id, "flow_id": self.flow_id,
                **finding,
            })
            new_ids.append(event["id"])
        return new_ids

    def _attach_mobile_evidence(self, tree: dict, step_index, findings: list[dict]) -> None:
        """Mobile evidence refs (M3 Canonical Interfaces). Must run before the caller's loop
        appends any finding to `events.jsonl` -- an event's `evidence` cannot be edited after
        `events.append` writes its line, so the refs go onto each finding dict here, first."""
        if not findings:
            return
        step_label = step_index if step_index is not None else "look"
        mobile_dir = self.run_dir / "mobile" / (self.flow_id or "_setup")
        mobile_dir.mkdir(parents=True, exist_ok=True)
        json_path = mobile_dir / f"{step_label}.json"
        json_path.write_text(json.dumps(tree, ensure_ascii=False)[:4000], encoding="utf-8")
        png_path = mobile_dir / f"{step_label}.png"
        self.driver.screenshot(png_path)
        refs = [f"mobile/{self.flow_id}/{step_label}.json", f"mobile/{self.flow_id}/{step_label}.png"]
        for finding in findings:
            finding["evidence"] = list(finding.get("evidence") or []) + refs
```

(`_run_checks`'s existing self-inflicted/fingerprint loop body above is copied verbatim from the current file -- only the `findings`/`route` computation above it changes, into the `if`/`else`; nothing in the loop itself is rewritten.)

```python
# plugins/flow-review/engine/flow_review/web/test_drive.py -- append
def test_drive_session_computes_screen_route_and_density_for_a_mobile_driver(monkeypatch, tmp_path):
    from flow_review.mobile.driver import MobileDriver
    from flow_review.web.drive import DriveSession

    tree = {"attributes": {}, "children": [
        {"attributes": {"text": "List", "bounds": "[0,0][100,30]"}, "children": []},
    ]}
    monkeypatch.setattr("flow_review.web.drive.maestro.hierarchy", lambda device: tree)
    monkeypatch.setattr("flow_review.web.drive.maestro.density", lambda device: 240)
    calls = {}
    monkeypatch.setattr(
        "flow_review.web.drive.mobile_measure.check_hierarchy",
        lambda t, sid, fid, route, density: calls.setdefault("called", (sid, fid, route, density)) or [],
    )
    driver = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    session = DriveSession(driver, "mobile", tmp_path, tmp_path, record_enabled=False)
    session.flow_begin("flow1")
    session._run_checks(0)
    assert calls["called"] == ("mobile", "flow1", "List", 240)
    assert driver.run_dir == tmp_path
    assert driver.flow_id == "flow1"


def test_drive_session_attaches_mobile_evidence_refs_to_findings_filed_that_step(monkeypatch, tmp_path):
    from flow_review.mobile.driver import MobileDriver
    from flow_review.web.drive import DriveSession

    tree = {"attributes": {}, "children": []}
    monkeypatch.setattr("flow_review.web.drive.maestro.hierarchy", lambda device: tree)
    monkeypatch.setattr("flow_review.web.drive.maestro.density", lambda device: 160)
    monkeypatch.setattr(
        "flow_review.web.drive.mobile_measure.check_hierarchy",
        lambda t, sid, fid, route, density: [
            {"surface_id": sid, "flow_id": fid, "rule": "rect.target-size", "route": route,
             "locator": "testid:icon", "sev": "P2", "text": "x", "evidence": ["w=32", "h=32"],
             "disposition": "engine"},
        ],
    )
    monkeypatch.setattr(MobileDriver, "screenshot", lambda self, path: path)
    driver = MobileDriver(app_id="com.example", device="emulator-5554", run_dir=tmp_path)
    session = DriveSession(driver, "mobile", tmp_path, tmp_path, record_enabled=False)
    session.flow_begin("flow1")
    session._run_checks(0)
    events_text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "mobile/flow1/0.json" in events_text
    assert "mobile/flow1/0.png" in events_text
    assert (tmp_path / "mobile" / "flow1" / "0.json").is_file()
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_measure.py plugins/flow-review/engine/flow_review/web/test_drive.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/mobile/measure.py plugins/flow-review/engine/flow_review/mobile/test_measure.py plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py && git commit -m "feat(mobile): dp-scaled rect checks, screen-route labels and evidence refs"`

### Task T8: Recording + replay for maestro surfaces

**Executor:** opus · **Depends:** T7 · **Wave:** 5
**Files:** `plugins/flow-review/engine/flow_review/mobile/yaml.py`, `plugins/flow-review/engine/flow_review/mobile/test_yaml.py`, `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/test_drive.py`, `plugins/flow-review/engine/flow_review/web/replay.py`, `plugins/flow-review/engine/flow_review/web/test_replay.py`
**Interfaces:** Consumes: `web.actionlog` step shape (M1), `mobile.maestro.run_flow`/`hierarchy`/`density`/`screenshot` (T3), `mobile.measure.check_hierarchy`/`screen_route` (T7). Produces: `mobile.yaml.to_maestro(log: dict, app_id: str) -> str`, `web.replay.replay_maestro_flow(yaml_path, log, device, run_dir=None) -> ReplayResult`.
**Ponytail rung:** 6 (minimum code: one new function per side, called from one new branch in `replay()`; `--variants` stays a no-op for maestro, logged, not silently ignored).

- [ ] Write the failing tests.

```python
# plugins/flow-review/engine/flow_review/mobile/test_yaml.py -- append
from flow_review.mobile.yaml import to_maestro

# app_id ("com.example.app") is deliberately different from surface_id ("mobile") in this
# fixture: to_maestro must emit the real package id, never the flow-review surface id.
ACTION_LOG = {
    "schema_version": 1, "surface_id": "mobile", "flow_id": "open-list",
    "recorded_at": "2026-01-01T00:00:00.000Z",
    "steps": [
        {"action": "goto", "url": "/", "locator": None, "value": None, "checkpoint": None},
        {"action": "click", "url": "/", "locator": {"testid": "open-list"}, "value": None,
         "checkpoint": None},
        {"action": "fill", "url": "/list", "locator": {"testid": "search"}, "value": "shoes",
         "checkpoint": None},
        {"action": "press", "url": "/list", "locator": None, "value": "Escape",
         "checkpoint": None},
    ],
}

ACTION_LOG_WITH_SECRET_FILL = {
    "schema_version": 1, "surface_id": "mobile", "flow_id": "login",
    "recorded_at": "2026-01-01T00:00:00.000Z",
    "steps": [
        {"action": "fill", "url": "/login", "locator": {"testid": "password", "secret": True},
         "value": None, "checkpoint": None, "from_env": "APP_PASSWORD"},
    ],
}


def test_to_maestro_builds_one_command_per_step_using_the_real_app_id():
    text = to_maestro(ACTION_LOG, "com.example.app")
    assert text == (
        "appId: com.example.app\n---\n"
        "- launchApp\n"
        "- tapOn:\n    id: open-list\n"
        "- tapOn:\n    id: search\n"
        "- inputText: shoes\n"
        "- pressKey: Back\n"
    )


def test_to_maestro_writes_an_env_placeholder_for_a_from_env_fill_never_the_value():
    text = to_maestro(ACTION_LOG_WITH_SECRET_FILL, "com.example.app")
    assert "inputText: ${APP_PASSWORD}" in text
    assert "APP_PASSWORD" not in text.replace("${APP_PASSWORD}", "")
```

```python
# plugins/flow-review/engine/flow_review/web/test_replay.py -- append
from flow_review.web.replay import replay_maestro_flow


def test_replay_maestro_flow_clean_when_maestro_exits_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "flow_review.web.replay.maestro.run_flow",
        lambda yaml_path, device, env=None, runner=None: {"ok": True, "failed_step": None, "output": ""},
    )
    monkeypatch.setattr(
        "flow_review.web.replay.maestro.hierarchy",
        lambda device, runner=None: {"attributes": {}, "children": []},
    )
    monkeypatch.setattr("flow_review.web.replay.maestro.density", lambda device, runner=None: 160)
    monkeypatch.setattr(
        "flow_review.web.replay.mobile_measure.check_hierarchy",
        lambda tree, sid, fid, route, density: [],
    )
    flow = tmp_path / "flow.yaml"
    flow.write_text("appId: com.example\n---\n- launchApp\n", encoding="utf-8")
    log = {"surface_id": "mobile", "flow_id": "open-list", "steps": []}
    result = replay_maestro_flow(flow, log, device="emulator-5554")
    assert result["status"] == "clean"
    assert result["divergence"] is None


def test_replay_maestro_flow_divergence_at_failed_step(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "flow_review.web.replay.maestro.run_flow",
        lambda yaml_path, device, env=None, runner=None: {"ok": False, "failed_step": 2, "output": "boom"},
    )
    flow = tmp_path / "flow.yaml"
    flow.write_text("appId: com.example\n---\n- launchApp\n", encoding="utf-8")
    log = {"surface_id": "mobile", "flow_id": "open-list", "steps": []}
    result = replay_maestro_flow(flow, log, device="emulator-5554")
    assert result["status"] == "divergence"
    assert result["divergence"]["step_index"] == 2
    assert result["divergence"]["reason"] == "maestro_step_failed"


def test_replay_maestro_flow_runs_check_hierarchy_after_a_clean_run_and_attaches_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "flow_review.web.replay.maestro.run_flow",
        lambda yaml_path, device, env=None, runner=None: {"ok": True, "failed_step": None, "output": ""},
    )
    monkeypatch.setattr(
        "flow_review.web.replay.maestro.hierarchy",
        lambda device, runner=None: {"attributes": {}, "children": []},
    )
    monkeypatch.setattr("flow_review.web.replay.maestro.density", lambda device, runner=None: 160)
    monkeypatch.setattr("flow_review.web.replay.maestro.screenshot", lambda path, device, runner=None: path)
    calls = {}
    monkeypatch.setattr(
        "flow_review.web.replay.mobile_measure.check_hierarchy",
        lambda tree, sid, fid, route, density: calls.setdefault("called", True) or [
            {"surface_id": sid, "flow_id": fid, "rule": "rect.target-size", "route": route,
             "locator": "", "sev": "P2", "text": "x", "evidence": [], "disposition": "engine"},
        ],
    )
    flow = tmp_path / "flow.yaml"
    flow.write_text("appId: com.example\n---\n- launchApp\n", encoding="utf-8")
    log = {"surface_id": "mobile", "flow_id": "open-list", "steps": []}
    result = replay_maestro_flow(flow, log, device="emulator-5554", run_dir=tmp_path)
    assert calls["called"] is True
    assert len(result["findings"]) == 1
    assert "mobile/open-list/replay.json" in result["findings"][0]["evidence"]
    assert (tmp_path / "mobile" / "open-list" / "replay.json").is_file()
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/web/test_replay.py`
      Expected FAIL: `TypeError: to_maestro() missing 1 required positional argument: 'app_id'`; `ImportError: cannot import name 'replay_maestro_flow'`.

- [ ] Implement (complete).

Append to `mobile/yaml.py`:
```python
_ACTION_TO_COMMAND = {
    "goto": lambda step: "launchApp",
    "click": lambda step: {"tapOn": locator_to_maestro(step["locator"])},
    "press": lambda step: f"pressKey: {press_key_to_maestro(step['value'])}",
}


def _fill_commands(step: dict) -> list:
    commands = [{"tapOn": locator_to_maestro(step["locator"])}]
    if step.get("from_env"):
        commands.append(f"inputText: ${{{step['from_env']}}}")  # never the resolved value
    else:
        commands.append(f"inputText: {step['value']}")
    return commands


def to_maestro(log: dict, app_id: str) -> str:
    """The full recorded flow as a Maestro flow file (M3 Canonical Interfaces: recording for
    maestro surfaces saves both the M1 JSON action log and this YAML; `replay` runs the YAML).
    `app_id` is always the surface's `options["app_id"]` (a package id) -- `log["surface_id"]`
    is a flow-review surface id (e.g. `"mobile"`) and is never a valid Maestro `appId`."""
    lines = [f"appId: {app_id}", "---", "- launchApp"]
    for step in log["steps"]:
        action = step["action"]
        if action == "goto":
            continue  # already covered by the leading launchApp
        if action == "fill":
            for command in _fill_commands(step):
                lines += _dump_command(command)
            continue
        command = _ACTION_TO_COMMAND[action](step)
        lines += _dump_command(command)
    return "\n".join(lines) + "\n"
```

Add to `web/replay.py` (imports at top: `from flow_review.mobile import maestro, measure as mobile_measure`):
```python
def replay_maestro_flow(yaml_path: Path, log: dict, device: str | None,
                         run_dir: Path | None = None) -> ReplayResult:
    """The maestro-surface counterpart of `replay_one` (A-47/M3): runs the whole recorded flow
    file in one `maestro test`, since Maestro has no step-by-step remote control. A failing step
    maps to the same `ReplayResult` shape web replay produces, so callers never branch on driver
    kind past this function. `run_dir`, when given, gets the same mobile evidence refs a live
    drive session writes (M3 Canonical Interfaces); omitted in a context with no run directory
    (e.g. a unit test), in which case findings simply carry no evidence refs."""
    surface_id, flow_id = log["surface_id"], log["flow_id"]
    result = maestro.run_flow(yaml_path, device)
    if not result["ok"]:
        return ReplayResult(
            flow_id=flow_id, status="divergence", steps_run=result["failed_step"] or 0,
            divergence={
                "step_index": result["failed_step"], "locator": None,
                "reason": "maestro_step_failed", "url": None,
            },
            findings=[],
        )
    tree = maestro.hierarchy(device)
    density = maestro.density(device)
    route = mobile_measure.screen_route(tree, surface_id)
    findings = mobile_measure.check_hierarchy(tree, surface_id, flow_id, route, density)
    if run_dir is not None and findings:
        mobile_dir = Path(run_dir) / "mobile" / flow_id
        mobile_dir.mkdir(parents=True, exist_ok=True)
        json_path = mobile_dir / "replay.json"
        json_path.write_text(json.dumps(tree, ensure_ascii=False)[:4000], encoding="utf-8")
        png_path = mobile_dir / "replay.png"
        maestro.screenshot(png_path, device)
        refs = [f"mobile/{flow_id}/replay.json", f"mobile/{flow_id}/replay.png"]
        for finding in findings:
            finding["evidence"] = list(finding.get("evidence") or []) + refs
    status = "regression" if findings else "clean"
    return ReplayResult(flow_id=flow_id, status=status, steps_run=len(log["steps"]),
                         divergence=None, findings=findings)
```
(`json` must already be imported at the top of `web/replay.py` -- it is, M1 uses it elsewhere in this file.)

In `web/replay.py::replay(...)`, find the per-surface loop that currently always builds a `WebDriver` and calls `replay_one`; wrap that existing body in an `else:` under a new `if surface.driver == "maestro":` branch placed immediately above it:

```python
        if surface.driver == "maestro":
            from flow_review.mobile.yaml import to_maestro
            device = surface.options.get("device")
            yaml_text = to_maestro(log, surface.options["app_id"])
            yaml_path = project_root / ".flow-review" / "runs" / ".replay-tmp" / f"{log['flow_id']}.yaml"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(yaml_text, encoding="utf-8")
            try:
                result = replay_maestro_flow(yaml_path, log, device, run_dir=run_dir)
            finally:
                yaml_path.unlink(missing_ok=True)
            if variants:
                events.append(run_dir, {
                    "type": "status", "surface_id": surface.id, "flow_id": log["flow_id"],
                    "status": "not-exercised", "reason": "variants-unsupported",
                })
        else:
            result = replay_one(driver, log, measure=measure_hook, project_root=project_root)
```
The implementer locates the line in the current per-surface loop that calls `replay_one(...)` (its exact call, and everything before it that builds `driver`/`measure_hook`, stays exactly where it is, now nested one level under this new `else:`); everything below the `replay_one`/`replay_maestro_flow` call in that loop (screenshot-on-divergence, accumulating into `divergences`, the exit-code logic) reads `result` either way and needs no change, since `ReplayResult` has the same shape from both paths.

Update `flow-end`'s writer in `web/drive.py::DriveSession.flow_end` to also emit the Maestro YAML when the surface is a `maestro` surface and recording is on:
```python
    def flow_end(self, flow_id: str, status: str) -> dict:
        log_path = None
        if self.log is not None:
            log_path = actionlog.save(self.log, self.run_dir, self.project_root,
                                       self.record_enabled)
            from flow_review.mobile.driver import MobileDriver
            if self.record_enabled and isinstance(self.driver, MobileDriver):
                from flow_review.mobile.yaml import to_maestro
                Path(log_path).with_suffix(".yaml").write_text(
                    to_maestro(self.log, self.driver.app_id), encoding="utf-8",
                )
        events.append(self.run_dir, {
            "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
            "step": "flow-end", "status": status,
        })
        self.log = None
        self.flow_id = None
        return {"flow_id": flow_id, "status": status,
                "log_path": str(log_path) if log_path else None}
```
(everything from `events.append(...)` onward is copied verbatim from the current file; only the `MobileDriver`/`to_maestro` block above it is new.)

```python
# plugins/flow-review/engine/flow_review/web/test_drive.py -- append
def test_flow_end_writes_a_maestro_yaml_alongside_the_json_when_recording(tmp_path):
    from flow_review.mobile.driver import MobileDriver
    from flow_review.web.drive import DriveSession

    driver = MobileDriver(app_id="com.example.app", device=None, run_dir=tmp_path)
    session = DriveSession(driver, "mobile", tmp_path, tmp_path, record_enabled=True)
    session.flow_begin("open-list")
    session.log["steps"].append({"action": "goto", "url": "/", "locator": None, "value": None,
                                  "checkpoint": None})
    result = session.flow_end("open-list", "ok")
    json_path = Path(result["log_path"])
    yaml_path = json_path.with_suffix(".yaml")
    assert yaml_path.is_file()
    assert yaml_path.read_text(encoding="utf-8").startswith("appId: com.example.app\n")
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/web/test_replay.py plugins/flow-review/engine/flow_review/web/test_drive.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/mobile/yaml.py plugins/flow-review/engine/flow_review/mobile/test_yaml.py plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/replay.py plugins/flow-review/engine/flow_review/web/test_replay.py && git commit -m "feat(mobile): record and replay maestro flows"`

### Task T9: Agent briefs + references

**Executor:** haiku · **Depends:** T8 · **Wave:** 6
**Files:** `plugins/flow-review/skills/flow-review/references/testing.md`, `plugins/flow-review/skills/flow-review/references/evidence.md`, `plugins/flow-review/skills/flow-review/references/surfaces.md`, `plugins/flow-review/agents/fr-explorer.md`, `plugins/flow-review/agents/fr-lens.md`
**Interfaces:** Consumes: none (documentation only). Produces: none new; keeps `test_cli_parity` (existing M1 test asserting every `drive`/verb documented in `testing.md` matches the CLI) green.
**Ponytail rung:** 1 (skip: no code).

- [ ] Write the failing test (a documentation-drift check, matching M1's existing `test_cli_parity` pattern -- confirm the exact test name and assertion shape in `test_cli.py` before writing this, since it already exists and this task only needs it to keep passing after the docs change, not to add a new test). If `test_cli_parity` already covers `drive`'s verb set exhaustively, no new test is needed for this task; instead add one narrow content check:

```python
# plugins/flow-review/engine/flow_review/test_cli.py -- append
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent.parent / "skills" / "flow-review"


def test_surfaces_md_documents_the_maestro_driver():
    text = (SKILL_ROOT / "references" / "surfaces.md").read_text(encoding="utf-8")
    assert "## Driver: maestro" in text
    assert "## Driver: adb" not in text or "pending-driver" not in text.split("## Driver: adb")[1].split("##")[0]
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py::test_surfaces_md_documents_the_maestro_driver`
      Expected FAIL: `AssertionError` (`"## Driver: maestro"` absent from `surfaces.md`).

- [ ] Implement (complete).

In `references/surfaces.md`, replace the `## Driver: adb` section with:
```markdown
## Driver: maestro

Drives an Android app under Expo Go (or any installed APK) via the Maestro CLI and `adb`.
Nothing here launches an emulator or installs Maestro (A-38) -- the user starts the emulator
and runs the app's `start_cmd` themselves; the engine only shells out to `maestro`/`adb`.

**Launch.** The surface's `options.start_cmd` (e.g. `npx expo start --android`) is a user step
documented in `SKILL.md`, never run by the engine.

**Proven attached when.** `adb devices` lists at least one device in state `device`, and
`maestro hierarchy` returns a JSON tree for it.

**Evidence it can produce.** The Maestro accessibility hierarchy (`text`, `resource-id`,
`bounds`, `clickable`), and a screenshot via `maestro screenshot`. No contrast measurement
(no computed-style access on a native view tree); only `rect.target-size` and `rect.overlap`,
scaled from px to dp with the device's reported density.

## Driver: ios-sim

pending-driver until a macOS host exists (A-40).

## Driver: shell

pending-driver until M4 (A-14).

## Driver: http

pending-driver until M4 (A-14).

## Driver: custom

pending-driver until M2/M3/M4 (A-14).
```

In `references/testing.md`, replace the `### adb (android)` section with:
```markdown
### maestro (android)

- Each action here is one generated single-step Maestro flow, not a persistent session -- there
  is no "wait for idle" the way Playwright's `_settle()` provides; a flow that taps something
  before its target rendered simply fails that step (a divergence on replay), so wait for the
  screen you expect with `look` before the next action if a flow seems to race the UI.
- `look`'s snapshot is the flattened hierarchy text, not a screenshot; pass `--shot` to also
  capture a PNG via `maestro screenshot`.
- The tap-target rule (`rect.target-size`) uses the device's *reported* density
  (`adb shell wm density`), not a fixed DPI -- two emulators at different densities file the
  same defect at different raw pixel bounds but the same dp size.
- `--css` locators are never supported here (`LocatorNotFound`); use `--role`/`--name` (mapped
  to Maestro `text:`) or `--testid` (mapped to `id:`, i.e. the view's `resource-id`).
- `goto` on this driver ignores its path argument and just relaunches the app (A-40); there is
  no URL concept, so every route in a mobile finding is the flow's own label, not a path.

### shell / http

pending-driver until M4 (A-14).
```

In `references/evidence.md`, add (after the existing per-driver evidence guidance -- read the file's current structure and add this as its own subsection, keeping the existing table/prose format rather than introducing a new one):
```markdown
### Mobile (maestro) evidence bundle

Order matters: the hierarchy excerpt (the relevant node's `text`/`resource-id`/`bounds`) comes
first in a mobile finding's evidence, because it is what proves the rect measurement; the
screenshot (`native/<finding_id>/shot.png`-shaped ref, taken via `maestro screenshot`) comes
second, as the human-readable confirmation, exactly like every other driver's screenshot-second
convention in this file.
```

In `agents/fr-explorer.md`, add one paragraph (after its existing driver-agnostic guidance, wherever the file currently discusses attaching to a surface):
```markdown
On a `maestro` surface, `look` returns hierarchy text instead of an accessibility tree string --
read it the same way, but expect Maestro's own node vocabulary (`resource-id`, `bounds`) rather
than ARIA roles. There is no URL to navigate to: `goto` always just relaunches the app, so plan a
flow as a sequence of taps from the launch screen, not as a set of addressable routes.
```

In `agents/fr-lens.md`, add one paragraph:
```markdown
On a `maestro` surface, judge tap targets and overlapping controls exactly as you would rects on
web (rect.target-size, rect.overlap) -- the numbers are already dp-scaled for the device. There
is no color/contrast signal on this driver; do not invent one from a screenshot alone.
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py`
      Expected PASS: all green (including the new `test_surfaces_md_documents_the_maestro_driver` and the pre-existing `test_cli_parity`).
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/skills/flow-review/references/testing.md plugins/flow-review/skills/flow-review/references/evidence.md plugins/flow-review/skills/flow-review/references/surfaces.md plugins/flow-review/agents/fr-explorer.md plugins/flow-review/agents/fr-lens.md plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "docs(mobile): document the maestro driver in agent references"`

### Task T10: SKILL.md prerequisites + GO-gate `device-missing` gap

**Executor:** sonnet · **Depends:** T9 · **Wave:** 7
**Files:** `plugins/flow-review/skills/flow-review/SKILL.md`, `plugins/flow-review/engine/flow_review/plan.py`, `plugins/flow-review/engine/flow_review/test_plan.py`
**Interfaces:** Consumes: `envsetup.check_mobile_tools` (T4), `drift.runnable_surfaces` (M1/T1). Produces: `plan.plan(...)`'s per-surface `gaps` list gains a `{"type": "device_missing", ...}` entry for a `maestro` surface when no device is attached.
**Ponytail rung:** 5 (one line: reuse `check_mobile_tools`'s existing device check inside `plan()` rather than re-implementing it).

- [ ] Write the failing test.

```python
# plugins/flow-review/engine/flow_review/test_plan.py -- append
def test_plan_reports_device_missing_gap_for_a_maestro_surface(tmp_path, monkeypatch):
    _write_project(tmp_path, surfaces=[{
        "id": "mobile", "name": "Mobile", "kind": "ui", "driver": "maestro",
        "launch": "npx expo start --android",
        "options": {"app_id": "com.example"},
    }])
    monkeypatch.setattr(
        "flow_review.plan.envsetup.check_mobile_tools",
        lambda: ["adb reports no device in state 'device'. Start the emulator first."],
    )
    result = plan(tmp_path, "quick", goal="open the list")
    mobile = next(s for s in result["surfaces"] if s["surface_id"] == "mobile")
    assert {"type": "device_missing"} <= {k: v for k, v in mobile["gaps"][0].items() if k == "type"}
```

(If `test_plan.py` has a `_write_project` helper already, reuse it as shown; if it does not, add one matching the existing tests' inline `config.save(...)` pattern in that file instead -- read the file first and match its established fixture style rather than introducing a second one.)

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_plan.py::test_plan_reports_device_missing_gap_for_a_maestro_surface`
      Expected FAIL: `StopIteration` or `IndexError` (`mobile["gaps"]` is empty; `plan()` has no device check).

- [ ] Implement (complete).

In `plan.py`, add the import `from flow_review import envsetup` is already present (module already imports `envsetup`); inside the per-surface loop in `plan(...)`, after the existing `missing_creds` gap loop, add:
```python
        if surface.driver == "maestro":
            mobile_gaps = envsetup.check_mobile_tools()
            if any("no device" in g.lower() for g in mobile_gaps):
                gaps.append({"type": "device_missing", "message": mobile_gaps[-1]})
```

In `SKILL.md`, add a "Mobile prerequisites" subsection under the existing per-surface setup guidance (find the section that already lists web/tauri prerequisites and add this alongside it, matching its existing checklist format rather than introducing a new heading style):
```markdown
### Mobile prerequisites (maestro surfaces)

Before running a `maestro` surface, confirm with the user:

1. An Android emulator is running (`adb devices` shows one `device` line) -- e.g. start
   `Pixel_API_35` from Android Studio's Device Manager or `emulator -avd Pixel_API_35`.
2. Expo Go is installed in it (Play Store, or `adb install <path-to-expo-go.apk>`).
3. The surface's `start_cmd` (e.g. `npx expo start --android`) has been run by the user in the
   project directory and the app is open on the device -- the engine never runs this for you.
4. `maestro --version` succeeds. If not, tell the user to install it (`setup-env` prints the
   exact line).

If `plan` reports a `device_missing` gap, stop and ask the user to complete step 1 before
continuing; do not attempt to start an emulator yourself.
```

- [ ] Run: `python -m pytest -q plugins/flow-review/engine/flow_review/test_plan.py`
      Expected PASS: all green.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/plan.py plugins/flow-review/engine/flow_review/test_plan.py plugins/flow-review/skills/flow-review/SKILL.md && git commit -m "feat(plan): surface a device-missing GO-gate gap for maestro surfaces"`

## Checkpoints

### Task CP1: M3 checkpoint

**Executor:** opus · **Depends:** T1-T10 · **Wave:** 8

- [ ] Run the full suite: `python -m pytest -q -m "web or not web"`. Expected: all tests pass (M1 count plus every test added in T1-T10; no regressions).
- [ ] Clean-venv install: `uv venv <tmp>/frv && uv pip install --python <tmp>/frv/Scripts/python.exe "plugins/flow-review/engine[web]"` then, from outside the repo, `<tmp>/frv/Scripts/flow-review --help` exits 0.
- [ ] User pre-steps checklist (state which are done before continuing; do not attempt any of these yourself):
      - [ ] `Pixel_API_35` emulator running (`adb devices` shows one `device` line).
      - [ ] Expo Go installed in the emulator.
      - [ ] `cd plugins/flow-review/engine/fixtures/mobileapp && npm install && npx expo start --android` has been run and the app is open on the device.
      - [ ] `maestro --version` succeeds.
- [ ] Real headless run from a scratch copy of the fixture project: `claude -p "/flow-review quick open the list and refresh it" --plugin-dir <repo>/plugins/flow-review`.
- [ ] Confirm in the resulting run directory:
      - [ ] a `maestro` surface was proven (device attached, `hierarchy` returned a tree).
      - [ ] `rect.target-size` (the 32dp icon button) and `rect.overlap` (the List badge) findings are in the ledger.
      - [ ] the dead "Refresh" button appears as either a judgment finding or a `not-exercised` status, never silently dropped.
      - [ ] evidence refs for mobile findings are hierarchy excerpts first, screenshot second, both under `mobile/` (per the cross-milestone Canonical Interfaces "Evidence refs" rule).
      - [ ] no `.flow-review/recordings/` entries exist (record was off for this run).
      - [ ] no secrets appear anywhere in the run directory (`grep -r` for anything in the project's `.env`, if one exists, returns nothing).

## Appendix A: Decisions log

Extends the M2 plan's Appendix A (A-35..A-47).

| # | Topic | Decision |
|---|---|---|
| A-53 | Driver construction: `driver_name`/`options` | `web/drive.py::serve(..., *, driver_name="playwright", options=None, ...)` and `build_driver(driver_name, *, headless, viewport, options)` (uniform `factory(headless, viewport, options or {})` call for every entry in `DRIVER_FACTORIES`, no playwright special case) are canonical from M2 onward; `cmd_start` reads `surface.driver`/`surface.options` and passes `--driver`/`--driver-options` (JSON) to the spawned `serve` subprocess. M3 only adds the `"maestro"` entry; M4's `http`/`shell` factories reuse the same signature. |
| A-54 | (drafter proposal, confirm at review) `Candidate.options` | `audit.Candidate` gains an `options: dict` field (default `{}`), first used by M2's `tauri` candidate and reused here by `_from_expo` to carry `app_id`/`start_cmd` for the setup agent to copy into the surface's `options` when it authors `config.json` -- the engine never writes `config.json` itself (A-19/A-20). |
| A-55 | (drafter proposal, confirm at review) Maestro CLI output parsing | `mobile/maestro.py::run_flow` parses `maestro test`'s human-readable stdout with a regex (`\[(\d+)\][^\n]*\n\s*FAILED`) rather than requiring a `--format json` flag, since Maestro does not currently document one; every test mocks this output, so a real-CLI format change is caught by a future run against a real device, not silently. |
| A-56 | (drafter proposal, confirm at review) `is_password` on mobile | `MobileDriver.is_password` reads a hierarchy node's `password` attribute (Maestro exposes this for `EditText` fields marked as password input) rather than trying to type into the field first; a locator that resolves to no node returns `False`, matching `WebDriver.is_password`'s fail-open-to-false behavior for an unresolved locator. |
| A-57 | (drafter proposal, confirm at review) No console/network signal on mobile | `MobileDriver.console_errors_since_check()`/`network_log_since_check()` always return `[]`; `console.error` and `http.5xx` findings never fire for a `maestro` surface in M3. A future milestone could wire `adb logcat` for the former if a real run shows the gap matters; out of scope here (ponytail: no speculative logcat parser before a concrete need). |
| A-58 | (drafter proposal, confirm at review) `--variants` on maestro | `replay`'s `--variants` flag is accepted but produces one `not-exercised` status event with `reason=variants-unsupported` for every maestro flow, rather than raising or silently doing nothing -- consistent with A-37's "an unfilled input reports rather than guesses" precedent. |
| A-59 | (drafter proposal, confirm at review) Secret fills on mobile never touch a flow file | `MobileDriver.fill`/`mobile/yaml.py::to_maestro` write `inputText: ${<ENV_NAME>}` for a secret/`from_env` fill, never the resolved value; the live driver passes the value only via `mobile/maestro.py::run_flow`'s `env` (`maestro -e KEY=VALUE`), so no `.flow-review-mobile-tmp`/`<run_dir>/maestro/**` file or committed `<recordings>/**/*.yaml` ever contains a secret in plain text. |
| A-60 | (drafter proposal, confirm at review) `screen_route` heuristic | A mobile finding's `route` is the current screen's first node with non-empty `text` and parseable `bounds`, ordered top-left (`(y, x)` ascending); the mobileapp fixture (T2) gives every screen an explicit heading Text with exactly that screen's name ("Home"/"List"/"Detail") as its first child, specifically so this heuristic is stable and matches `planted.json`'s `route` values without depending on a real device's font metrics or layout timing. |
| A-61 | (drafter proposal, confirm at review) Dead-control findings are never benchmarked | `planted.json` never lists a rule the engine cannot check mechanically (e.g. "this button does nothing"); the mobileapp fixture's dead "Refresh" button stays in the app as a judgment-finding exercise for the lens/cold-eyes agents (README), but `bench` (M5) only ever scores rule ids `planted.json` names. |

## QUESTIONS

- none
