from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # plugins/flow-review (test file is at
                                              # plugins/flow-review/engine/flow_review/test_repo_hygiene.py)


def test_no_inline_python_dash_c_in_skills_or_agents_or_readme():
    targets = [
        _ROOT / "skills",
        _ROOT / "agents",
        _ROOT / "README.md",
        _ROOT.parents[1] / "README.md",  # repo root
    ]
    offenders = []
    for target in targets:
        if not target.exists():
            continue
        files = [target] if target.is_file() else list(target.rglob("*"))
        for path in files:
            if path.is_dir():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            if "python -c" in text or "python3 -c" in text:
                offenders.append(str(path))
    assert offenders == [], f"inline python -c found in: {offenders}"
