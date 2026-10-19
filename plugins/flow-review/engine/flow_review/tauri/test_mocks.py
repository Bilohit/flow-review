import json
from pathlib import Path

import pytest

_FIXTURE_SRC_TAURI = (
    Path(__file__).resolve().parents[2] / "fixtures" / "tauriapp" / "src-tauri"
)


def test_scan_commands_finds_tauri_command_fns(tmp_path):
    from flow_review.tauri.mocks import scan_commands
    src_tauri = tmp_path / "src-tauri"
    (src_tauri / "src").mkdir(parents=True)
    (src_tauri / "src" / "commands.rs").write_text(
        "#[tauri::command]\nfn load_items() -> Vec<Item> { vec![] }\n\n"
        "#[tauri::command]\npub fn save_note(text: String) -> Result<(), String> { Ok(()) }\n",
        encoding="utf-8",
    )
    assert sorted(scan_commands(src_tauri)) == ["load_items", "save_note"]


@pytest.mark.parametrize(
    "snippet,expected",
    [
        pytest.param(
            '#[tauri::command(rename_all = "snake_case")]\nfn load_items() {}\n',
            ["load_items"],
            id="attribute-args",
        ),
        pytest.param(
            "#[tauri::command]\npub async fn load_items() {}\n",
            ["load_items"],
            id="pub-async-fn",
        ),
        pytest.param(
            "#[tauri::command]\nasync fn load_items() {}\n",
            ["load_items"],
            id="bare-async-fn",
        ),
        pytest.param(
            "#[tauri::command]\n#[allow(dead_code)]\nfn load_items() {}\n",
            ["load_items"],
            id="attribute-between",
        ),
        pytest.param(
            "// #[tauri::command]\nfn load_items() {}\n",
            [],
            id="commented-out-not-matched",
        ),
        pytest.param(
            "#[tauri::command] // exposed to the UI\nfn load_items() {}\n",
            ["load_items"],
            id="trailing-comment",
        ),
        pytest.param(
            "#[tauri::command] fn load_items() {}\n",
            ["load_items"],
            id="same-line-fn",
        ),
        pytest.param(
            "#[tauri::command]\n/// Loads the items.\n/// Second line.\npub fn load_items() {}\n",
            ["load_items"],
            id="doc-comments-between",
        ),
    ],
)
def test_scan_commands_handles_real_tauri_shapes(tmp_path, snippet, expected):
    from flow_review.tauri.mocks import scan_commands
    src_tauri = tmp_path / "src-tauri"
    (src_tauri / "src").mkdir(parents=True)
    (src_tauri / "src" / "commands.rs").write_text(snippet, encoding="utf-8")
    assert sorted(scan_commands(src_tauri)) == expected


def test_scan_commands_finds_exactly_fixture_commands():
    from flow_review.tauri.mocks import scan_commands
    assert sorted(scan_commands(_FIXTURE_SRC_TAURI)) == ["load_items", "save_note"]


def test_write_stubs_never_overwrites_a_filled_value(tmp_path):
    from flow_review.tauri.mocks import write_stubs
    path = tmp_path / "tauri-mocks.json"
    path.write_text(json.dumps({"save_note": {"ok": True}}), encoding="utf-8")
    added = write_stubs(path, ["load_items", "save_note"])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert added == 1
    assert data["load_items"] is None
    assert data["save_note"] == {"ok": True}


def test_write_stubs_raises_value_error_on_corrupt_json(tmp_path):
    from flow_review.tauri.mocks import write_stubs
    path = tmp_path / "tauri-mocks.json"
    original = b"{not valid json"
    path.write_bytes(original)
    with pytest.raises(ValueError, match=re_escape_path(path)):
        write_stubs(path, ["load_items"])
    assert path.read_bytes() == original


def test_write_stubs_raises_value_error_on_non_object_json(tmp_path):
    from flow_review.tauri.mocks import write_stubs
    path = tmp_path / "tauri-mocks.json"
    original = b"[1, 2, 3]"
    path.write_bytes(original)
    with pytest.raises(ValueError, match=re_escape_path(path)):
        write_stubs(path, ["load_items"])
    assert path.read_bytes() == original


def re_escape_path(path: Path) -> str:
    import re
    return re.escape(str(path))


def test_init_script_shape_matches_mock_ipc():
    from flow_review.tauri.mocks import init_script
    script = init_script({"load_items": [{"id": 1}]})
    assert "__TAURI_INTERNALS__" in script
    assert "invoke" in script
    assert "load_items" in script


def test_init_script_reject_sentinel_rejects_and_null_still_resolves():
    from flow_review.tauri.mocks import init_script
    script = init_script({"save_note": {"$reject": "disk full"}, "load_items": None})
    assert "Promise.reject" in script
    assert '"$reject"' in script
    # null stubs still resolve null and are tracked as mock-missing
    assert "Promise.resolve(value)" in script and "__flowReviewMissingMocks.push" in script


def test_scan_commands_skips_target_dir_and_tolerates_non_utf8(tmp_path):
    from flow_review.tauri.mocks import scan_commands
    src_tauri = tmp_path / "src-tauri"
    (src_tauri / "src").mkdir(parents=True)
    (src_tauri / "src" / "commands.rs").write_bytes(
        b"// caf\xe9\n#[tauri::command]\nfn load_items() {}\n")
    generated = src_tauri / "target" / "debug" / "build" / "x" / "out"
    generated.mkdir(parents=True)
    (generated / "gen.rs").write_text("#[tauri::command]\nfn generated_cmd() {}\n",
                                      encoding="utf-8")
    # only src-tauri/target is cargo's; an app module named target/ is still scanned
    (src_tauri / "src" / "target").mkdir()
    (src_tauri / "src" / "target" / "mod.rs").write_text("#[tauri::command]\nfn aim() {}\n",
                                                         encoding="utf-8")
    assert scan_commands(src_tauri) == ["load_items", "aim"]


def test_init_script_tracks_absent_commands_as_missing_too():
    from flow_review.tauri.mocks import init_script
    script = init_script({"load_items": []})
    # a command absent from the mocks resolves null and is tracked just like a null stub
    assert "if (value === null && !String(cmd).startsWith('plugin:'))" in script


def test_init_script_provides_current_window_metadata():
    # @tauri-apps/api v2 getCurrentWindow() reads __TAURI_INTERNALS__.metadata and throws without it
    from flow_review.tauri.mocks import init_script
    script = init_script({})
    assert "metadata: {currentWindow: {label: 'main'}," in script
    assert "currentWebview: {windowLabel: 'main', label: 'main'}}" in script
