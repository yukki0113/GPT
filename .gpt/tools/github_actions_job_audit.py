#!/usr/bin/env python3
"""Audit GitHub Actions job execution time and estimate private-repository minutes.

The tool reads workflow-run and job history through the authenticated ``gh`` CLI.
It does not use GitHub's deprecated workflow-usage endpoint. Instead, it derives
job duration from ``started_at`` / ``completed_at`` and estimates private-repo
billable minutes by rounding each GitHub-hosted job up to the next whole minute.

The estimate intentionally does not apply runner minute multipliers or prices.
It is an execution-time audit, not an invoice calculator.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

DEFAULT_REPOSITORY = "yukki0113/GPT"


class ActionsJobAuditError(RuntimeError):
    """Raised when GitHub Actions history cannot be audited safely."""


@dataclass(frozen=True)
class DateRange:
    """Inclusive UTC date range used for workflow-run discovery."""

    start: date
    end: date

    @property
    def github_created_filter(self) -> str:
        """Return the value accepted by the workflow-runs ``created`` filter."""
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


@dataclass(frozen=True)
class JobAuditRow:
    """One normalized GitHub Actions job record."""

    run_id: int
    run_attempt: int
    workflow_name: str
    workflow_path: str
    run_event: str
    run_conclusion: str
    run_created_at: str
    run_url: str
    job_id: int
    job_name: str
    job_conclusion: str
    started_at: str
    completed_at: str
    duration_seconds: int
    actual_minutes: float
    rounded_job_minutes: int
    private_estimated_minutes: int
    runner_type: str
    runner_os: str
    runner_name: str
    labels: str


def run_gh(arguments: list[str]) -> str:
    """Run GitHub CLI and return stdout, raising a readable error on failure."""
    command = ["gh"] + arguments
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        command_text = " ".join(command)
        error_text = result.stderr.strip() or result.stdout.strip()
        raise ActionsJobAuditError(
            f"GitHub CLI failed: {command_text}\n{error_text}"
        )
    return result.stdout


def ensure_gh_available() -> None:
    """Verify that GitHub CLI exists and has an authenticated session."""
    if shutil.which("gh") is None:
        raise ActionsJobAuditError("GitHub CLI 'gh' is not installed or not on PATH.")
    run_gh(["auth", "status"])


def parse_iso_date(value: str) -> date:
    """Parse an ISO YYYY-MM-DD date and raise a readable CLI error."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ActionsJobAuditError(
            f"Invalid date '{value}'. Use YYYY-MM-DD."
        ) from exc


def resolve_date_range(month: str | None, start_text: str | None, end_text: str | None) -> DateRange:
    """Resolve either ``--month`` or explicit inclusive start/end dates."""
    if month is not None and (start_text is not None or end_text is not None):
        raise ActionsJobAuditError(
            "Use --month by itself, or use --from and --to together."
        )

    if month is not None:
        match = re.fullmatch(r"(\d{4})-(\d{2})", month)
        if match is None:
            raise ActionsJobAuditError("--month must use YYYY-MM format.")
        year = int(match.group(1))
        month_number = int(match.group(2))
        if month_number < 1 or month_number > 12:
            raise ActionsJobAuditError("--month contains an invalid month number.")
        start = date(year, month_number, 1)
        if month_number == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month_number + 1, 1)
        end = date.fromordinal(next_month.toordinal() - 1)
        return DateRange(start=start, end=end)

    if start_text is None or end_text is None:
        raise ActionsJobAuditError(
            "Specify either --month YYYY-MM or both --from YYYY-MM-DD and --to YYYY-MM-DD."
        )

    start = parse_iso_date(start_text)
    end = parse_iso_date(end_text)
    if end < start:
        raise ActionsJobAuditError("--to must be the same date as or later than --from.")
    return DateRange(start=start, end=end)


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a GitHub ISO timestamp into an offset-aware datetime."""
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def flatten_paginated_response(response_text: str, collection_key: str) -> list[dict[str, Any]]:
    """Flatten ``gh api --paginate --slurp`` pages for one collection key."""
    payload = json.loads(response_text)
    pages: list[Any]
    if isinstance(payload, list):
        pages = payload
    else:
        pages = [payload]

    records: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        collection = page.get(collection_key, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict):
                records.append(item)
    return records


def fetch_workflow_runs(repository: str, date_range: DateRange) -> list[dict[str, Any]]:
    """Fetch all workflow runs created inside the requested inclusive date range."""
    endpoint = (
        f"repos/{repository}/actions/runs"
        f"?per_page=100&created={date_range.github_created_filter}"
    )
    response_text = run_gh(["api", "--paginate", "--slurp", endpoint])
    return flatten_paginated_response(response_text, "workflow_runs")


def fetch_run_jobs(repository: str, run_id: int) -> list[dict[str, Any]]:
    """Fetch jobs from every attempt of one workflow run."""
    endpoint = (
        f"repos/{repository}/actions/runs/{run_id}/jobs"
        "?filter=all&per_page=100"
    )
    response_text = run_gh(["api", "--paginate", "--slurp", endpoint])
    return flatten_paginated_response(response_text, "jobs")


def normalize_labels(job: dict[str, Any]) -> list[str]:
    """Return non-empty runner labels as strings."""
    raw_labels = job.get("labels") or []
    labels: list[str] = []
    if isinstance(raw_labels, list):
        for label in raw_labels:
            text = str(label).strip()
            if text:
                labels.append(text)
    return labels


def classify_runner(job: dict[str, Any]) -> tuple[str, str]:
    """Classify runner ownership and operating-system family from job metadata."""
    labels = normalize_labels(job)
    lower_labels = [label.lower() for label in labels]
    runner_name = str(job.get("runner_name") or "")
    runner_group_name = str(job.get("runner_group_name") or "")

    if "self-hosted" in lower_labels:
        runner_type = "self-hosted"
    elif runner_group_name == "GitHub Actions" or runner_name.startswith("GitHub Actions"):
        runner_type = "github-hosted"
    elif any(
        label.startswith(("ubuntu", "windows", "macos"))
        for label in lower_labels
    ):
        runner_type = "github-hosted"
    else:
        runner_type = "unknown"

    runner_os = "unknown"
    if any(label.startswith("ubuntu") for label in lower_labels):
        runner_os = "linux"
    elif any(label.startswith("windows") for label in lower_labels):
        runner_os = "windows"
    elif any(label.startswith("macos") for label in lower_labels):
        runner_os = "macos"

    return runner_type, runner_os


def calculate_duration_seconds(job: dict[str, Any]) -> int:
    """Calculate non-negative runner wall-clock seconds from GitHub job timestamps."""
    started_at = parse_timestamp(str(job.get("started_at") or ""))
    completed_at = parse_timestamp(str(job.get("completed_at") or ""))
    if started_at is None or completed_at is None:
        return 0
    duration = int((completed_at - started_at).total_seconds())
    return max(0, duration)


def calculate_rounded_job_minutes(job: dict[str, Any], duration_seconds: int) -> int:
    """Round a started job up to the next minute, matching private-job display rules."""
    if str(job.get("conclusion") or "") == "skipped":
        return 0
    if not job.get("started_at") or not job.get("completed_at"):
        return 0
    return max(1, math.ceil(duration_seconds / 60.0))


def build_job_row(run: dict[str, Any], job: dict[str, Any]) -> JobAuditRow:
    """Normalize one run/job pair into the audit output schema."""
    duration_seconds = calculate_duration_seconds(job)
    rounded_job_minutes = calculate_rounded_job_minutes(job, duration_seconds)
    runner_type, runner_os = classify_runner(job)

    private_estimated_minutes = 0
    if runner_type == "github-hosted":
        private_estimated_minutes = rounded_job_minutes

    labels = normalize_labels(job)
    run_attempt = int(job.get("run_attempt") or run.get("run_attempt") or 1)

    return JobAuditRow(
        run_id=int(run.get("id") or 0),
        run_attempt=run_attempt,
        workflow_name=str(run.get("name") or job.get("workflow_name") or ""),
        workflow_path=str(run.get("path") or ""),
        run_event=str(run.get("event") or ""),
        run_conclusion=str(run.get("conclusion") or ""),
        run_created_at=str(run.get("created_at") or ""),
        run_url=str(run.get("html_url") or ""),
        job_id=int(job.get("id") or 0),
        job_name=str(job.get("name") or ""),
        job_conclusion=str(job.get("conclusion") or ""),
        started_at=str(job.get("started_at") or ""),
        completed_at=str(job.get("completed_at") or ""),
        duration_seconds=duration_seconds,
        actual_minutes=round(duration_seconds / 60.0, 4),
        rounded_job_minutes=rounded_job_minutes,
        private_estimated_minutes=private_estimated_minutes,
        runner_type=runner_type,
        runner_os=runner_os,
        runner_name=str(job.get("runner_name") or ""),
        labels=",".join(labels),
    )


def compile_patterns(pattern_texts: Iterable[str]) -> list[re.Pattern[str]]:
    """Compile user-supplied workflow-name/path regular expressions."""
    patterns: list[re.Pattern[str]] = []
    for pattern_text in pattern_texts:
        try:
            patterns.append(re.compile(pattern_text))
        except re.error as exc:
            raise ActionsJobAuditError(
                f"Invalid workflow regex '{pattern_text}': {exc}"
            ) from exc
    return patterns


def run_matches_patterns(run: dict[str, Any], patterns: list[re.Pattern[str]]) -> bool:
    """Return whether any pattern matches a workflow's name or path."""
    if not patterns:
        return False
    target = f"{run.get('name') or ''}\n{run.get('path') or ''}"
    return any(pattern.search(target) is not None for pattern in patterns)


def should_include_run(
    run: dict[str, Any],
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
) -> bool:
    """Apply optional include and exclude workflow regular expressions."""
    if include_patterns and not run_matches_patterns(run, include_patterns):
        return False
    if exclude_patterns and run_matches_patterns(run, exclude_patterns):
        return False
    return True


def collect_audit_rows(
    repository: str,
    date_range: DateRange,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
) -> tuple[list[dict[str, Any]], list[JobAuditRow]]:
    """Fetch workflow runs and all executed jobs needed for the audit."""
    workflow_runs = fetch_workflow_runs(repository, date_range)
    selected_runs: list[dict[str, Any]] = []
    rows: list[JobAuditRow] = []

    for run in workflow_runs:
        if not should_include_run(run, include_patterns, exclude_patterns):
            continue
        selected_runs.append(run)

        # A run concluded as skipped never acquired a runner, so avoid one API call.
        if str(run.get("conclusion") or "") == "skipped":
            continue

        run_id = int(run.get("id") or 0)
        if run_id <= 0:
            continue
        jobs = fetch_run_jobs(repository, run_id)
        for job in jobs:
            rows.append(build_job_row(run, job))

    return selected_runs, rows


def summarize_runs(runs: list[dict[str, Any]]) -> Counter[str]:
    """Count workflow runs by conclusion, including still-running states."""
    conclusions: Counter[str] = Counter()
    for run in runs:
        conclusion = str(run.get("conclusion") or run.get("status") or "unknown")
        conclusions[conclusion] += 1
    return conclusions


def summarize_jobs(rows: list[JobAuditRow]) -> Counter[str]:
    """Count normalized jobs by conclusion."""
    conclusions: Counter[str] = Counter()
    for row in rows:
        conclusions[row.job_conclusion or "unknown"] += 1
    return conclusions


def format_counter(counter: Counter[str]) -> str:
    """Format a counter deterministically for console output."""
    if not counter:
        return "none"
    parts = [f"{key}={counter[key]}" for key in sorted(counter)]
    return ", ".join(parts)


def build_workflow_summary(rows: list[JobAuditRow]) -> list[tuple[str, int, float, int]]:
    """Aggregate job count, actual time, and private estimate by workflow."""
    aggregates: dict[str, dict[str, float]] = defaultdict(
        lambda: {"jobs": 0.0, "actual": 0.0, "private": 0.0}
    )
    for row in rows:
        key = row.workflow_name or row.workflow_path or "(unknown workflow)"
        aggregate = aggregates[key]
        aggregate["jobs"] += 1
        aggregate["actual"] += row.actual_minutes
        aggregate["private"] += row.private_estimated_minutes

    result: list[tuple[str, int, float, int]] = []
    for workflow_name, aggregate in aggregates.items():
        result.append(
            (
                workflow_name,
                int(aggregate["jobs"]),
                aggregate["actual"],
                int(aggregate["private"]),
            )
        )
    result.sort(key=lambda item: (-item[3], -item[2], item[0].lower()))
    return result


def print_summary(
    repository: str,
    date_range: DateRange,
    runs: list[dict[str, Any]],
    rows: list[JobAuditRow],
) -> None:
    """Print a compact audit summary and per-workflow breakdown."""
    run_conclusions = summarize_runs(runs)
    job_conclusions = summarize_jobs(rows)
    actual_minutes = sum(row.actual_minutes for row in rows)
    rounded_job_minutes = sum(row.rounded_job_minutes for row in rows)
    private_minutes = sum(row.private_estimated_minutes for row in rows)
    github_hosted_jobs = sum(1 for row in rows if row.runner_type == "github-hosted")
    self_hosted_jobs = sum(1 for row in rows if row.runner_type == "self-hosted")
    unknown_runner_jobs = sum(1 for row in rows if row.runner_type == "unknown")

    print(f"Repository: {repository}")
    print(f"Range (workflow run created_at, UTC): {date_range.start} .. {date_range.end}")
    print(f"Workflow runs: {len(runs)} ({format_counter(run_conclusions)})")
    print(f"Jobs fetched: {len(rows)} ({format_counter(job_conclusions)})")
    print(
        "Runner types: "
        f"github-hosted={github_hosted_jobs}, "
        f"self-hosted={self_hosted_jobs}, unknown={unknown_runner_jobs}"
    )
    print(f"Actual runner time: {actual_minutes:.2f} minutes")
    print(f"All started jobs rounded per job: {rounded_job_minutes} minutes")
    print(
        "Estimated private GitHub-hosted minutes: "
        f"{private_minutes} minutes"
    )
    print(
        "Note: estimate rounds each GitHub-hosted job up to a whole minute; "
        "runner multipliers/prices are not applied."
    )

    non_linux_hosted = sorted(
        {
            row.runner_os
            for row in rows
            if row.runner_type == "github-hosted" and row.runner_os not in {"linux", "unknown"}
        }
    )
    if non_linux_hosted:
        print(
            "Warning: non-Linux GitHub-hosted runners detected: "
            + ", ".join(non_linux_hosted)
            + ". Check current GitHub billing multipliers separately."
        )
    if unknown_runner_jobs:
        print(
            "Warning: some jobs have unknown runner type and are excluded from the private estimate."
        )

    workflow_summary = build_workflow_summary(rows)
    if not workflow_summary:
        return

    print("\nBy workflow:")
    print("private_min  actual_min  jobs  workflow")
    for workflow_name, job_count, workflow_actual, workflow_private in workflow_summary:
        print(
            f"{workflow_private:11d}  "
            f"{workflow_actual:10.2f}  "
            f"{job_count:4d}  "
            f"{workflow_name}"
        )


def write_csv(path: Path, rows: list[JobAuditRow]) -> None:
    """Write one row per job for later spreadsheet analysis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(JobAuditRow.__annotations__.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(
    path: Path,
    repository: str,
    date_range: DateRange,
    runs: list[dict[str, Any]],
    rows: list[JobAuditRow],
) -> None:
    """Write structured summary plus normalized job rows as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repository": repository,
        "range": {
            "basis": "workflow run created_at (UTC)",
            "from": date_range.start.isoformat(),
            "to": date_range.end.isoformat(),
        },
        "summary": {
            "workflow_runs": len(runs),
            "run_conclusions": dict(summarize_runs(runs)),
            "jobs": len(rows),
            "job_conclusions": dict(summarize_jobs(rows)),
            "actual_runner_minutes": round(sum(row.actual_minutes for row in rows), 4),
            "rounded_job_minutes": sum(row.rounded_job_minutes for row in rows),
            "estimated_private_github_hosted_minutes": sum(
                row.private_estimated_minutes for row in rows
            ),
        },
        "jobs": [asdict(row) for row in rows],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Audit GitHub Actions job time and estimate private-repository "
            "GitHub-hosted minutes from job timestamps."
        )
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository in owner/name form (default: {DEFAULT_REPOSITORY}).",
    )
    range_group = parser.add_mutually_exclusive_group(required=False)
    range_group.add_argument("--month", help="Calendar month in YYYY-MM format.")
    range_group.add_argument("--from", dest="start_text", help="Inclusive start date YYYY-MM-DD.")
    parser.add_argument("--to", dest="end_text", help="Inclusive end date YYYY-MM-DD.")
    parser.add_argument(
        "--include-workflow-regex",
        action="append",
        default=[],
        help="Only include workflow names/paths matching this regex. Repeatable.",
    )
    parser.add_argument(
        "--exclude-workflow-regex",
        action="append",
        default=[],
        help="Exclude workflow names/paths matching this regex. Repeatable.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        help="Optional detailed CSV output path.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        help="Optional structured JSON output path.",
    )
    return parser


def main() -> int:
    """Run the Actions job-time audit CLI."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        date_range = resolve_date_range(args.month, args.start_text, args.end_text)
        include_patterns = compile_patterns(args.include_workflow_regex)
        exclude_patterns = compile_patterns(args.exclude_workflow_regex)
        ensure_gh_available()
        runs, rows = collect_audit_rows(
            repository=args.repo,
            date_range=date_range,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
        print_summary(args.repo, date_range, runs, rows)
        if args.csv_path is not None:
            write_csv(args.csv_path, rows)
            print(f"\nCSV: {args.csv_path}")
        if args.json_path is not None:
            write_json(args.json_path, args.repo, date_range, runs, rows)
            print(f"JSON: {args.json_path}")
        return 0
    except (ActionsJobAuditError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
