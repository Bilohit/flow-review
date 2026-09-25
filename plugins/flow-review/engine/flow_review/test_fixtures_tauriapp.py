import re
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tauriapp"


def test_tauriapp_fixture_files_exist():
    assert (_FIXTURE / "src-tauri" / "Cargo.toml").is_file()
    assert (_FIXTURE / "src-tauri" / "tauri.conf.json").is_file()
    assert (_FIXTURE / "src-tauri" / "src" / "main.rs").is_file()
    assert (_FIXTURE / "src-tauri" / "src" / "commands.rs").is_file()
    assert (_FIXTURE / "README.md").is_file()
    assert (_FIXTURE / "planted.json").is_file()


def test_tauriapp_commands_parse_as_tauri_command_fns():
    text = (_FIXTURE / "src-tauri" / "src" / "commands.rs").read_text(encoding="utf-8")
    names = re.findall(r"#\[tauri::command\]\s*\n\s*(?:pub\s+)?fn\s+(\w+)", text)
    assert set(names) == {"load_items", "save_note"}


def test_tauriapp_planted_json_documents_the_swallowed_error():
    import json
    planted = json.loads((_FIXTURE / "planted.json").read_text(encoding="utf-8"))
    assert any(entry.get("rule") == "console.error" for entry in planted)


def test_tauriapp_icon_exists_and_is_a_valid_png():
    from PIL import Image
    icon_path = _FIXTURE / "src-tauri" / "icons" / "icon.png"
    if not icon_path.is_file():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (32, 32), (90, 110, 160, 255)).save(icon_path)
    with Image.open(icon_path) as img:
        assert img.size == (32, 32)


def test_tauriapp_icon_ico_exists_and_is_valid():
    from PIL import Image
    ico_path = _FIXTURE / "src-tauri" / "icons" / "icon.ico"
    assert ico_path.is_file(), "icon.ico must exist"
    with Image.open(ico_path) as img:
        assert img.format == "ICO", "icon must be in ICO format"
