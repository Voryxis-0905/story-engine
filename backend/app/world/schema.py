"""World/save schema versioning, file catalog and controlled migration.

The catalog is the single source of truth for what belongs to a world and must
travel with save/restore/branch/export. Cache/index files are listed separately
so a new feature cannot be forgotten from snapshots, and so we can tell core
data apart from things that can be rebuilt.
"""
import json
import os
import shutil
import time

from app.world.templates import TEMPLATES, SCHEMA_VERSION

# Core persisted state: saved, restored, branched, exported and migrated as one.
CORE_STATE_FILES = dict(TEMPLATES)

# Rebuildable / derived data. Not copied by snapshots; regenerated on demand.
CACHE_FILES = frozenset({"saves_index.json", "turn_receipts.json"})

BACKUP_DIRNAME = "schema_backups"


class SchemaVersionError(Exception):
    def __init__(self, message: str, *, version=None, supported=SCHEMA_VERSION):
        super().__init__(message)
        self.version = version
        self.supported = supported


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.migrate.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def read_schema_version(world_path: str) -> int:
    """Return the stored schema version, defaulting to 1 for legacy worlds.

    Raises SchemaVersionError instead of guessing when the file is unreadable.
    """
    config_path = os.path.join(world_path, "world_config.json")
    if not os.path.isfile(config_path):
        return 1
    try:
        config = _read_json(config_path)
    except (json.JSONDecodeError, OSError) as error:
        raise SchemaVersionError(
            f"world_config.json is not readable JSON ({error}); refusing to migrate or overwrite it."
        ) from error
    if not isinstance(config, dict):
        raise SchemaVersionError("world_config.json must contain a JSON object.")
    version = config.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise SchemaVersionError(f"world_config.json has an invalid schema_version: {version!r}")
    return version


def _corrupt_core_files(world_path: str) -> list:
    corrupt = []
    for filename in CORE_STATE_FILES:
        path = os.path.join(world_path, filename)
        if not os.path.isfile(path):
            continue
        try:
            _read_json(path)
        except (json.JSONDecodeError, OSError):
            corrupt.append(filename)
    return corrupt


def _backup_world(world_path: str, from_version: int) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    backup_dir = os.path.join(world_path, BACKUP_DIRNAME, f"v{from_version}_{stamp}")
    os.makedirs(backup_dir, exist_ok=True)
    for filename in CORE_STATE_FILES:
        source = os.path.join(world_path, filename)
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(backup_dir, filename))
    return backup_dir


def _migrate_v1_to_v2(world_path: str, config: dict) -> dict:
    """v1 -> v2 is additive: v2 only formalizes the version marker/file catalog."""
    return config


def _migrate_v2_to_v3(world_path: str, config: dict) -> dict:
    """v2 -> v3 adds the monotonic world revision used for stale-write checks."""
    config.setdefault("revision", 0)
    return config


def _migrate_v3_to_v4(world_path: str, config: dict) -> dict:
    """v3 -> v4 records the pre-turn snapshot used by regenerate."""
    config.setdefault("pre_turn_snapshot", None)
    return config


def _migrate_v4_to_v5(world_path: str, config: dict) -> dict:
    """v4 -> v5 adds the discovery store (created from the file catalog)."""
    return config


def _migrate_v5_to_v6(world_path: str, config: dict) -> dict:
    """v5 -> v6 persists resumable narrative journeys."""
    config.setdefault("active_journey", None)
    return config


MIGRATIONS = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
    4: _migrate_v4_to_v5,
    5: _migrate_v5_to_v6,
}


def ensure_current_schema(world_path: str, *, create_missing: bool = True) -> dict:
    """Bring a world up to the current schema. Idempotent and backup-first."""
    config_path = os.path.join(world_path, "world_config.json")
    recovered = []
    if os.path.isfile(config_path):
        try:
            config = _read_json(config_path)
        except (json.JSONDecodeError, OSError) as error:
            raise SchemaVersionError(
                f"world_config.json is not readable JSON ({error}); refusing to migrate or overwrite it."
            ) from error
        if not isinstance(config, dict):
            raise SchemaVersionError("world_config.json must contain a JSON object.")
        version = config.get("schema_version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SchemaVersionError(f"world_config.json has an invalid schema_version: {version!r}")
    else:
        # A world without world_config is a damaged world, not a valid v1 one.
        # Rebuild it from the full template (never a config with only a version)
        # and report the recovery so callers can warn.
        config = dict(CORE_STATE_FILES["world_config.json"])
        config.pop("schema_version", None)
        version = 1
        recovered = ["world_config.json"]

    if version > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"World data version {version} is newer than this app supports (max {SCHEMA_VERSION}). "
            "Update Story Engine or import the world with a compatible build.",
            version=version,
        )
    if version == SCHEMA_VERSION:
        return {"migrated": False, "version": version, "backup": None, "recovered": []}

    corrupt = _corrupt_core_files(world_path)
    if corrupt:
        raise SchemaVersionError(
            "Refusing to migrate: these files are not valid JSON and would be lost: "
            + ", ".join(sorted(corrupt))
        )

    backup_dir = _backup_world(world_path, version)

    if create_missing:
        for filename, template in CORE_STATE_FILES.items():
            path = os.path.join(world_path, filename)
            if not os.path.isfile(path):
                if filename == "world_config.json":
                    # Already seeded from the full template above.
                    continue
                if isinstance(template, dict):
                    _write_json(path, template)
                    recovered.append(filename)
                else:
                    raise SchemaVersionError(f"No template available for missing file {filename}")

    migrated = config
    for step in range(version, SCHEMA_VERSION):
        migration = MIGRATIONS.get(step)
        if migration is None:
            raise SchemaVersionError(f"Missing migration step v{step} -> v{step + 1}")
        migrated = migration(world_path, migrated)

    migrated["schema_version"] = SCHEMA_VERSION
    if not migrated.get("display_name") and not os.path.isfile(config_path):
        # Guard: never certify a config that is still empty after a "recovery".
        migrated["display_name"] = CORE_STATE_FILES["world_config.json"].get("display_name", "")
    _write_json(config_path, migrated)
    return {
        "migrated": True,
        "from_version": version,
        "version": SCHEMA_VERSION,
        "backup": backup_dir,
        "recovered": sorted(set(recovered)),
    }


def migrate_all_worlds(worlds_dir: str, logger=None) -> dict:
    """Migrate every world directory at startup; never crash the server.

    Returns per-world status. A corrupt world is reported and left untouched.
    """
    results = {"migrated": [], "skipped": [], "errors": []}
    if not worlds_dir or not os.path.isdir(worlds_dir):
        return results
    for name in sorted(os.listdir(worlds_dir)):
        world_path = os.path.join(worlds_dir, name)
        if not os.path.isdir(world_path):
            continue
        try:
            from app.persistence import recover_world
            recovery = recover_world(world_path)
            if recovery.get('recovered'):
                results.setdefault('recovered', []).append(name)
        except Exception as error:  # recovery must never stop the startup scan
            results["errors"].append({"world": name, "error": f"recovery failed: {error}"})
            if logger:
                logger.error("Commit recovery failed for %s: %s", name, error)
            continue
        try:
            info = ensure_current_schema(world_path)
        except SchemaVersionError as error:
            results["errors"].append({"world": name, "error": str(error)})
            if logger:
                logger.error("Schema migration skipped for %s: %s", name, error)
            continue
        except OSError as error:
            results["errors"].append({"world": name, "error": str(error)})
            if logger:
                logger.error("Schema migration failed for %s: %s", name, error)
            continue
        if info["migrated"]:
            results["migrated"].append(name)
        else:
            results["skipped"].append(name)
    return results
