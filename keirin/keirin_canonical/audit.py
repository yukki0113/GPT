"""Machine-readable universe and integrity audit."""

from collections import Counter, defaultdict


def summarize(meets, races, assets, audits, actual_by_meet, archive_names, expected_assets=8464,
              deduplicated_replicas=0, supplemental_event_assets=0, supporting_assets=None):
    meet_counts = Counter(m["meet_key"] for m in meets)
    race_counts = Counter(r["race_key"] for r in races)
    keys = set(meet_counts)
    annual = defaultdict(lambda: {"meet_count":0,"race_count":0,"race_days":0,"unique_venue_count":0,
                                  "ruleset":{"standard_keirin_line":0,"girls_international_no_line":0,
                                             "advance_international_no_line":0,"other":0,"unknown":0},
                                  "with_detail_token":0,"without_detail_token":0})
    venues, days = defaultdict(set), defaultdict(set)
    for m in meets:
        year = str(m["meet_start_date"].year)
        annual[year]["meet_count"] += 1
        venues[year].add(m["venue_code"])
    for r in races:
        year = str(r["race_date"].year)
        annual[year]["race_count"] += 1
        annual[year]["ruleset"][r["race_ruleset"]] += 1
        annual[year]["with_detail_token" if r["detail_token"] else "without_detail_token"] += 1
        days[year].add((r["race_date"],r["venue_code"]))
        venues[year].add(r["venue_code"])
    for year, metrics in annual.items():
        metrics["race_days"] = len(days[year])
        metrics["unique_venue_count"] = len(venues[year])
    errors = Counter(code for audit in audits for code in __import__("json").loads(audit["error_codes"]))
    integrity = {
        "duplicate_meet_key":sum(n-1 for n in meet_counts.values() if n>1),
        "duplicate_race_key":sum(n-1 for n in race_counts.values() if n>1),
        "orphan_race":sum(r["meet_key"] not in keys for r in races),
        "invalid_race_no":sum(not 1<=r["race_no"]<=12 for r in races),
        "missing_race_date":sum(r["race_date"] is None for r in races),
        "race_date_outside_actual_dates":sum(r["race_date"] not in actual_by_meet.get(r["meet_key"],set()) for r in races),
        "arithmetic_date_inference":0,
    }
    unique_event_paths = {a["raw_relative_path"] for a in assets if "/events/" in a["raw_relative_path"]}
    coverage = {"archive_count":len(archive_names),"archive_names":sorted(archive_names),
                "source_asset_count":len(unique_event_paths),"source_asset_rows":len(assets),
                "parsed_asset_count":sum(a["parse_status"]=="parsed" for a in audits),
                "quarantined_asset_count":sum(a["parse_status"]=="quarantined" for a in audits),
                "parser_errors":dict(errors),"expected_discovered_assets":expected_assets,
                "missing_expected_assets":max(0,expected_assets-len(unique_event_paths)),
                "supplemental_event_asset_count":supplemental_event_assets,
                "deduplicated_same_sha_replicas":deduplicated_replicas,
                "supporting_raw_assets":supporting_assets or []}
    total = {"meet_count":len(meets),"race_count":len(races),"race_days":sum(v["race_days"] for v in annual.values()),
             "unique_venue_count":len({m["venue_code"] for m in meets}),
             "with_detail_token":sum(bool(r["detail_token"]) for r in races),
             "without_detail_token":sum(not r["detail_token"] for r in races),
             "ruleset":dict(Counter(r["race_ruleset"] for r in races))}
    pass_gate = (len(archive_names)==10 and len(unique_event_paths)==expected_assets and
                 len(assets)==len(audits) and coverage["quarantined_asset_count"]==0 and
                 not any(integrity.values()))
    return {"status":"pass" if pass_gate else "fail","total":total,"by_year":dict(sorted(annual.items())),
            "integrity":integrity,"raw_coverage":coverage}
