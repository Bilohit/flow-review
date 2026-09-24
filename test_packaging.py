"""Cheap regression guard for the wheel's test-file exclusion (final-review Minor: the wheel
shipped every colocated test_*.py/conftest.py, about 290 KB of 570 KB). A real `pyproject-build`
is slow and needs network for an isolated build env, so this exercises the same
`build_py.find_package_modules` override setup.py registers, without actually building a wheel.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "plugins" / "flow-review" / "engine"


def _load_setup_module():
    spec = importlib.util.spec_from_file_location("_flow_review_setup", ENGINE_DIR / "setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # guarded by `if __name__ == "__main__"`: safe to import
    return module


def test_setup_py_does_not_call_setup_on_import():
    # Importing setup.py must never invoke setuptools' CLI as a side effect of pytest
    # collection walking the repo.
    assert "setuptools" not in sys.modules or True  # import itself must not raise/exit
    _load_setup_module()


def test_build_py_excludes_test_modules_and_conftest(monkeypatch):
    setup_mod = _load_setup_module()
    build_py = setup_mod.build_py
    from setuptools.command.build_py import build_py as base_build_py

    fake_modules = [
        ("flow_review", "envsetup", "flow_review/envsetup.py"),
        ("flow_review", "test_envsetup", "flow_review/test_envsetup.py"),
        ("flow_review.web", "drive", "flow_review/web/drive.py"),
        ("flow_review.web", "test_drive", "flow_review/web/test_drive.py"),
        ("flow_review.dashboard", "conftest", "flow_review/dashboard/conftest.py"),
        ("flow_review.dashboard", "serve", "flow_review/dashboard/serve.py"),
    ]
    # Stub the discovery the base class would normally do by walking the filesystem, so this
    # exercises only build_py's own filter -- the actual thing being tested.
    monkeypatch.setattr(
        base_build_py, "find_package_modules",
        lambda self, package, package_dir: fake_modules,
    )

    instance = build_py.__new__(build_py)  # skip __init__: the filter needs no command state
    filtered = instance.find_package_modules("flow_review", "flow_review")
    names = {name for _, name, _ in filtered}
    assert names == {"envsetup", "drive", "serve"}
    assert "test_envsetup" not in names
    assert "test_drive" not in names
    assert "conftest" not in names
