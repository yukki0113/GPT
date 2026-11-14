#!/usr/bin/env python3
"""Read-only JRDB niche QuerySpec runner. Uses canonical data_storage.query for SQL."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from compile_query import build_sql, validate_spec
from resolve_analysis_generation import prepare_current_only


def _write_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str)+"\n",encoding="utf-8")


def _records(columns, rows):
    return [dict(zip(columns,r)) for r in rows]


def _write_csv(path: Path, columns: list[str], rows: list[tuple]):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f); writer.writerow(columns);writer.writerows(rows)


def run(spec: dict, analysis_root: Path, work_dir: Path, output_dir: Path) -> dict:
    from data_storage.query import execute_query  # Canonical Data Storage DuckDB query path.
    validate_spec(spec)
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    snapshot=prepare_current_only(analysis_root,Path(work_dir),int(spec["date_from"][:4]),int(spec["date_to"][:4]))
    if not snapshot.get("period_to") or spec["date_to"] > snapshot["period_to"]:
        raise ValueError("Requested end date is beyond verified Analysis coverage: "+str(snapshot.get("period_to")))
    if not snapshot.get("period_from") or spec["date_from"] < snapshot["period_from"]:
        raise ValueError("Requested start date predates verified Analysis coverage")
    dataset=snapshot["dataset_path"]
    sql=build_sql(spec)
    # Verify selected manifest row counts match actual queryable Parquet data.
    cc,rr=execute_query(dataset,"SELECT COUNT(*) AS n FROM data")
    actual=rr[0][0]
    if actual != snapshot["selected_rows"]:
        raise ValueError(f"Parquet row-count mismatch: actual={actual} manifest={snapshot['selected_rows']}")
    ac,ar=execute_query(dataset,sql["audit"])
    audit_row=_records(ac,ar)[0]
    if audit_row["unknown_abnormal_code"] or audit_row["missing_win_payout_winner"]:
        raise ValueError("Abnormal code or missing winner payout requires review: "+str(audit_row))
    columns,rows=execute_query(dataset,sql["summary"])
    summary=_records(columns,rows)
    if (sum(int(r["entries"]) for r in summary)+int(audit_row["excluded_band_entries"]))!=audit_row["matching_entries"]:
        raise ValueError("Group entry counts do not reconcile")
    if any(int(r["starts"])+int(r["cancelled"])!=int(r["entries"]) for r in summary):
        raise ValueError("Starter denominators do not reconcile")
    if all(k in columns for k in ("win","second","third","other")):
        if any(sum(int(r[k]) for k in ("win","second","third","other"))!=int(r["starts"]) for r in summary):
            raise ValueError("Finish disposition does not reconcile")
    _write_json(output_dir/"query_spec.json",spec)
    _write_json(output_dir/"results.json",{"status":"PASS","columns":columns,"rows":summary})
    _write_csv(output_dir/"results.csv",columns,rows)
    if spec.get("detail",False):
        dc,dr=execute_query(dataset,sql["detail"])
        _write_csv(output_dir/"matching_entries.csv",dc,dr)
        audit_row["detail_rows_output"]=len(dr)
        audit_row["detail_truncated"]=bool(audit_row["matching_entries"]>len(dr))
    final={"status":"PASS","source":snapshot,"spec_sha256":hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
           "sql_sha256":{k:hashlib.sha256(v.encode()).hexdigest() for k,v in sql.items()},"input_parquet_rows":actual,
           "aggregation":audit_row,"summary_groups":len(rows),"warnings":[]}
    if audit_row["missing_place_payout_top3"]:
        final["warnings"].append("Some top-three finishers lack place payouts; short fields/non-payable places or missing data require review")
    if audit_row["excluded_band_entries"]:
        final["warnings"].append(f"Entries outside specified bands: {audit_row['excluded_band_entries']}")
    _write_json(output_dir/"query_audit.json",final)
    print(json.dumps({"status":"PASS","output_dir":str(output_dir),"generation_id":snapshot["generation_id"],"matched":audit_row["matching_entries"],"groups":len(rows)},ensure_ascii=False))
    return final


def main():
    p=argparse.ArgumentParser();p.add_argument("--analysis-root",type=Path,required=True)
    spec=p.add_mutually_exclusive_group(required=True);spec.add_argument("--spec-json");spec.add_argument("--spec-file",type=Path)
    p.add_argument("--work-dir",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    obj=json.loads(a.spec_json if a.spec_json is not None else a.spec_file.read_text(encoding="utf-8"))
    run(obj,a.analysis_root,a.work_dir,a.output_dir)

if __name__=="__main__":main()