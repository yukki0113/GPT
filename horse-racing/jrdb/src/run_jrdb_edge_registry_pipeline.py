#!/usr/bin/env python3
"""Orchestrate the JRDB Edge Registry build without reimplementing domain logic.

The driver deliberately delegates every domain/statistical operation to the existing
JRDB CLI modules. Its responsibilities are request validation, deterministic stage
sequencing, fail-fast control flow, failure taxonomy, and machine-readable RESULT
emission. The final stage builds the fail-closed publication manifest.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

RESULT_SCHEMA_VERSION = "0.1"
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
VERSION_RE = re.compile(r"[A-Za-z0-9._-]{1,100}\Z")
SHA_RE = re.compile(r"[0-9a-fA-F]{40}\Z")

FAILURE_CLASS_REQUEST = "REQUEST_INVALID"
FAILURE_CLASS_EXTERNAL = "EXTERNAL_TRANSIENT"
FAILURE_CLASS_DOMAIN = "DOMAIN_VALIDATION_FAILED"
FAILURE_CLASS_IMPLEMENTATION = "IMPLEMENTATION_ERROR"


class RequestValidationError(ValueError):
    """Raised before any stage starts when a request violates the driver contract."""


@dataclass(frozen=True)
class PipelineRequest:
    request_id: str
    from_year: int
    to_year: int
    registry_version: str
    issue_number: int
    run_id: int
    head_sha: str
    template_version: str
    hash_archives: bool = False
    skip_fetch: bool = False


@dataclass(frozen=True)
class PipelinePaths:
    repo_root: Path
    work_dir: Path
    raw_root: Path
    out_dir: Path
    report_dir: Path
    index_db: Path
    mart_db: Path


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    failure_class: str
    retryable: bool = False


Executor = Callable[[Stage, Path], int]


def validate_request(request: PipelineRequest) -> None:
    if not REQUEST_ID_RE.fullmatch(request.request_id):
        raise RequestValidationError("invalid request_id")
    if request.from_year < 2010 or request.to_year > 2025 or request.to_year < request.from_year:
        raise RequestValidationError("year range must be within 2010..2025")
    if not VERSION_RE.fullmatch(request.registry_version):
        raise RequestValidationError("invalid registry_version")
    if request.issue_number <= 0 or request.run_id <= 0:
        raise RequestValidationError("issue_number and run_id must be positive")
    if not SHA_RE.fullmatch(request.head_sha):
        raise RequestValidationError("head_sha must be a 40-character hexadecimal Git SHA")
    if not VERSION_RE.fullmatch(request.template_version):
        raise RequestValidationError("invalid template_version")


def load_template_version(repo_root: Path) -> str:
    path = repo_root / "horse-racing/jrdb/config/jrdb_edge_candidate_templates_v0_1.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequestValidationError(f"cannot load Edge template config: {exc}") from exc
    version = str(payload.get("template_version") or "")
    if not VERSION_RE.fullmatch(version):
        raise RequestValidationError("Edge template config has invalid template_version")
    return version


def make_paths(repo_root: Path, work_dir: Path) -> PipelinePaths:
    root = work_dir.resolve()
    return PipelinePaths(
        repo_root=repo_root.resolve(),
        work_dir=root,
        raw_root=root / "raw",
        out_dir=root / "out",
        report_dir=root / "report",
        index_db=root / "index.sqlite",
        mart_db=root / "edge_mart.sqlite",
    )


def prepare_directories(paths: PipelinePaths) -> None:
    paths.raw_root.mkdir(parents=True, exist_ok=True)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    paths.report_dir.mkdir(parents=True, exist_ok=True)


def _script(paths: PipelinePaths, name: str) -> str:
    return str(paths.repo_root / "horse-racing/jrdb/src" / name)


def build_stages(request: PipelineRequest, paths: PipelinePaths, python: str) -> list[Stage]:
    years = [str(year) for year in range(request.from_year, request.to_year + 1)]
    stages: list[Stage] = []
    if not request.skip_fetch:
        stages.append(
            Stage(
                "fetch_raw",
                (
                    python,
                    _script(paths, "fetch_jrdb_history.py"),
                    "--from-year",
                    str(request.from_year),
                    "--to-year",
                    str(request.to_year),
                    "--kinds",
                    "BAC",
                    "KYI",
                    "SED",
                    "UKC",
                    "--output-dir",
                    str(paths.raw_root),
                    "--manifest",
                    str(paths.report_dir / "fetch_manifest.jsonl"),
                    "--sleep-seconds",
                    "1",
                    "--continue-on-error",
                ),
                FAILURE_CLASS_EXTERNAL,
                retryable=True,
            )
        )

    index_command = [
        python,
        _script(paths, "build_jrdb_index_base_from_raw.py"),
        "--raw-root",
        str(paths.raw_root),
        "--years",
        *years,
        "--db",
        str(paths.index_db),
    ]
    if not request.hash_archives:
        index_command.append("--no-archive-hash")
    stages.extend(
        [
            Stage("index_build", tuple(index_command), FAILURE_CLASS_IMPLEMENTATION),
            Stage(
                "index_audit",
                (
                    python,
                    _script(paths, "audit_jrdb_index_base.py"),
                    "--db",
                    str(paths.index_db),
                    "--out",
                    str(paths.report_dir / "index_audit.json"),
                ),
                FAILURE_CLASS_DOMAIN,
            ),
            Stage(
                "feature_mart",
                (
                    python,
                    _script(paths, "build_jrdb_edge_feature_mart.py"),
                    "--source",
                    str(paths.index_db),
                    "--output",
                    str(paths.mart_db),
                ),
                FAILURE_CLASS_IMPLEMENTATION,
            ),
            Stage(
                "discovery",
                (
                    python,
                    _script(paths, "jrdb_edge_discovery.py"),
                    "--mart",
                    str(paths.mart_db),
                    "--output",
                    str(paths.out_dir / "edge_candidates.jsonl"),
                ),
                FAILURE_CLASS_IMPLEMENTATION,
            ),
            Stage(
                "registry",
                (
                    python,
                    _script(paths, "build_jrdb_edge_registry.py"),
                    "--mart",
                    str(paths.mart_db),
                    "--candidates",
                    str(paths.out_dir / "edge_candidates.jsonl"),
                    "--registry",
                    str(paths.out_dir / "edge_registry.sqlite"),
                    "--registry-version",
                    request.registry_version,
                    "--export-jsonl",
                    str(paths.out_dir / "edge_registry_active.jsonl"),
                    "--export-csv",
                    str(paths.out_dir / "edge_registry_active.csv"),
                    "--audit-json",
                    str(paths.out_dir / "edge_registry_audit.json"),
                ),
                FAILURE_CLASS_IMPLEMENTATION,
            ),
            Stage(
                "statistical_guard",
                (
                    python,
                    _script(paths, "apply_jrdb_edge_statistical_guard.py"),
                    "--mart",
                    str(paths.mart_db),
                    "--registry",
                    str(paths.out_dir / "edge_registry.sqlite"),
                    "--registry-audit",
                    str(paths.out_dir / "edge_registry_audit.json"),
                    "--output-jsonl",
                    str(paths.out_dir / "edge_statistical_guard.jsonl"),
                    "--audit-json",
                    str(paths.out_dir / "edge_statistical_guard_audit.json"),
                    "--export-jsonl",
                    str(paths.out_dir / "edge_registry_active.jsonl"),
                    "--export-csv",
                    str(paths.out_dir / "edge_registry_active.csv"),
                ),
                FAILURE_CLASS_DOMAIN,
            ),
            Stage(
                "summary",
                (
                    python,
                    _script(paths, "report_jrdb_edge_registry.py"),
                    "--registry",
                    str(paths.out_dir / "edge_registry.sqlite"),
                    "--output-json",
                    str(paths.out_dir / "edge_registry_summary.json"),
                    "--output-md",
                    str(paths.out_dir / "edge_registry_summary.md"),
                    "--top-n",
                    "30",
                ),
                FAILURE_CLASS_IMPLEMENTATION,
            ),
            Stage(
                "publication_manifest",
                (
                    python,
                    _script(paths, "build_jrdb_edge_publication_manifest.py"),
                    "--publication-dir",
                    str(paths.out_dir),
                    "--output",
                    str(paths.out_dir / "manifest.json"),
                    "--issue-number",
                    str(request.issue_number),
                    "--run-id",
                    str(request.run_id),
                    "--head-sha",
                    request.head_sha,
                    "--request-id",
                    request.request_id,
                    "--from-year",
                    str(request.from_year),
                    "--to-year",
                    str(request.to_year),
                    "--template-version",
                    request.template_version,
                ),
                FAILURE_CLASS_DOMAIN,
            ),
        ]
    )
    return stages


def execute_stage(stage: Stage, report_dir: Path) -> int:
    stdout_path = report_dir / f"{stage.name}_stdout.log"
    stderr_path = report_dir / f"{stage.name}_stderr.log"
    env = os.environ.copy()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(stage.command, stdout=stdout, stderr=stderr, env=env, check=False)
    return int(completed.returncode)


def _result_payload(
    request: PipelineRequest,
    paths: PipelinePaths,
    *,
    status: str,
    exit_codes: dict[str, int],
    failed_stage: Stage | None = None,
    error_code: str | None = None,
    message: str | None = None,
) -> dict:
    artifact_name = f"jrdb-edge-registry-v2-{request.request_id}-{request.run_id}"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": status,
        "request": asdict(request),
        "artifact_name": artifact_name,
        "exit_codes": exit_codes,
        "failed_step": failed_stage.name if failed_stage else None,
        "failure_class": failed_stage.failure_class if failed_stage else None,
        "error_code": error_code,
        "retryable": failed_stage.retryable if failed_stage else False,
        "message": message,
        "publication_manifest": str(paths.out_dir / "manifest.json"),
    }


def write_result(paths: PipelinePaths, payload: dict) -> Path:
    paths.report_dir.mkdir(parents=True, exist_ok=True)
    output = paths.report_dir / "workflow_result.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def run_pipeline(
    request: PipelineRequest,
    paths: PipelinePaths,
    *,
    python: str = sys.executable,
    executor: Executor = execute_stage,
) -> dict:
    validate_request(request)
    prepare_directories(paths)
    exit_codes: dict[str, int] = {}
    for stage in build_stages(request, paths, python):
        code = executor(stage, paths.report_dir)
        exit_codes[stage.name] = code
        if code != 0:
            payload = _result_payload(
                request,
                paths,
                status="failure",
                exit_codes=exit_codes,
                failed_stage=stage,
                error_code=f"{stage.name.upper()}_FAILED",
                message=f"stage {stage.name} exited with code {code}",
            )
            write_result(paths, payload)
            return payload

    manifest_path = paths.out_dir / "manifest.json"
    if not manifest_path.is_file():
        synthetic = Stage("publication_manifest", tuple(), FAILURE_CLASS_IMPLEMENTATION)
        payload = _result_payload(
            request,
            paths,
            status="failure",
            exit_codes=exit_codes,
            failed_stage=synthetic,
            error_code="MANIFEST_OUTPUT_MISSING",
            message="publication manifest command succeeded but manifest.json is missing",
        )
        write_result(paths, payload)
        return payload

    payload = _result_payload(request, paths, status="success", exit_codes=exit_codes)
    write_result(paths, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--registry-version", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--template-version")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--hash-archives", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--python", default=sys.executable)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    paths = make_paths(repo_root, Path(args.work_dir))
    try:
        template_version = args.template_version or load_template_version(repo_root)
        request = PipelineRequest(
            request_id=args.request_id,
            from_year=args.from_year,
            to_year=args.to_year,
            registry_version=args.registry_version,
            issue_number=args.issue_number,
            run_id=args.run_id,
            head_sha=args.head_sha,
            template_version=template_version,
            hash_archives=bool(args.hash_archives),
            skip_fetch=bool(args.skip_fetch),
        )
        validate_request(request)
    except RequestValidationError as exc:
        prepare_directories(paths)
        request = PipelineRequest(
            request_id=str(args.request_id),
            from_year=int(args.from_year),
            to_year=int(args.to_year),
            registry_version=str(args.registry_version),
            issue_number=int(args.issue_number),
            run_id=int(args.run_id),
            head_sha=str(args.head_sha),
            template_version=str(args.template_version or "INVALID"),
            hash_archives=bool(args.hash_archives),
            skip_fetch=bool(args.skip_fetch),
        )
        synthetic = Stage("request_validation", tuple(), FAILURE_CLASS_REQUEST)
        payload = _result_payload(
            request,
            paths,
            status="failure",
            exit_codes={},
            failed_stage=synthetic,
            error_code="REQUEST_VALIDATION_FAILED",
            message=str(exc),
        )
        write_result(paths, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    payload = run_pipeline(request, paths, python=args.python)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
