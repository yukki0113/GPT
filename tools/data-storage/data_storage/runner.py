from __future__ import annotations

import datetime as dt
import platform
import time

from . import __version__
from .common import write_json
from .dependencies import dependency_report


def run_config(config: dict) -> dict:
    started = time.perf_counter()
    dependencies = dependency_report()
    if dependencies["status"] != "success":
        return dependencies
    from .convert import convert
    from .validate import validate

    converted = convert(config)
    validation = validate(config, converted)
    result = {
        "status": "success" if validation["passed"] else "VALIDATION_FAILED",
        "tool_version": __version__,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "config_path": config.get("_config_path"),
        **converted,
        "validation": validation,
        "elapsed_seconds_total": round(time.perf_counter() - started, 6),
    }
    if (config.get("benchmark") or {}).get("run_after_convert"):
        from .benchmark import benchmark
        result["benchmark"] = benchmark(config)
    audit_path = (config.get("audit") or {}).get("path")
    if audit_path:
        write_json(audit_path, result)
    return result
