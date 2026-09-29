"""Offline Stage A CLI. Input ZIPs are read-only; output generations are exclusive."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile

import pyarrow.parquet as pq

from . import PARSER_VERSION
from .audit import summarize
from .raw_archive import LogicalAssetRegistry, read_archives
from .schema import schema_for, validated_table
from .stage_a_parser import ParseError, meet_key, parse


def now():
    return datetime.now(timezone.utc)


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_table(root, name, rows, partition=False):
    target = root / ("pre/" if name in {"meet","race"} else "provenance/") / name
    groups = defaultdict(list)
    for row in rows:
        date = row["race_date"] if name == "race" else row["meet_start_date"] if name == "meet" else None
        key = f"year={date.year:04d}/month={date.month:02d}" if partition and date else ""
        groups[key].append(row)
    if not groups:
        groups[""] = []
    for key, group in groups.items():
        folder = target / key
        folder.mkdir(parents=True, exist_ok=True)
        pq.write_table(validated_table(name, group), folder / "part-000.parquet", compression="zstd")


def _supplemental_audit(path):
    """Validate the January PoC archive and return schedule provenance facts."""
    with zipfile.ZipFile(path) as archive:
        names=set(archive.namelist())
        manifest_path="audit/201601_events_manifest.json"
        source_list_path="audit/201601_source_list.jsonl"
        summary_path="audit/201601_summary.json"
        schedule_path="raw/2016/01/schedule.html"
        required={manifest_path,source_list_path,summary_path,schedule_path}
        if not required.issubset(names):
            raise ValueError(f"supplemental archive missing required members: {sorted(required-names)}")
        summary=json.loads(archive.read(summary_path))
        manifest=json.loads(archive.read(manifest_path))
        source_lines=[line for line in archive.read(source_list_path).decode("utf-8").splitlines() if line.strip()]
        event_paths={n for n in names if re.fullmatch(r"raw/2016/01/events/[^/]+\.html",n)}
        manifest_success=[s for s in manifest.get("sources",[]) if s.get("status")=="success"]
        declared={"raw/"+s["relative_path"] for s in manifest_success}
        if summary.get("discovered_events")!=60 or summary.get("successful_events")!=60 or summary.get("failed_events")!=0:
            raise ValueError("supplemental summary is not discovered=60/success=60/failed=0")
        if manifest.get("requested_sources")!=60 or manifest.get("successful_sources")!=60 or manifest.get("failed_sources")!=0:
            raise ValueError("supplemental event manifest is not 60/60/0")
        if len(event_paths)!=60 or event_paths!=declared or len(source_lines)!=60:
            raise ValueError("supplemental event HTML/manifest/source-list counts do not agree at 60")
        schedule=archive.read(schedule_path)
        schedule_sha=sha256(schedule).hexdigest()
        if schedule_sha!=summary.get("schedule_sha256"):
            raise ValueError("supplemental January schedule SHA-256 mismatch")
        return {"provider":"keirin.jp","drive_archive_name":path.name,"raw_relative_path":schedule_path,
                "raw_sha256":schedule_sha,"source_url":summary.get("schedule_url"),
                "http_status":summary.get("schedule_http_status"),"content_type":"text/html",
                "request_method":"GET","audit_timestamp":summary.get("generated_at_utc"),
                "schedule_size_bytes":len(schedule),"discovered_events":60,"successful_events":60,
                "failed_events":0,"event_html_count":60,"source_list_count":60}


def run(archives, output, parser_commit, expected_assets=8464, supplemental_archives=()):
    archives = sorted(map(Path, archives))
    supplemental_archives=sorted(map(Path,supplemental_archives))
    if len(archives) != 10 or {int(re.search(r"(20\d\d)\.zip$", p.name)[1]) for p in archives} != set(range(2016,2026)):
        raise ValueError("exactly ten annual ZIPs (2016–2025) are required")
    if len({p.name for p in [*archives,*supplemental_archives]})!=len(archives)+len(supplemental_archives):
        raise ValueError("archive file names must be unique across annual and supplemental inputs")
    for path in supplemental_archives:
        if not re.fullmatch(r"keirin-historical-20\d\d-\d\d-poc-\d+\.zip",path.name):
            raise ValueError(f"invalid supplemental archive name: {path.name}")
    schema_text = {name:str(schema_for(name)) for name in ("meet","race","source_asset","row_source_map","parse_audit")}
    schema_hash = sha256(json.dumps(schema_text, sort_keys=True).encode()).hexdigest()
    # Generation identity includes all raw ZIP digests and the parser commit.
    all_archives=[*archives,*supplemental_archives]
    archive_sha = {p.name:sha256(p.read_bytes()).hexdigest() for p in all_archives}
    input_hash = sha256(json.dumps({"archives":archive_sha,"parser_commit":parser_commit,"schema_hash":schema_hash},sort_keys=True).encode()).hexdigest()
    timestamp = now()
    generation = f"KEIRIN_CANON_V0_1_{timestamp:%Y%m%d_%H%M}_{input_hash[:12]}"
    target = Path(output) / "v0_1" / "generations" / generation
    target.mkdir(parents=True, exist_ok=False)
    meets, races, assets, audits, maps = [], [], [], [], []
    actual_by_meet = {}
    logical_assets={}
    asset_registry=LogicalAssetRegistry()
    canonical_keys_by_asset_path={}
    replica_count=0
    for archive_name, name, raw, record in read_archives(all_archives):
        digest = sha256(raw).hexdigest()
        is_new_logical_asset=asset_registry.register(name,digest)
        asset_key = sha256((archive_name+"|"+name+"|"+digest).encode()).hexdigest()
        acquired = datetime.fromisoformat(record["started_at_utc"])
        assets.append(dict(source_asset_key=asset_key, provider="keirin.jp",raw_sha256=digest,
                           drive_archive_name=archive_name,raw_relative_path=name,acquired_at=acquired,
                           parser_version=PARSER_VERSION,source_url=record.get("final_url") or record.get("url"),
                           request_method=record.get("request_method"),request_form_json=json.dumps(record.get("form_data"),ensure_ascii=False,sort_keys=True),
                           http_status=record.get("http_status"),content_type=record.get("content_type"),source_updated_at=None))
        if not is_new_logical_asset:
            replica_count+=1
            original=logical_assets[name]
            # Same logical path and same SHA is parsed once; each physical source
            # archive remains represented and maps to the canonical rows.
            for table,key in original["keys"]:
                maps.append(dict(table_name=table,canonical_key=key,source_asset_key=asset_key,
                                 parser_version=PARSER_VERSION,source_locator="identical_sha_replica",
                                 parse_rule="sha256-identical-deduplication"))
            audits.append(dict(source_asset_key=asset_key,parse_status=original["parse_status"],meet_rows=original["meet_rows"],
                               race_rows=original["race_rows"],warnings_count=original["warnings_count"],
                               errors_count=original["errors_count"],warning_codes=original["warning_codes"],
                               error_codes=original["error_codes"],parser_version=PARSER_VERSION,generated_at=timestamp))
            continue
        try:
            meet, parsed_races, days, warnings = parse(raw, record)
            for row in [meet,*parsed_races]:
                row.update(source_provider="keirin.jp",source_raw_sha256=digest,acquired_at=acquired)
            meets.append(meet)
            races.extend(parsed_races)
            actual_by_meet[meet["meet_key"]] = set(days)
            asset_maps=[dict(table_name=table,canonical_key=row[key],source_asset_key=asset_key,
                             parser_version=PARSER_VERSION,source_locator="jsonData['PJ0301'].raceDayDataList" if table=="pre/race" else "jsonData['PC0201'].C0201data",
                             parse_rule=PARSER_VERSION) for table,key,rows in (("pre/meet","meet_key",[meet]),("pre/race","race_key",parsed_races)) for row in rows]
            maps.extend(asset_maps)
            status, errors = "parsed", []
        except (ParseError, ValueError, KeyError, TypeError) as exc:
            asset_maps=[]
            status, errors, warnings, parsed_races = "quarantined", [str(exc)], [], []
        audits.append(dict(source_asset_key=asset_key,parse_status=status,meet_rows=int(status=="parsed"),
                           race_rows=len(parsed_races),warnings_count=len(warnings),errors_count=len(errors),
                           warning_codes=json.dumps(sorted(set(warnings))),error_codes=json.dumps(errors),
                           parser_version=PARSER_VERSION,generated_at=timestamp))
        audit=audits[-1]
        logical_assets[name]={"sha256":digest,"keys":[(m["table_name"],m["canonical_key"]) for m in asset_maps],
                              "meet_rows":int(status=="parsed"),"race_rows":len(parsed_races),
                              "parse_status":status,"warnings_count":audit["warnings_count"],
                              "errors_count":audit["errors_count"],"warning_codes":audit["warning_codes"],
                              "error_codes":audit["error_codes"]}
    # Monthly discovery may capture one official meet twice at a month boundary.
    # Merge only when all overlapping race tokens agree; retain both raw mappings.
    by_start = defaultdict(list)
    for m in meets:
        by_start[(m["venue_code"],m["meet_start_date"])].append(m)
    races_by_source = defaultdict(list)
    for r in races:
        races_by_source[r["source_raw_sha256"]].append(r)
    asset_sha = {a["source_asset_key"]:a["raw_sha256"] for a in assets}
    meet_map_by_sha = defaultdict(list)
    for mapping in maps:
        if mapping["table_name"] == "pre/meet":
            meet_map_by_sha[asset_sha[mapping["source_asset_key"]]].append(mapping)
    removed = set()
    retained_extra = set()
    for group in by_start.values():
        if len(group) < 2:
            continue
        primary = sorted(group,key=lambda x:x["source_raw_sha256"])[0]
        primary_races = {r["race_key"]:r for r in races_by_source[primary["source_raw_sha256"]]}
        for candidate in group:
            if candidate is primary:
                continue
            other_races = {r["race_key"]:r for r in races_by_source[candidate["source_raw_sha256"]]}
            overlap = primary_races.keys() & other_races.keys()
            compatible = (candidate["event_name"]==primary["event_name"] and
                          candidate["meet_end_date"]==primary["meet_end_date"] and
                          all(primary_races[k]["detail_token"]==other_races[k]["detail_token"] for k in overlap))
            if not compatible:
                continue
            removed.add(candidate["source_raw_sha256"])
            for key,row in other_races.items():
                if key not in primary_races:
                    primary_races[key] = row
                    row["meet_key"] = primary["meet_key"]
                    retained_extra.add(id(row))
            for mapping in meet_map_by_sha[candidate["source_raw_sha256"]]:
                mapping["canonical_key"] = primary["meet_key"]
    meets = [m for m in meets if m["source_raw_sha256"] not in removed]
    races = [r for r in races if r["source_raw_sha256"] not in removed or id(r) in retained_extra]
    # Preserve all source links; duplicate raw rows map to a single canonical row.
    unique_races = {}
    for r in races:
        previous = unique_races.get(r["race_key"])
        if previous and previous["detail_token"]==r["detail_token"]:
            continue
        if not previous:
            unique_races[r["race_key"]] = r
    races = [r for r in races if unique_races.get(r["race_key"]) is r or
             (unique_races.get(r["race_key"]) and unique_races[r["race_key"]]["detail_token"]!=r["detail_token"])]
    # Resolve genuinely distinct same-venue/same-start identity collisions.
    collisions = defaultdict(list)
    for m in meets:
        collisions[(m["venue_code"],m["meet_start_date"])].append(m)
    for (venue, start), group in collisions.items():
        if len(group) < 2:
            continue
        for number, meet in enumerate(sorted(group,key=lambda x:x["source_raw_sha256"]),1):
            old = meet["meet_key"]
            new = meet_key(venue,start,number)
            meet["meet_key"] = new
            actual_by_meet[new] = actual_by_meet[old]
            for r in races_by_source[meet["source_raw_sha256"]]:
                r["meet_key"] = new
            for mapping in meet_map_by_sha[meet["source_raw_sha256"]]:
                mapping["canonical_key"] = new
    outside_range = sum(not 2016<=r["race_date"].year<=2025 for r in races)
    races = [r for r in races if 2016<=r["race_date"].year<=2025]
    valid_race_keys = {r["race_key"] for r in races}
    maps = [m for m in maps if m["table_name"]!="pre/race" or
            m["canonical_key"] in valid_race_keys]
    supporting_assets=[_supplemental_audit(p) for p in supplemental_archives]
    jan_event_count=sum(1 for name in logical_assets if name.startswith("raw/2016/01/events/"))
    coverage = summarize(meets,races,assets,audits,actual_by_meet,
                         {p.name:archive_sha[p.name] for p in archives},expected_assets,
                         deduplicated_replicas=replica_count,supplemental_event_assets=jan_event_count,
                         supporting_assets=supporting_assets)
    coverage["raw_coverage"]["supplemental_archive_count"]=len(supplemental_archives)
    coverage["raw_coverage"]["all_archive_sha256"]=archive_sha
    coverage["raw_coverage"]["archive_names"]=sorted(p.name for p in all_archives)
    coverage["raw_coverage"]["out_of_range_race_rows_excluded"] = outside_range
    for name,rows in (("meet",meets),("race",races),("source_asset",assets),("row_source_map",maps),("parse_audit",audits)):
        write_table(target,name,rows,name in {"meet","race"})
    manifest = dict(generation=generation,schema_version="0.1",stage="A",source_range="2016-2025",
                    source_provider="keirin.jp",source_policy="personal_research_approved",parser_version=PARSER_VERSION,
                    parser_commit=parser_commit,schema_hash=schema_hash,archive_sha256=archive_sha,
                    input_hash=input_hash,pre_post_separated=True,timestamp_timezone="UTC; source acquisition timestamps are UTC",
                    generated_at=timestamp.isoformat(),status=coverage["status"],
                    supporting_raw_assets=supporting_assets)
    dump(target/"manifest/generation.json",manifest)
    dump(target/"manifest/schema.json",schema_text)
    dump(target/"manifest/coverage.json",coverage)
    return target, manifest, coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives",type=Path,required=True,help="directory with ten immutable annual ZIPs")
    parser.add_argument("--supplemental-archive",type=Path,action="append",default=[],
                        help="additional immutable Raw archive; repeat for multiple archives")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--parser-commit",required=True)
    args = parser.parse_args()
    annual=sorted(p for p in args.archives.glob("keirin-historical-*.zip")
                  if re.fullmatch(r"keirin-historical-20\d\d\.zip",p.name))
    target,_,coverage = run(annual,args.output,args.parser_commit,supplemental_archives=args.supplemental_archive)
    print(json.dumps({"output":str(target),"coverage":coverage},ensure_ascii=False,default=str))
    return 0 if coverage["status"]=="pass" else 2


if __name__=="__main__":
    raise SystemExit(main())
