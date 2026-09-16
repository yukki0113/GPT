from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ConfigError


def load_config(path: str | Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ConfigError("PyYAML is required for run-config") from exc
    config_path = Path(path).resolve()
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read config: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config root must be a mapping")
    for key in ("source", "target"):
        if not isinstance(data.get(key), dict):
            raise ConfigError(f"missing mapping: {key}")
    base = config_path.parent
    for section, key in (("source", "path"), ("target", "path")):
        value = data[section].get(key)
        if value and not Path(value).is_absolute():
            data[section][key] = str((base / value).resolve())
    if data["source"].get("paths"):
        data["source"]["paths"] = [
            value if Path(value).is_absolute() else str((base / value).resolve())
            for value in data["source"]["paths"]
        ]
    audit_path = (data.get("audit") or {}).get("path")
    if audit_path and not Path(audit_path).is_absolute():
        data["audit"]["path"] = str((base / audit_path).resolve())
    for source in (data.get("benchmark") or {}).get("sources") or []:
        value = source.get("path")
        if value and not Path(value).is_absolute():
            source["path"] = str((base / value).resolve())
    data["_config_path"] = str(config_path)
    return data
