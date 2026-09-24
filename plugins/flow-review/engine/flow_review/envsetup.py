"""Managed venv setup, .flow-review scaffolding, and a dependency-free .env loader (A-10).

Every subprocess interaction is injected (`runner`) and every `which` lookup is injected too --
this module is exercised entirely against fakes; nothing here ever spawns uv/pip/venv for real
or touches the network in this suite. That is a requirement of this task, not an incidental
convenience: setup-env is exactly the kind of command a CI run or a sandboxed test box cannot
actually execute, so the logic that decides WHAT to run has to be testable independently of
actually running it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VENV_DIRNAME = ".venv"
_MARKER_NAME = ".flow-review-setup.json"


@dataclass
class SetupResult:
    created: bool
    used_uv: bool
    venv_path: Path
    commands_run: list[list[str]] = field(default_factory=list)


def find_uv(which=shutil.which) -> str | None:
    return which("uv")


def _venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _run(runner, cmd: list[str]) -> None:
    result = runner(cmd)
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError(f"command failed: {cmd}")


def setup_env(
    project_dir: Path, engine_path: Path, extras: str = "web",
    runner=subprocess.run, which=shutil.which,
) -> SetupResult:
    project_dir = Path(project_dir)
    engine_path = Path(engine_path)
    flow_review_dir = project_dir / ".flow-review"
    venv_path = flow_review_dir / VENV_DIRNAME
    marker = venv_path / _MARKER_NAME

    desired = {"extras": extras, "engine_path": str(engine_path)}
    if marker.exists():
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError:
            existing = None
        if existing == desired:
            return SetupResult(created=False, used_uv=False, venv_path=venv_path)

    flow_review_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    uv = find_uv(which)

    if uv:
        create_cmd = [uv, "venv", str(venv_path)]
        _run(runner, create_cmd)
        commands.append(create_cmd)
        install_cmd = [uv, "pip", "install", "--python", str(_venv_python(venv_path)), f"{engine_path}[{extras}]"]
        _run(runner, install_cmd)
        commands.append(install_cmd)
        used_uv = True
    else:
        create_cmd = [sys.executable, "-m", "venv", str(venv_path)]
        _run(runner, create_cmd)
        commands.append(create_cmd)
        install_cmd = [str(_venv_python(venv_path)), "-m", "pip", "install", f"{engine_path}[{extras}]"]
        _run(runner, install_cmd)
        commands.append(install_cmd)
        used_uv = False

    venv_path.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(desired), encoding="utf-8")
    return SetupResult(created=True, used_uv=used_uv, venv_path=venv_path, commands_run=commands)


def write_gitignore(flow_review_dir: Path, commit_recordings: bool = True) -> None:
    flow_review_dir = Path(flow_review_dir)
    flow_review_dir.mkdir(parents=True, exist_ok=True)
    lines = [".env", ".venv/", "runs/"]
    if not commit_recordings:
        lines.append("recordings/")
    (flow_review_dir / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")


_MIN_SECRET_LEN = 4


def secret_names(cfg) -> set[str]:
    """A-26: the env-var names some surface's `creds` points at -- the only .env values that
    are secrets. Registering every value (DEBUG=1, PORT=3000) blanked those substrings in every
    event, timestamps included."""
    return {name for surface in cfg.surfaces for name in (surface.creds or {}).values()}


def load_dotenv(path: Path, environ: dict | None = None, secret_names=()) -> dict[str, str]:
    from flow_review import events  # local import: envsetup must not force events' import cost
                                     # onto every caller that only wants the .gitignore writer

    target = os.environ if environ is None else environ
    path = Path(path)
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        parsed[key] = value
        if key in secret_names and len(value) >= _MIN_SECRET_LEN:
            events.register_secret(value)
        target[key] = value
    return parsed


def resolve_env(name: str, project_root: Path | None, secret_names=()) -> str | None:
    """os.environ first, then <project_root>/.flow-review/.env (A-26). The resolved value is
    registered as a secret -- it is only ever asked for to type into a credential field.

    A-26 / CP3 finding 1: only names the surface's `creds` actually points at may be resolved.
    Anything else -- an arbitrary os.environ name a CSRF-forged drive request asked for -- is
    treated exactly like a missing one, so callers hit the existing missing-env error path.
    """
    from flow_review import events

    if name not in secret_names:
        return None

    value = os.environ.get(name)
    if value is None and project_root is not None:
        dotenv = load_dotenv(Path(project_root) / ".flow-review" / ".env", environ={},
                             secret_names=set(secret_names) | {name})
        value = dotenv.get(name)
    if value:
        events.register_secret(value)
    return value


def project_secret_names(project_root: Path | None) -> set[str]:
    """secret_names() for the project's config, or empty when it has none/unreadable."""
    if project_root is None:
        return set()
    try:
        from flow_review import config as configmod
        return secret_names(configmod.load(Path(project_root) / ".flow-review" / "config.json"))
    except Exception:
        return set()
