#!/usr/bin/env python3
"""Single RaceNote T1/T2 intent resolver for ChatGPT-driven operations.

No model decisions or data transport occur in this planner. It chooses the
existing canonical execution paths; a caller must execute and read back each
stage. An ambiguous request fails rather than binding to the wrong BTDAY/day.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from racenote_forward_errors import DataInvalid, OrchestrationMissing, run_cli

BASE = Path("horse-racing/jrdb")
BTDAY = re.compile(r"BTDAY-\d{4}\Z")
DATE = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
MODE = ("BACKTEST", "FORWARD")
VERSIONS = ("v056", "v055-r6")
PREDICTION_INCOMING = "incoming/llm_decisions.json"
CONFIDENCE_INCOMING = "incoming/llm_confidence.json"


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise DataInvalid(f"unreadable canonical session/manifest: {path}") from exc
    if not isinstance(value, dict):
        raise DataInvalid(f"canonical record is not an object: {path}")
    return value


def _day(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value,str) or not DATE.fullmatch(value):
        raise DataInvalid("target_date must be a valid YYYY-MM-DD")
    from datetime import date
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError(value)
    except ValueError as exc:
        raise DataInvalid("nonexistent target_date") from exc
    return value


def t1_plan(mode: str, *, version: str, target_date: str | None = None,
            selection_id: str | None = None) -> dict:
    if mode not in MODE:
        raise DataInvalid("specify existing BACKTEST or FORWARD context")
    if version not in VERSIONS:
        raise DataInvalid("unsupported RaceNote version")
    target_date = _day(target_date)
    if mode == "BACKTEST":
        if target_date:
            raise DataInvalid("BACKTEST T1 selects from the canonical pool, not a guessed date")
        if selection_id and not BTDAY.fullmatch(selection_id):
            raise DataInvalid("invalid BTDAY selection")
        directory = "orchestrator-v056" if version == "v056" else "orchestrator"
        entry = (".github/workflows/racenote_v056_t1_orchestrator.yml"
                 if version == "v056" else
                 ".github/workflows/racenote_v055_r6_t1_orchestrator.yml")
        return {
            "schema_version": "racenote-t1-t2-command-v1", "mode": mode,
            "phase": "T1", "version": version, "action": "DISPATCH_EXISTING_ORCHESTRATOR",
            "workflow": entry,
            "request_directory": f"horse-racing/jrdb/backtests/requests/{directory}",
            "request": {"mode": "EXISTING" if selection_id else "NEXT",
                        "selection_id": selection_id},
            "execution_boundary": "ACTIONS_RESERVATION_T1_DELIVERY_READBACK",
        }
    if version != "v056":
        raise DataInvalid("FORWARD v0.5.5 is not the current supported entry")
    if selection_id:
        raise DataInvalid("FORWARD target is a race date, not a BTDAY selection")
    return {
        "schema_version": "racenote-t1-t2-command-v1", "mode": mode,
        "phase": "T1", "version": version,
        "action": "RESOLVE_CANONICAL_PACI_AND_DISPATCH",
        "target_date": target_date,
        "paci_canonical_folder_id": "1zFajenPU5jxInZCcmqZzkgiaYil3MD8r",
        "request_prefix": "[RACENOTE_FORWARD_T1]",
        "workflow": ".github/workflows/racenote_v056_forward_paci_t1.yml",
        "producer_acceptance": "AUTOMATIC_PREREQUISITE",
        "paci_locator": "EXACT_NAME_PARENT_AND_DATE_THROUGH_CONNECTED_DRIVE",
        "execution_boundary": "CANONICAL_PACI_ACCEPTANCE_T1_MAIN_ARTIFACT_READBACK",
    }


def _root_candidates(repo_root: Path, mode: str, version: str) -> list[Path]:
    if mode == "FORWARD":
        return sorted((repo_root / BASE / "daily").glob("*/v056_day/v056"))
    vdir = "v056" if version == "v056" else "v055"
    return sorted((repo_root / BASE / "backtests").glob(f"BTDAY-*/*/{vdir}"))


def _resolve_t2_root(repo_root: Path, mode: str, version: str, *,
                     target_date: str | None, selection_id: str | None) -> Path:
    if mode == "FORWARD" and version != "v056":
        raise DataInvalid("FORWARD T2 only supports v0.5.6")
    if selection_id and not BTDAY.fullmatch(selection_id):
        raise DataInvalid("invalid BTDAY selection")
    if mode == "FORWARD" and selection_id:
        raise DataInvalid("FORWARD T2 must not take a BTDAY selection")
    if mode == "BACKTEST" and target_date and not selection_id:
        raise DataInvalid("backtest target_date alone may match multiple BTDAY cycles")
    candidates = _root_candidates(repo_root, mode, version)
    if target_date:
        stamp=target_date.replace("-","")
        candidates=[x for x in candidates if (stamp in x.parts)]
    if selection_id:
        candidates=[x for x in candidates if selection_id in x.parts]
    candidates=[x for x in candidates if x.is_dir() and not x.is_symlink()
                and (x / "session.json").is_file()]
    if not candidates:
        raise OrchestrationMissing("no sealed T1 Reader/session found for this T2")
    if len(candidates) != 1:
        raise OrchestrationMissing(
            "multiple T1 sessions match; use the selection/date from the active T1 "
            "handoff rather than guessing or silently selecting the latest"
        )
    return candidates[0]


def t2_plan(repo_root: Path, mode: str, *, version: str,
            target_date: str | None = None, selection_id: str | None = None) -> dict:
    if mode not in MODE or version not in VERSIONS:
        raise DataInvalid("invalid mode/version")
    target_date=_day(target_date)
    root=_resolve_t2_root(repo_root,mode,version,
                          target_date=target_date,selection_id=selection_id)
    session=_read(root/"session.json")
    manifest=_read(root/"authoring_bundle/manifest.json")
    expected_contract=("v056-prediction-confidence-audit-newspaper-v1"
                       if version=="v056" else "v055-prediction-freeze-confidence-review-r6")
    if session.get("contract_revision") != expected_contract:
        raise DataInvalid("T2 session does not match the selected canonical version")
    if (session.get("market_blind") is not True
            or session.get("result_opened") is not False
            or session.get("target_market_opened",False) is not False
            or manifest.get("status") != "READY_FOR_LLM_RACE_BY_RACE_REVIEW"):
        raise DataInvalid("T2 lacks sealed CLEAN BLIND authoring boundary")
    if target_date and session.get("target_date") != target_date:
        raise DataInvalid("T2 session target_date mismatch")
    if selection_id and session.get("selection_id") != selection_id:
        raise DataInvalid("T2 session selection_id mismatch")
    if mode == "FORWARD":
        from datetime import date
        if (date.fromisoformat(session["target_date"])
                < datetime.now(ZoneInfo("Asia/Tokyo")).date()):
            raise DataInvalid("cannot retroactively run unsealed FORWARD T2")
    pred_frozen=(root/"frozen/day_handoff.json")
    conf_frozen=(root/"confidence_frozen/day_handoff.json")
    if conf_frozen.is_file():
        if not pred_frozen.is_file():
            raise DataInvalid("Confidence Freeze exists without Prediction Freeze")
        if (root/"turn2_summary.json").is_file():
            result=_read(root/"turn2_summary.json")
            if result.get("status")!="TURN2_COMPLETE":
                raise DataInvalid("incomplete canonical T2 summary")
            action="ALREADY_COMPLETE"
        else:
            raise DataInvalid("Confidence Freeze exists but T2 completion receipt is missing")
    elif pred_frozen.is_file():
        frozen=_read(pred_frozen)
        if frozen.get("status") != "PREDICTION_FROZEN_CLEAN_BLIND":
            raise DataInvalid("unverified Prediction Freeze status")
        action=("SUBMIT_CONFIDENCE_FREEZE" if (root/CONFIDENCE_INCOMING).is_file()
                else "AUTHOR_INDEPENDENT_CONFIDENCE")
    elif (root/"frozen").exists():
        raise DataInvalid("partial Prediction Freeze exists")
    else:
        action=("SUBMIT_PREDICTION_FREEZE" if (root/PREDICTION_INCOMING).is_file()
                else "AUTHOR_ALL_RACE_PREDICTIONS")
    return {
        "schema_version": "racenote-t1-t2-command-v1",
        "mode":mode, "phase":"T2", "version":version,
        "target_date":session.get("target_date"),
        "selection_id":session.get("selection_id"),
        "root":root.resolve().relative_to(repo_root.resolve()).as_posix(),
        "action":action,
        "prediction_draft":PREDICTION_INCOMING,
        "confidence_draft":CONFIDENCE_INCOMING,
        "prediction_freeze_workflow":
            ".github/workflows/racenote_v056_llm_prediction_freeze.yml"
            if version=="v056" else ".github/workflows/racenote_v055_llm_prediction_freeze.yml",
        "confidence_freeze_workflow":
            ".github/workflows/racenote_v056_llm_confidence_freeze.yml"
            if version=="v056" else ".github/workflows/racenote_v055_llm_confidence_freeze.yml",
        "execution_boundary":"LLM_AUTHORED_PREDICTION_THEN_INDEPENDENT_CONFIDENCE_FREEZE",
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase",choices=("T1","T2"))
    p.add_argument("--mode",required=True,choices=MODE)
    p.add_argument("--version",default="v056",choices=VERSIONS)
    p.add_argument("--target-date")
    p.add_argument("--selection-id")
    p.add_argument("--repo-root",type=Path,default=Path("."))
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=(t1_plan(args.mode,version=args.version,target_date=args.target_date,
                    selection_id=args.selection_id) if args.phase=="T1" else
            t2_plan(args.repo_root,args.mode,version=args.version,
                    target_date=args.target_date,selection_id=args.selection_id))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main,"T1_T2_COMMAND"))
