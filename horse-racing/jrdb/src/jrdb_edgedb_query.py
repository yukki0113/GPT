#!/usr/bin/env python3
"""Stable, consumer-neutral query boundary over EdgeDB generations."""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json, tempfile
from pathlib import Path
from typing import Any
import jrdb_edge_matcher_v0_2 as matcher
from jrdb_edge_v04_observe_cohort import validate as validate_cohort
from jrdb_edge_v04_observe_shadow import condition_matches

SCHEMA_VERSION = "edgedb-query/v1"
VERSION = "1.0.0"
PROFILES = {"STANDARD": {"STANDARD"}, "STANDARD_PLUS_SHADOW": {"STANDARD", "SHADOW"}, "RESEARCH_ALL": {"STANDARD", "SHADOW", "OBSERVE_ONLY"}}
LIFECYCLES = {"STANDARD", "SHADOW", "OBSERVE_ONLY"}
ADAPTERS = {"jrdb_registry_jsonl_v0_2", "jrdb_registry_jsonl_v0_3", "jrdb_observe_cohort_v0_1"}

class ManifestError(ValueError): pass

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def _resolve(root: Path, rel: str) -> Path:
    p=Path(rel)
    if p.is_absolute() or ".." in p.parts: raise ManifestError(f"unsafe source path: {rel}")
    out=(root/p).resolve()
    if root.resolve() not in (out,*out.parents): raise ManifestError(f"source escapes repository root: {rel}")
    return out

def load_manifest(path: str|Path, root: str|Path|None=None) -> tuple[dict[str,Any],list[dict[str,Any]]]:
    path=Path(path); repo_root=Path(root) if root else path.resolve().parents[4]
    try: doc=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as e: raise ManifestError(f"cannot read manifest: {e}") from e
    if doc.get("schema_version")!="edgedb-current-manifest/v1" or doc.get("query_contract")!=SCHEMA_VERSION: raise ManifestError("unsupported manifest schema/contract")
    if not doc.get("manifest_revision") or not isinstance(doc.get("sources"),list): raise ManifestError("manifest revision and sources are required")
    if doc.get("production_impact")!="NONE": raise ManifestError("production_impact must be NONE")
    seen=set(); identities={}; loaded=[]
    for src in doc["sources"]:
        for k in ("source_key","source_generation","lifecycle","adapter_type","path","enabled","production_eligible","display_eligible_default","prediction_eligible_default","notes"):
            if k not in src: raise ManifestError(f"source missing {k}")
        if src["source_key"] in seen: raise ManifestError("duplicate source_key")
        seen.add(src["source_key"])
        if not isinstance(src["enabled"], bool) or any(not isinstance(src[k], bool) for k in ("production_eligible","display_eligible_default","prediction_eligible_default")):
            raise ManifestError(f"source eligibility flags must be booleans: {src['source_key']}")
        if not isinstance(src["path"], str) or not src["path"]:
            raise ManifestError(f"source path must be a non-empty string: {src['source_key']}")
        if src["lifecycle"] in {"SHADOW","OBSERVE_ONLY"} and src["production_eligible"]:
            raise ManifestError(f"{src['lifecycle']} source cannot be production eligible: {src['source_key']}")
        expected_adapter={"v0.2":"jrdb_registry_jsonl_v0_2","v0.3":"jrdb_registry_jsonl_v0_3","v0.4":"jrdb_observe_cohort_v0_1"}.get(src["source_generation"])
        if expected_adapter != src["adapter_type"]:
            raise ManifestError(f"adapter/source generation mismatch: {src['source_key']}")
        if src["lifecycle"] not in LIFECYCLES: raise ManifestError(f"unsupported lifecycle: {src['lifecycle']}")
        if src["adapter_type"] not in ADAPTERS: raise ManifestError(f"unsupported adapter: {src['adapter_type']}")
        if not src["enabled"]: continue
        p=_resolve(repo_root,src["path"])
        if not p.is_file(): raise ManifestError(f"source missing (no fallback): {src['source_key']}: {p}")
        expected=src.get("expected_sha256")
        semantic_identity=expected or src.get("expected_fingerprint_set_sha256")
        if semantic_identity:
            prior=identities.get(semantic_identity)
            if prior is not None and prior!=src["lifecycle"]:
                raise ManifestError("same immutable source identity claims contradictory lifecycle")
            identities[semantic_identity]=src["lifecycle"]
        if expected and sha256(p)!=expected: raise ManifestError(f"source SHA-256 mismatch: {src['source_key']}")
        if src["adapter_type"]=="jrdb_observe_cohort_v0_1":
            cohort=json.loads(p.read_text(encoding="utf-8")); validate_cohort(cohort)
            fp=src.get("expected_fingerprint_set_sha256")
            if fp and cohort.get("fingerprint_set_sha256")!=fp: raise ManifestError("cohort fingerprint mismatch")
            if src.get("expected_rows") is not None and cohort.get("cohort_row_count")!=src["expected_rows"]: raise ManifestError("cohort row-count mismatch")
            loaded.append({**src,"data":cohort})
        else:
            if p.name.endswith(".gz.b64"):
                try: compressed=base64.b64decode(p.read_text(encoding="ascii"),validate=True)
                except (OSError,ValueError) as e: raise ManifestError(f"invalid base64 registry snapshot: {src['source_key']}") from e
                snapshot_sha=src.get("snapshot_gzip_sha256")
                if snapshot_sha and hashlib.sha256(compressed).hexdigest()!=snapshot_sha: raise ManifestError(f"compressed snapshot SHA-256 mismatch: {src['source_key']}")
                with tempfile.TemporaryDirectory(prefix="edgedb-registry-") as temp:
                    expanded=Path(temp)/"registry.jsonl"
                    try:
                        with gzip.GzipFile(fileobj=__import__("io").BytesIO(compressed),mode="rb") as source, expanded.open("wb") as target:
                            for block in iter(lambda:source.read(1024*1024),b""): target.write(block)
                    except (OSError,EOFError) as e: raise ManifestError(f"invalid gzip registry snapshot: {src['source_key']}") from e
                    rows=matcher.load_registry(expanded)
            elif p.suffix==".gz":
                with tempfile.TemporaryDirectory(prefix="edgedb-registry-") as temp:
                    expanded=Path(temp)/"registry.jsonl"
                    with gzip.open(p,"rb") as source, expanded.open("wb") as target:
                        for block in iter(lambda:source.read(1024*1024),b""): target.write(block)
                    rows=matcher.load_registry(expanded)
            else:
                rows=matcher.load_registry(p)
            loaded.append({**src,"data":rows,"v03_shadow_by_id":{str(r.get("edge_id")):r.get("v03_shadow") for r in rows} if src["source_generation"]=="v0.3" else {}})
    if not loaded: raise ManifestError("manifest has no enabled sources")
    return doc,loaded

def _registry_signals(src:dict[str,Any],facts:dict[str,Any])->list[dict[str,Any]]:
    rows=matcher.match_runner(src["data"],facts,profile=matcher.PROFILE_STANDARD)
    out=[]
    for m in rows:
        ev=m.get("evidence") or {}; pres=m.get("presentation") or {}
        out.append({"signal_id":str(m.get("edge_id")),"source_generation":src["source_generation"],"lifecycle":src["lifecycle"],"source_id":src["source_key"],"family":m.get("family"),"status":m.get("registry_status"),"production_eligible":bool(src["production_eligible"]),"performance":{"signal":ev.get("performance_signal","NEUTRAL"),"evidence_level":m.get("performance_evidence_level","NONE"),"p_value":ev.get("performance_p_value"),"q_value":ev.get("performance_q_value")},"value":{"signal":ev.get("value_signal","UNASSESSED"),"evidence_level":m.get("value_evidence_level","NONE"),"p_value":ev.get("value_p_value"),"q_value":ev.get("value_q_value")},"presentation":pres,"matched_conditions":m.get("matched_conditions",{}),"audit":{**m,"v03_shadow":src["v03_shadow_by_id"].get(str(m.get("edge_id"))) if src["source_generation"]=="v0.3" else None}})
    return out

def _observe_signals(src:dict[str,Any],facts:dict[str,Any])->list[dict[str,Any]]:
    out=[]; cohort=src["data"]
    vals=facts.get("facts",facts)
    for row in cohort["rows"]:
        if not condition_matches(row,vals): continue
        out.append({"signal_id":row["cohort_id"],"source_generation":src["source_generation"],"lifecycle":"OBSERVE_ONLY","source_id":src["source_key"],"family":row["family"],"status":"OBSERVE_ONLY","production_eligible":False,"performance":{"signal":"MATCH","evidence_level":"OBSERVE_ONLY"},"value":{"signal":"UNASSESSED","evidence_level":"OBSERVE_ONLY"},"presentation":{"role":"OBSERVE_ONLY","conflict":False},"matched_conditions":row["conditions"],"audit":{"cohort_id":row["cohort_id"],"candidate_id":row["candidate_id"],"template_id":row["template_id"],"condition_fingerprint":row["condition_fingerprint"],"historical_source":row["historical_source"]}})
    return out

def query(facts:list[dict[str,Any]], manifest_path:str|Path, *, profile="STANDARD", only_matched=False, race_horse_key=None, horse_id=None, root=None)->list[dict[str,Any]]:
    if profile not in PROFILES: raise ValueError(f"unsupported profile: {profile}")
    manifest,sources=load_manifest(manifest_path,root)
    results=[]
    for fact in facts:
        key={k:fact.get(k) for k in ("race_date","race_key","race_horse_key","horse_id","horse_no") if k in fact}
        if race_horse_key and key.get("race_horse_key")!=race_horse_key: continue
        if horse_id and key.get("horse_id")!=horse_id: continue
        signals=[]; audit=[]
        for src in sources:
            if src["lifecycle"] not in PROFILES[profile]: continue
            audit.append({"source_key":src["source_key"],"generation":src["source_generation"],"lifecycle":src["lifecycle"]})
            if src["adapter_type"]=="jrdb_observe_cohort_v0_1": signals.extend(_observe_signals(src,fact))
            else: signals.extend(_registry_signals(src,fact))
        lifecycle_order={"STANDARD":0,"SHADOW":1,"OBSERVE_ONLY":2}
        signals.sort(key=lambda s:(lifecycle_order[s["lifecycle"]],s["source_generation"],str(s["signal_id"])))
        if only_matched and not signals: continue
        results.append({"schema_version":SCHEMA_VERSION,"query_engine_version":VERSION,"manifest_revision":manifest["manifest_revision"],"profile":profile,"key":key,"signals":signals,"source_audit":audit})
    results.sort(key=lambda r:tuple(str(r["key"].get(k) or "") for k in ("race_date","race_key","horse_no","horse_id")))
    return results

def read_jsonl(path): return [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]
def main():
    p=argparse.ArgumentParser(description=__doc__); mode=p.add_mutually_exclusive_group(required=True); mode.add_argument("--facts-jsonl"); mode.add_argument("--paci")
    h=p.add_mutually_exclusive_group(); h.add_argument("--analysis-root"); h.add_argument("--analysis-db")
    p.add_argument("--manifest",default="horse-racing/jrdb/config/edgedb/current_manifest.json"); p.add_argument("--profile",choices=tuple(PROFILES),default="STANDARD"); p.add_argument("--race-horse-key"); p.add_argument("--horse-id"); p.add_argument("--only-matched",action="store_true"); p.add_argument("--output-jsonl",required=True); a=p.parse_args()
    if a.facts_jsonl: facts=read_jsonl(a.facts_jsonl)
    else:
        if not a.analysis_root and not a.analysis_db: p.error("--paci requires --analysis-root or --analysis-db")
        from build_jrdb_edge_current_facts_v0_2 import build_current_facts
        facts,_=build_current_facts(a.paci,analysis_root=a.analysis_root,analysis_db=a.analysis_db)
    rows=query(facts,a.manifest,profile=a.profile,only_matched=a.only_matched,race_horse_key=a.race_horse_key,horse_id=a.horse_id)
    with Path(a.output_jsonl).open("w",encoding="utf-8",newline="\n") as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
