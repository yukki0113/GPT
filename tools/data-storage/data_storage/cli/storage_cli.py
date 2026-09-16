from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..common import write_json
from ..config import load_config
from ..dependencies import dependency_report
from ..errors import ConfigError, StorageError


def _emit(value: dict, output: str | None = None) -> None:
    if output:
        write_json(output, value)
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gpt-data-storage")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("check-deps")
    convert = commands.add_parser("convert")
    convert.add_argument("--input", required=True)
    convert.add_argument("--input-format", choices=("sqlite", "csv"), required=True)
    convert.add_argument("--table")
    convert.add_argument("--output", required=True)
    convert.add_argument("--compression", choices=("zstd", "snappy"), default="zstd")
    convert.add_argument("--columns", nargs="*")
    convert.add_argument("--partition-by", nargs="*", default=[])
    convert.add_argument("--sort-by", nargs="*", default=[])
    convert.add_argument("--encoding", default="utf-8")
    convert.add_argument("--delimiter", default=",")
    convert.add_argument("--audit")
    run = commands.add_parser("run-config")
    run.add_argument("config")
    check = commands.add_parser("validate")
    check.add_argument("config")
    bench = commands.add_parser("benchmark")
    bench.add_argument("config")
    bench.add_argument("--output")
    query = commands.add_parser("query")
    query.add_argument("path")
    query.add_argument("sql")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "check-deps":
            result = dependency_report()
            _emit(result)
            return 0 if result.get("status") == "success" else 2
        dependencies = dependency_report()
        if dependencies["status"] != "success":
            _emit(dependencies)
            return 2
        if args.command == "convert":
            from ..runner import run_config
            if args.input_format == "sqlite" and not args.table:
                raise ConfigError("--table is required for SQLite")
            source = {"format": args.input_format, "path": args.input}
            if args.table:
                source["table"] = args.table
            if args.columns:
                source["columns"] = args.columns
            if args.input_format == "csv":
                source.update({"encoding": args.encoding, "delimiter": args.delimiter})
            config = {
                "source": source,
                "target": {"format": "parquet", "path": args.output, "compression": args.compression, "partition_by": args.partition_by},
                "sort_by": args.sort_by,
                "validation": {"require_row_count_match": True},
            }
            if args.audit:
                config["audit"] = {"path": args.audit}
            result = run_config(config)
        elif args.command == "run-config":
            from ..runner import run_config
            result = run_config(load_config(args.config))
        elif args.command == "validate":
            from ..validate import validate
            result = validate(load_config(args.config))
        elif args.command == "benchmark":
            from ..benchmark import benchmark
            result = benchmark(load_config(args.config))
            _emit(result, args.output)
            return 0
        else:
            from ..query import execute_query
            columns, rows = execute_query(args.path, args.sql)
            result = {"status": "success", "columns": columns, "rows": rows}
        _emit(result)
        return 0 if result.get("status") == "success" else 2
    except StorageError as exc:
        _emit({"status": exc.status, "error": str(exc)})
        return 2
    except (KeyError, ValueError, OSError) as exc:
        _emit({"status": "INVALID_CONFIG", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
