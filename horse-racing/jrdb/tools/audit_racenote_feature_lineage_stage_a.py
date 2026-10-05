#!/usr/bin/env python3
"""Generate the structural JRDB-to-RaceNote Stage A feature inventory.

The inventory is intentionally a reviewed field catalog rather than a guess
based on database column names. Source paths and offsets cite the production
fixed-width parser and RaceNote normalizer; Reader exposure is checked against
the representative, committed v0.4.6 clean Reader witness.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
JRDB = ROOT / "horse-racing" / "jrdb"
WITNESS = JRDB / "backtests/BTDAY-0048/20260207/forecast_prep/reader/racenote_reader_20260207_東京1R.json"

# field_id, name, category, record, raw field + byte range, raw/derived,
# derivation, paths in Reader View, v046 clean Reader inclusion, status,
# semantic note, overlap candidates
ROWS = [
    ("race.surface_distance", "芝/ダート・距離", "suitability_context", "BAC", "surface_code@25:1;distance_raw@21:4", "raw", "BAC fixed-width decode", "race.surface,race.distance_m", True, "CURRENT_VISIBLE", "今回条件の記述値。", "race.course_layout;KYI distance_fit"),
    ("race.class_grade", "クラス・格", "class_level", "BAC", "race_class_code@30:2;grade_code@36:1", "raw", "BAC fixed-width decode", "race.class,race.grade", True, "CURRENT_VISIBLE", "番組上のクラス/格と個体JRDBクラス指標は別概念。", "KYI jrdb_class"),
    ("race.symbols", "レース条件記号", "suitability_context", "BAC", "symbol_code@32:3;weight_rule_code@35:1", "derived", "Normalizer.symbols / weight rule decoder", "race.race_conditions,race.weight_rule", True, "DERIVED_VISIBLE", "3桁条件コードを制約ラベルへデコード。", "race.class_grade"),
    ("horse.idm", " IDM", "ability_performance", "KYI", "idm@55:5", "raw", "KYI parser numeric field", "horses[].ability.idm", True, "CURRENT_VISIBLE", "JRDB能力値。", "horse.total_index;recent_runs[].performance.idm"),
    ("horse.total_index", "総合指数", "ability_performance", "KYI", "total_index@85:5", "raw", "KYI parser numeric field", "horses[].ability.total_index", True, "CURRENT_VISIBLE", "事前評価の合成指数。内部算出式は本監査範囲で未確認。", "horse.idm;horse.jrdb_ratings.info_index"),
    ("horse.info_index", "情報指数", "jrdb_composite", "KYI", "info_index@65:5", "raw", "KYI parser numeric field", "horses[].jrdb_ratings.info_index", True, "CURRENT_VISIBLE", "JRDB提供の指数。", "horse.total_index;horse.idm"),
    ("horse.jockey_index", "騎手指数", "jockey_trainer", "KYI", "jockey_index@60:5", "raw", "KYI parser numeric field", "horses[].jrdb_ratings.jockey_index", True, "CURRENT_VISIBLE", "現騎手名と異なる数値評価。", "horse.jockey_expected_top2_rate"),
    ("horse.stable_index", "厩舎指数", "jockey_trainer", "KYI", "stable_index@150:5", "raw", "KYI parser numeric field", "horses[].jrdb_ratings.stable_index", True, "CURRENT_VISIBLE", "厩舎評価の数値指標。", "horse.stable_evaluation;training.condition_index"),
    ("horse.longshot_index", "穴指数", "jrdb_composite", "KYI", "longshot_index@161:3", "raw", "KYI parser numeric field", "horses[].jrdb_ratings.longshot_index", True, "CURRENT_VISIBLE", "複合評価と思われるが公式定義式は未確認。", "horse.total_index;horse.info_index"),
    ("horse.jockey_expected_top2_rate", "騎手連対期待率", "jockey_trainer", "KYI", "jockey_expected_top2_rate@157:4", "raw", "KYI parser numeric field", "horses[].jrdb_ratings.jockey_expected_top2_rate", True, "CURRENT_VISIBLE", "単位/較正定義は外部コードブックで要確認。", "horse.jockey_index"),
    ("horse.jrdb_class", "JRDBクラス", "class_level", "KYI", "jrdb_class_code@167:2", "derived", "KYI code decode", "horses[].ability.jrdb_class", True, "DERIVED_VISIBLE", "個体のJRDBクラス判定。番組クラスとは区別。", "race.class_grade"),
    ("horse.running_style", "脚質", "pace_position", "KYI", "running_style_code@90:1", "derived", "KYI code decode", "horses[].ability.running_style", True, "DERIVED_VISIBLE", "コードを脚質ラベルへ変換。", "pace.indices.front;pace.indices.position"),
    ("horse.pace_indices", "ペース/位置指数", "pace_position", "KYI", "front@359:5;pace@364:5;late@369:5;position@374:5", "raw", "KYI parser numeric fields", "horses[].pace.indices.{front,pace,late,position}", True, "CURRENT_VISIBLE", "4軸の数値指標。", "pace.ranks;forecast_positions"),
    ("horse.pace_ranks", "ペース/位置順位", "pace_position", "KYI", "front@453:2;pace@455:2;late@457:2;position@459:2", "raw", "KYI parser numeric fields", "horses[].pace.ranks.{front,pace,late,position}", True, "CURRENT_VISIBLE", "指数に対応する順位。欠損を含む。", "pace.indices"),
    ("horse.forecast_positions", "想定位置取り", "pace_position", "KYI", "mid@380:2,382:2,384:1;last3f@385:2,387:2,389:1;finish@390:2,392:2,394:1", "derived", "KYI tuple decode to order/margin/lane", "horses[].pace.forecast_positions", True, "DERIVED_VISIBLE", "想定隊列の順・差・内外。", "pace.indices;pace.ranks"),
    ("horse.start_index", "スタート指数", "pace_position", "KYI", "start_index@520:4", "raw", "KYI parser numeric field", "horses[].pace.start_index", True, "CURRENT_VISIBLE", "スタートに関する数値指標。", "horse.late_break_rate"),
    ("horse.late_break_rate", "出遅れ率", "pace_position", "KYI", "late_break_rate@524:4", "raw", "KYI parser numeric field", "horses[].pace.late_break_rate", True, "CURRENT_VISIBLE", "率のスケール詳細は要確認。", "horse.start_index"),
    ("horse.distance_fit", "距離適性", "suitability_context", "KYI", "distance_fit_code@91:1", "derived", "KYI code decode", "horses[].ability.distance_fit", True, "DERIVED_VISIBLE", "カテゴリ評価。", "pedigree_context.distance_ranges;history same_distance"),
    ("horse.surface_fit", "芝/ダート適性", "suitability_context", "KYI", "turf_fit_code@334:1;dirt_fit_code@335:1", "derived", "KYI code decode", "horses[].ability.surface_fit", True, "DERIVED_VISIBLE", "表面別カテゴリ評価。", "distance_fit;heavy_track_fit"),
    ("horse.heavy_track_fit", "道悪適性", "suitability_context", "KYI", "heavy_track_fit_code@166:1", "derived", "KYI code decode", "horses[].ability.heavy_track_fit", True, "DERIVED_VISIBLE", "3段階コードのデコード。", "surface_fit;recent_runs.track_condition"),
    ("horse.condition", "上昇度・厩舎評価", "training_condition", "KYI", "improvement_code@92:1;stable_evaluation_code@156:1", "derived", "KYI code decode", "horses[].condition.improvement,horses[].condition.stable_evaluation", True, "DERIVED_VISIBLE", "質的コンディション評価。", "training.summary;stable_index"),
    ("horse.training_index", "調教指数", "training_condition", "KYI", "training_index@145:5", "raw", "KYI parser numeric field", "horses[].training.summary.training_index", True, "CURRENT_VISIBLE", "CYB側training_indexとは別レコード由来。", "CYB training_index;CHA clock_index.total"),
    ("horse.training_arrow", "調教矢印", "training_condition", "KYI", "training_arrow_code@155:1", "derived", "KYI code decode", "horses[].training.summary.training_arrow", True, "DERIVED_VISIBLE", "方向を表すカテゴリ。", "condition.improvement;CYB condition_change"),
    ("horse.workout", "直前追切時計/指数", "training_condition", "CHA", "clock@29:3,32:3,35:3;clock_index@38:3,41:3,44:3,47:3", "derived", "CHA parser converts tenths and grouped indices", "horses[].training.main_workout.{clock,clock_index}", True, "DERIVED_VISIBLE", "1件の追切。総合・区間時計と指数は関連するが同一でない。", "KYI training_index;CYB training_index"),
    ("horse.workout_context", "追切コース/負荷/併せ", "training_condition", "CHA", "course@22:2;strength@24:1;state@25:2;rider@27:1;furlongs@28:1;pair@50:5", "derived", "CHA code decode", "horses[].training.main_workout.{course,strength,state,rider_type,furlongs,pair}", True, "DERIVED_VISIBLE", "追切条件と併せ馬情報。", "CYB course_counts;training_index"),
    ("horse.training_analysis", "調教分析/馬場別本数", "training_condition", "CYB", "course_counts@14..27;training_index@30:3;condition_index@33:3;comment@38:40", "derived", "CYB fields normalized into training_analysis", "horses[].training.analysis", True, "DERIVED_VISIBLE", "本数・指数・コメントを持つ別評価系。condition_changeは現実装で常にnull。", "KYI training_index;CHA clock_index;stable_index"),
    ("horse.jockey_trainer_identity", "騎手・調教師", "jockey_trainer", "KYI", "jockey@172:12;trainer@188:12;trainer_base@200:4", "raw", "KYI fixed-width text fields", "horses[].basic.{jockey,trainer,trainer_base}", True, "CURRENT_VISIBLE", "識別情報。独立した実績集計ではない。", "jockey_index;stable_index"),
    ("horse.market_opening", "基準オッズ/人気", "market", "KYI", "base_win_odds@96:5;base_win_rank@101:2;base_place_odds@103:5;base_place_rank@108:2", "raw", "KYI parser numeric fields", "horses[].market.*", False, "CURRENT_HIDDEN", "DAY PREPでは存在、v0.4.6 clean input bindingで除去。", "final market (not in clean input)"),
    ("horse.jrdb_marks", "JRDB印", "jrdb_composite", "KYI", "marks@327:1..333:1", "derived", "KYI code decode", "horses[].jrdb_ratings.marks", True, "DERIVED_VISIBLE", "指数ごとの印カテゴリ。名称と原指数は併存。", "total_index;idm;info_index;jockey_index;stable_index;training_index;longshot_index"),
    ("horse.farm", "外厩名/評価", "training_condition", "KYI", "farm_name@573:50;farm_rank@623:1;farm_index_rank@624:1", "raw", "KYI parser fields", "horses[].condition.farm", True, "CURRENT_VISIBLE", "外厩情報。", "stable_index;training_analysis"),
    ("horse.past_performance", "直近5走の成績/走破内容", "ability_performance", "ZED", "time@144:4;idm@183:3;metrics@186..239;corners@309..315;3F@259,262", "derived", "KYI previous keys join to strictly prior ZED; Normalizer.history", "horses[].recent_runs[].{result,performance,jrdb_metrics}", True, "DERIVED_VISIBLE", "過去走から構成され対象日以降は除外。レース後の評価値群を含む。", "KYI idm;pace indices"),
    ("horse.past_notes", "過去走特記事項/馬体", "ability_performance", "ZKB", "tokki@27..44;equipment@45..68;leg@69..113;comments@114..273", "derived", "KYI previous result keys join to ZKB", "horses[].recent_runs[].notes,horses[].recent_runs[].body", True, "DERIVED_VISIBLE", "過去走の観察コメント・装備・脚元。", "horse_traits;current condition"),
    ("horse.recent_runs", "直近履歴接続", "ability_performance", "KYI", "previous[5]@204..323", "derived", "KYI explicit previous keys join PACI ZED/ZKB", "horses[].recent_runs", True, "DERIVED_VISIBLE", "最大5走、キー照合、target date strictly earlier。", "Analysis older_runs"),
    ("horse.history_profile", "通算/条件別成績", "analysis_history", "Analysis Lite", "fact_entry_result_lite(horse_id,race_date,finish,track_type,distance,venue_code)", "derived", "racenote_history_enrichment query_summary; as-of-exclusive", "horses[].historical_profile", True, "DERIVED_VISIBLE", "出走・勝利・3着内と率/標本帯。", "recent_runs;pedigree_context"),
    ("horse.older_runs", "古い過去走", "analysis_history", "Analysis Lite", "fact_entry_result_lite fields in racenote_analysis_backend.TARGET_COLUMNS", "derived", "racenote_history_enrichment: up to 3 strictly older than PACI recent runs", "horses[].older_runs", True, "DERIVED_VISIBLE", "直近PACI履歴より古い最大3件。", "recent_runs;historical_profile"),
    ("horse.pedigree_identity", "血統識別", "pedigree", "Analysis Lite", "horse_id,sire_name,dam_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code", "derived", "approved pre-race Analysis identity projection", "horses[].pedigree", True, "DERIVED_VISIBLE", "結果値は露出しない識別情報。部分欠損あり。", "pedigree_context"),
    ("horse.pedigree_context", "父/母父条件別成績", "pedigree", "Analysis Lite", "horse_id + sire_name/broodmare_sire_name; historical facts", "derived", "racenote_history_enrichment pedigree context; as-of-exclusive", "horses[].pedigree_context", True, "DERIVED_VISIBLE", "血統軸の条件別集計。スコア化なし、小標本を保持。", "historical_profile;distance_fit"),
    ("race.trends", "枠/脚質等レース傾向", "analysis_history", "Analysis Lite", "fact_entry_result_lite historical rows", "derived", "racenote_trend_aggregator / build_racenote_v1", "race.race_trends", True, "DERIVED_VISIBLE", "過去集計（starts/wins/top3/rates/sample band）。", "horse.history_profile;running_style"),
    ("field.context", "出走馬比較文脈", "suitability_context", "KYI + Analysis", "current runners + historical facts", "derived", "RaceNote field-context builder", "field_context", True, "UNKNOWN_LINEAGE", "正確な集約/フィールド一覧の系譜は builder 定義照合を要する。", "race.trends;historical_profile"),
    ("paci.extra_records", "PACI追加レコード", "paci_extension", "PACI", "CHA/CYB/ZED/ZKB and optional records", "derived", "parser/joins vary by record family", "some under training/recent_runs; others absent", True, "UNKNOWN_LINEAGE", "PACIの全レコード種別とRaceNote出力対応は個別に照合が必要。", "recent_runs;training"),
    ("analysis.unused_columns", "Analysis Lite非Reader列", "analysis_history", "Analysis Lite", "meeting_no,meeting_day,race_name,course_code,age,sex_code,sire_line_code,broodmare_sire_line_code,prev_result_key_1,prev_race_key_1", "raw", "Analysis Lite schema v1.4", "none in historical_profile summary", False, "CURRENT_HIDDEN", "Analysisテーブルにはあるが、このreader出力パスで特徴値としては未表示。", "race identity;pedigree identity"),
]


def paths(value: Any, prefix: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            p = f"{prefix}.{key}" if prefix else key
            result.add(p)
            result.update(paths(child, p))
    elif isinstance(value, list):
        for child in value:
            result.update(paths(child, prefix + "[]"))
    return result


def inventory() -> list[dict[str, Any]]:
    witness = json.loads(WITNESS.read_text(encoding="utf-8"))
    # v0.4.6 consumes the immutable market-stripped projection produced by
    # racenote_prepare_forecast_input.bind; derive that surface from the
    # checked-in pre-bind witness, matching the production omission operation.
    witness.get("race", {}).pop("market", None)
    for horse in witness.get("horses", []):
        horse.pop("market", None)
    witness_paths = paths(witness)
    output = []
    for row in ROWS:
        (field_id, name, category, record, source_field, raw_derived,
         derivation, exposure, clean_visible, status, notes, overlap) = row
        # Exposure is based on stable documented path families in the committed
        # witness; normalize [] notation against observed object paths.
        expected = {part.strip() for part in exposure.split(",")}
        present = any(
            path in witness_paths or ("{" in path and any(p.startswith(path.split("{", 1)[0]) for p in witness_paths))
            for path in expected
        )
        if status == "UNKNOWN_LINEAGE":
            pass
        elif not clean_visible and present:
            raise ValueError(f"clean Reader unexpectedly contains hidden field {field_id}")
        elif clean_visible and not present and status not in {"LEGACY_ONLY", "UNKNOWN_LINEAGE"}:
            raise ValueError(f"expected Reader path absent from witness: {field_id} ({exposure})")
        output.append({
            "field_id": field_id, "display_name": name.strip(), "category": category,
            "source_record": record, "source_field": source_field,
            "raw_or_derived": raw_derived, "derivation_source": derivation,
            "current_racenote_exposure": exposure,
            "current_reader_exposure": exposure if clean_visible or present else "DAY PREP only / excluded from clean Reader",
            "current_v046_visible": bool(clean_visible and present),
            "lineage_status": status, "semantic_notes": notes,
            "overlap_candidates": overlap.split(";") if overlap else [],
            "witness_path_present": present,
            "evidence_witness": str(WITNESS.relative_to(ROOT)).replace("\\", "/"),
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=JRDB / "docs/racenote/research-work/feature_inventory_stage_a.json")
    args = parser.parse_args()
    rows = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"inventory_version": "stage-a-1", "generated_from": [
        "horse-racing/jrdb/src/racenote_jrdb.py", "horse-racing/jrdb/src/racenote_analysis_backend.py",
        "horse-racing/jrdb/src/racenote_history_enrichment.py", "horse-racing/jrdb/schema/jrdb_analysis_schema_v1_4.sql",
        str(WITNESS.relative_to(ROOT)).replace("\\", "/")], "fields": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = collections.Counter(r["lineage_status"] for r in rows)
    categories = collections.Counter(r["category"] for r in rows)
    print(json.dumps({"inventory": str(args.output), "fields": len(rows), "by_status": counts, "by_category": categories}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
