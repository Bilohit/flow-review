from __future__ import annotations

import json

from flow_review import audit


def test_detects_a_web_dev_server_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "demo", "scripts": {"dev": "vite", "test": "vitest run"}
    }, indent=2), encoding="utf-8")
    found = audit.detect(tmp_path)
    web = [c for c in found if c.kind == "ui"]
    assert web, "a dev script should propose a ui surface"
    assert web[0].launch == "npm run dev"
    assert "package.json:" in web[0].evidence
    assert "vite" in web[0].evidence


def test_package_json_cites_the_dev_key_not_a_colliding_devdependencies_value(tmp_path):
    # "vite" appears as both the dev script's value and a devDependencies key, so a
    # value-based (or bare-word) search could land on the wrong line. indent=2 keeps
    # every entry on its own line so the citation can be checked precisely.
    text = json.dumps({
        "name": "demo",
        "scripts": {"dev": "vite"},
        "devDependencies": {"vite": "^5.0.0"},
    }, indent=2)
    (tmp_path / "package.json").write_text(text, encoding="utf-8")
    lines = text.splitlines()
    dev_line = next(i for i, line in enumerate(lines, 1) if '"dev":' in line)
    found = audit.detect(tmp_path)
    web = [c for c in found if c.kind == "ui"]
    assert web
    assert web[0].evidence == audit.EVIDENCE_FORMAT.format(
        path="package.json", line=dev_line, snippet=lines[dev_line - 1].strip()
    )


def test_detects_a_cli_entry_point_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\ndemo = "demo.cli:main"\n', encoding="utf-8")
    found = audit.detect(tmp_path)
    cli = [c for c in found if c.kind == "cli"]
    assert cli
    assert cli[0].launch == "demo"
    assert "pyproject.toml:" in cli[0].evidence


def test_pyproject_cites_the_scripts_line_not_the_colliding_project_name_line(tmp_path):
    # Both the [project] name and the [project.scripts] entry say "demo", so a substring
    # search for "demo" would stop at the first (wrong) line. Line numbers are asserted
    # directly -- a substring check would pass on either line for the wrong reason.
    text = (
        '[project]\n'
        'name = "demo"\n'
        '\n'
        '[project.scripts]\n'
        'demo = "demo.cli:main"\n'
    )
    (tmp_path / "pyproject.toml").write_text(text, encoding="utf-8")
    scripts_line = text.splitlines().index('demo = "demo.cli:main"') + 1
    name_line = text.splitlines().index('name = "demo"') + 1
    assert scripts_line != name_line
    found = audit.detect(tmp_path)
    cli = [c for c in found if c.kind == "cli"]
    assert cli
    assert cli[0].evidence == audit.EVIDENCE_FORMAT.format(
        path="pyproject.toml", line=scripts_line, snippet='demo = "demo.cli:main"'
    )


def test_detects_an_api_surface_from_an_openapi_file(tmp_path):
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    found = audit.detect(tmp_path)
    assert any(c.kind == "api" for c in found)


def test_swagger_file_cites_the_file_with_no_fabricated_line(tmp_path):
    # A genuine Swagger 2.0 file never contains the word "openapi" -- a needle search for
    # that literal has nothing real to find, so the finding has to be "this file exists",
    # not a line.
    (tmp_path / "swagger.yaml").write_text('swagger: "2.0"\ninfo:\n  title: demo\n', encoding="utf-8")
    found = audit.detect(tmp_path)
    api = [c for c in found if c.kind == "api"]
    assert api
    assert api[0].evidence == audit.EVIDENCE_FORMAT_NO_LINE.format(path="swagger.yaml")
    assert "openapi" not in api[0].evidence
    assert ":1 ->" not in api[0].evidence


def test_an_empty_repo_proposes_nothing_rather_than_guessing(tmp_path):
    assert audit.detect(tmp_path) == []


def test_every_candidate_kind_is_valid(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    from flow_review.config import VALID_KINDS
    found = audit.detect(tmp_path)
    assert found, "the fixture should have produced at least one candidate"
    for candidate in found:
        assert candidate.kind in VALID_KINDS


def test_package_json_cites_the_scripts_entry_not_an_earlier_object_with_the_same_key(tmp_path):
    """Quoting the key rules out "devDependencies", but not a literal "dev" key of its own."""
    text = json.dumps({
        "name": "demo",
        "config": {"dev": True},
        "scripts": {"dev": "vite"},
    }, indent=2)
    (tmp_path / "package.json").write_text(text, encoding="utf-8")
    lines = text.splitlines()
    scripts_at = next(i for i, line in enumerate(lines, 1) if '"scripts"' in line)
    wanted = next(i for i, line in enumerate(lines, 1) if i > scripts_at and '"dev"' in line)
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web
    assert web[0].evidence == f"package.json:{wanted} -> \"dev\": \"vite\""


def test_a_dev_script_with_no_locatable_line_still_yields_a_surface(tmp_path):
    """json.loads found the script, so the surface is real; cite the file rather than drop it."""
    # JSON tolerates a newline between a key and its colon; the per-line search does not, so
    # this is a file whose key is real to a parser and invisible to a grep.
    text = '\n'.join(['{"scripts": {"dev"', ': "vite"}}'])
    (tmp_path / "package.json").write_text(text, encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web, "a script json.loads can see must not vanish because the raw text hid it"
    assert web[0].launch == "npm run dev"
    assert web[0].evidence == "package.json (file present)"


def test_web_candidate_driver_is_playwright_not_cdp(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web[0].driver == "playwright"


def test_poetry_scripts_table_is_detected(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "demo"\n\n[tool.poetry.scripts]\ndemo = "demo.cli:main"\n',
        encoding="utf-8",
    )
    cli = [c for c in audit.detect(tmp_path) if c.kind == "cli"]
    assert cli
    assert cli[0].launch == "demo"
    assert "pyproject.toml:" in cli[0].evidence


def test_poetry_and_pep621_scripts_are_not_duplicated(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\ndemo = "demo.cli:main"\n\n'
        '[tool.poetry.scripts]\ndemo = "demo.cli:main"\n',
        encoding="utf-8",
    )
    cli = [c for c in audit.detect(tmp_path) if c.kind == "cli" and c.launch == "demo"]
    assert len(cli) == 1


def test_npm_workspace_member_is_detected_with_its_own_name(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/*"]}), encoding="utf-8")
    member = tmp_path / "packages" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web
    assert web[0].name == "web"
    assert web[0].evidence.startswith("packages")


def test_pnpm_workspace_yaml_member_is_detected(tmp_path):
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n", encoding="utf-8")
    member = tmp_path / "apps" / "site"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "next dev"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert any(c.name == "site" for c in web)


def test_workspace_double_star_glob_finds_a_nested_member(tmp_path):
    # A-23: workspace globs use Path.glob directly, so ** works exactly as Path.glob's own
    # recursive-match syntax -- no special-casing needed for it in this module.
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/**"]}), encoding="utf-8")
    member = tmp_path / "packages" / "group" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert any(c.name == "web" for c in web)


def test_workspace_brace_list_glob_is_unsupported_and_matches_nothing(tmp_path):
    # A-23: brace lists ("{a,b}") are not Path.glob syntax and are not special-cased here --
    # the pattern simply matches nothing extra, it never raises.
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/{web,api}"]}), encoding="utf-8")
    member = tmp_path / "packages" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web == []


def test_tauri_src_tauri_dir_is_pending_driver(tmp_path):
    (tmp_path / "src-tauri").mkdir()
    found = audit.detect(tmp_path)
    tauri = [c for c in found if c.driver == "pending" and "tauri" in c.evidence.lower() or "src-tauri" in c.evidence]
    assert tauri
    assert tauri[0].launch == ""


def test_expo_app_json_is_pending_driver(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"expo": {"name": "demo"}}), encoding="utf-8")
    found = audit.detect(tmp_path)
    assert any(c.driver == "pending" and "app.json" in c.evidence for c in found)


def test_a_plain_app_json_with_no_expo_key_is_not_detected(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")
    found = audit.detect(tmp_path)
    assert not any(c.driver == "pending" and "app.json" in c.evidence for c in found)


def test_electron_dependency_is_pending_driver(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "devDependencies": {"electron": "^30.0.0"},
    }, indent=2), encoding="utf-8")
    found = audit.detect(tmp_path)
    electron = [c for c in found if c.driver == "pending" and "electron" not in c.name]
    assert any(c.driver == "pending" for c in found)


def test_pending_driver_is_valid_per_config():
    from flow_review.config import VALID_DRIVERS
    assert "pending" in VALID_DRIVERS
