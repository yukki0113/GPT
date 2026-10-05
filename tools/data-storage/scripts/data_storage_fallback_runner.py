#!/usr/bin/env python3
"""Repository-wide local-blocked -> GitHub Actions fallback runner for Parquet/DuckDB tasks.

The runner intentionally accepts repository Python entrypoints plus argv arrays.
It never evaluates arbitrary shell command strings.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path("/tmp/data-storage-fallback")
INPUTS = BASE / "inputs"
WORK = BASE / "work"
OUTPUT = BASE / "output"
STDOUT = BASE / "stdout"
STDERR = BASE / "stderr"
AUDIT = BASE / "fallback-audit.json"

LABEL_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
STEP_RE = re.compile(r"[A-Za-z0-9_.-]{1,80}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, check=False, text=True)


def validate_request(raw: str) -> dict[str, Any]:
    try:
        request = json.loads(raw)
    except Exception as exc:
        raise ValueError(f"issue body must be a single JSON object: {exc}") from exc
    if not isinstance(request, dict):
        raise ValueError("issue body must be a JSON object")

    source_ref = request.get("source_ref", "main")
    if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 200:
        raise ValueError("source_ref must be a non-empty string <=200 chars")

    request_id = request.get("request_id", "")
    if request_id is not None and (not isinstance(request_id, str) or len(request_id) > 200):
        raise ValueError("request_id must be a string <=200 chars")

    artifacts = request.get("input_artifacts", [])
    if not isinstance(artifacts, list) or len(artifacts) > 8:
        raise ValueError("input_artifacts must be an array with at most 8 items")
    labels: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("each input_artifacts item must be an object")
        label = item.get("label")
        run_id = item.get("run_id")
        artifact_name = item.get("artifact_name")
        if not isinstance(label, str) or not LABEL_RE.fullmatch(label):
            raise ValueError(f"invalid input label: {label!r}")
        if label in labels:
            raise ValueError(f"duplicate input label: {label}")
        labels.add(label)
        if not isinstance(run_id, int) or run_id <= 0:
            raise ValueError(f"invalid run_id for input {label}")
        if not isinstance(artifact_name, str) or not artifact_name.strip() or len(artifact_name) > 255:
            raise ValueError(f"invalid artifact_name for input {label}")

    steps = request.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        raise ValueError("steps must contain 1..20 items")
    step_names: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {index} must be an object")
        name = step.get("name")
        entrypoint = step.get("entrypoint")
        args = step.get("args", [])
        if not isinstance(name, str) or not STEP_RE.fullmatch(name):
            raise ValueError(f"invalid step name at index {index}")
        if name in step_names:
            raise ValueError(f"duplicate step name: {name}")
        step_names.add(name)
        if not isinstance(entrypoint, str) or not entrypoint.endswith(".py"):
            raise ValueError(f"step {name}: entrypoint must be a repository-relative .py file")
        p = Path(entrypoint)
        if p.is_absolute() or ".." in p.parts or any(part.startswith(".") for part in p.parts):
            raise ValueError(f"step {name}: unsafe entrypoint path")
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError(f"step {name}: args must be an array of strings")
        for arg in args:
            for found in re.findall(r"\{input:([^}]+)\}", arg):
                if found not in labels:
                    raise ValueError(f"step {name}: unknown input label {found!r}")
    return request


def write_audit(payload: dict[str, Any]) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def checkout_source(root: Path, source_ref: str) -> str:
    fetch = run(["git", "fetch", "--depth=1", "origin", source_ref], cwd=root)
    if fetch.returncode != 0:
        raise RuntimeError(f"git fetch failed for source_ref={source_ref!r}")
    checkout = run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=root)
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout failed for source_ref={source_ref!r}")
    result = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True)
    return result.strip()


def bootstrap_dependencies(root: Path) -> tuple[str | None, str | None]:
    requirements = root / "tools/data-storage/requirements.txt"
    if not requirements.is_file():
        raise RuntimeError("tools/data-storage/requirements.txt missing at requested source ref")
    install = run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        cwd=root,
    )
    if install.returncode != 0:
        raise RuntimeError("canonical data-storage dependency install failed")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "tools/data-storage")
    check = run([sys.executable, "-m", "data_storage", "check-deps"], cwd=root, env=env)
    if check.returncode != 0:
        raise RuntimeError("canonical data_storage check-deps failed after install")
    return version("duckdb"), version("pyarrow")


def download_inputs(request: dict[str, Any], repository: str) -> None:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN is required to download declared artifacts")
    for item in request.get("input_artifacts", []):
        destination = INPUTS / item["label"]
        destination.mkdir(parents=True, exist_ok=True)
        proc = run(
            [
                "gh",
                "run",
                "download",
                str(item["run_id"]),
                "--repo",
                repository,
                "--name",
                item["artifact_name"],
                "--dir",
                str(destination),
            ],
            cwd=Path.cwd(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"artifact download failed: label={item['label']} run_id={item['run_id']} "
                f"name={item['artifact_name']}"
            )


def expand_arg(value: str, root: Path, labels: dict[str, Path]) -> str:
    value = value.replace("{repo}", str(root))
    value = value.replace("{work}", str(WORK))
    value = value.replace("{output}", str(OUTPUT))
    for label, path in labels.items():
        value = value.replace("{input:" + label + "}", str(path))
    return value


def execute_steps(request: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    labels = {item["label"]: INPUTS / item["label"] for item in request.get("input_artifacts", [])}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "tools/data-storage")
    audits: list[dict[str, Any]] = []

    for index, step in enumerate(request["steps"], 1):
        entrypoint = (root / step["entrypoint"]).resolve()
        if root not in entrypoint.parents or not entrypoint.is_file() or entrypoint.suffix != ".py":
            raise RuntimeError(f"invalid or missing entrypoint after checkout: {step['entrypoint']}")
        args = [expand_arg(arg, root, labels) for arg in step.get("args", [])]
        stdout_path = STDOUT / f"{index:02d}-{step['name']}.log"
        stderr_path = STDERR / f"{index:02d}-{step['name']}.log"
        started = time.monotonic()
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            proc = subprocess.run(
                [sys.executable, str(entrypoint), *args],
                cwd=root,
                env=env,
                stdout=out,
                stderr=err,
                check=False,
            )
        elapsed = time.monotonic() - started
        row = {
            "name": step["name"],
            "entrypoint": step["entrypoint"],
            "entrypoint_sha256": sha256_file(entrypoint),
            "args": args,
            "exit_code": proc.returncode,
            "elapsed_seconds": round(elapsed, 6),
        }
        audits.append(row)
        if proc.returncode != 0:
            raise RuntimeError(f"repository fallback step failed: {step['name']}")
    return audits


def main() -> int:
    for directory in (BASE, INPUTS, WORK, OUTPUT, STDOUT, STDERR):
        directory.mkdir(parents=True, exist_ok=True)

    raw = os.environ.get("FALLBACK_REQUEST_JSON", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    root = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())).resolve()

    audit: dict[str, Any] = {
        "status": "FAIL",
        "production_publication": False,
    }

    try:
        request = validate_request(raw)
        normalized = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        request_sha = sha256_bytes(normalized.encode())
        (BASE / "request.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (BASE / "request.sha256").write_text(request_sha + "\n", encoding="utf-8")

        source_ref = request.get("source_ref", "main")
        source_commit = checkout_source(root, source_ref)
        duckdb_version, pyarrow_version = bootstrap_dependencies(root)
        download_inputs(request, repository)
        steps = execute_steps(request, root)

        audit.update(
            {
                "status": "PASS",
                "request_id": request.get("request_id"),
                "request_sha256": request_sha,
                "source_ref": source_ref,
                "source_commit": source_commit,
                "python_version": sys.version.split()[0],
                "duckdb_version": duckdb_version,
                "pyarrow_version": pyarrow_version,
                "input_artifacts": request.get("input_artifacts", []),
                "steps": steps,
            }
        )
        write_audit(audit)
        return 0
    except Exception as exc:
        audit["error"] = f"{type(exc).__name__}: {exc}"
        audit["python_version"] = sys.version.split()[0]
        audit["duckdb_version"] = version("duckdb")
        audit["pyarrow_version"] = version("pyarrow")
        write_audit(audit)
        print(audit["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
