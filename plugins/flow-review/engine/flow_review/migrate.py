"""v1 -> v2 config auto-migration (A-5).

Runs on load, silently on unattended paths. Never guesses at a v1 field's meaning beyond what
A-5 states explicitly: name/kind/driver/launch/preconditions/provenance carry over as-is,
destructive becomes state, lens_sets/evidence_types/tester_agent are dropped. A backup of the
untouched original bytes is always written first, because an auto-migration that cannot be
undone is a rewrite, not a migration.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from flow_review import config as cfgmod

_V1_SURFACE_KNOWN = {
    "name", "kind", "driver", "launch", "preconditions", "destructive", "provenance",
}
_V1_TOP_KNOWN = {
    "schema_version", "generator_version", "surfaces", "lens_sets", "tester_agent",
    "evidence_types", "flows_hash",
}


def is_v1(raw: dict) -> bool:
    return raw.get("schema_version", 1) <= 1


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "surface"


@dataclass
class MigrationSummary:
    surfaces_migrated: int = 0
    dropped_keys: list[str] = field(default_factory=list)
    destructive_to_persistent: list[str] = field(default_factory=list)
    id_collisions_resolved: dict[str, str] = field(default_factory=dict)
    backup_name: str = "config.v1.bak"

    def render(self) -> str:
        lines = [
            "flow-review: migrated config from schema v1 to v2.",
            f"  {self.surfaces_migrated} surface(s) migrated.",
        ]
        if self.destructive_to_persistent:
            lines.append("  destructive -> persistent: " + ", ".join(self.destructive_to_persistent))
        if self.dropped_keys:
            lines.append("  dropped (no longer used): " + ", ".join(self.dropped_keys))
        lines.append(f"  a backup of the old file was saved to {self.backup_name}")
        return "\n".join(lines)


def migrate(raw: dict) -> tuple[cfgmod.Config, MigrationSummary]:
    summary = MigrationSummary()
    dropped: set[str] = set()
    for key in raw:
        if key not in _V1_TOP_KNOWN:
            dropped.add(key)
    for key in ("lens_sets", "tester_agent", "evidence_types"):
        if key in raw:
            dropped.add(key)
    summary.dropped_keys = sorted(dropped)

    surfaces: list[cfgmod.Surface] = []
    used_ids: dict[str, int] = {}
    for entry in raw.get("surfaces", []):
        for key in entry:
            if key not in _V1_SURFACE_KNOWN:
                if key not in summary.dropped_keys:
                    summary.dropped_keys.append(key)

        name = entry.get("name", "")
        base_id = _slug(name)
        count = used_ids.get(base_id, 0) + 1
        used_ids[base_id] = count
        surface_id = base_id if count == 1 else f"{base_id}-{count}"
        if count > 1:
            summary.id_collisions_resolved[name] = surface_id

        state = "persistent" if entry.get("destructive") else "disposable"
        if entry.get("destructive"):
            summary.destructive_to_persistent.append(surface_id)

        surfaces.append(cfgmod.Surface(
            id=surface_id,
            name=name,
            kind=entry.get("kind", ""),
            driver=entry.get("driver", ""),
            launch=entry.get("launch", ""),
            preconditions=entry.get("preconditions", []),
            state=state,
            provenance=entry.get("provenance", {}),
        ))
        summary.surfaces_migrated += 1

    summary.dropped_keys = sorted(set(summary.dropped_keys))
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION,
        generator_version=raw.get("generator_version", ""),
        surfaces=surfaces,
        flows_hash=raw.get("flows_hash", ""),
    )
    return cfg, summary


def migrate_file(path: Path, quiet: bool = False) -> MigrationSummary | None:
    path = Path(path)
    if not path.exists():
        return None
    original = path.read_bytes()
    raw = json.loads(original.decode("utf-8"))
    if not is_v1(raw):
        return None

    backup = path.with_name(path.stem + ".v1.bak")
    backup.write_bytes(original)

    cfg, summary = migrate(raw)
    summary.backup_name = backup.name
    cfgmod.save(cfg, path)
    if not quiet:
        print(summary.render())
    return summary
