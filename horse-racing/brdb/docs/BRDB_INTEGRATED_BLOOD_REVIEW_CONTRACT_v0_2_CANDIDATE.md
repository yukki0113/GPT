# BRDB ⑤ 統合血統レビュー出力契約 v0.2 — candidate

Status: **RESEARCH DESIGN CONTRACT / NOT IMPLEMENTED / NOT PRODUCTION AUTHORIZED**
Date: 2026-11-05
Contract ID: `brdb-integrated-blood-review-v0.2-candidate`
Machine-readable sample/schema: `schema/brdb_integrated_review_v0_2_candidate.schema.json`
Related: `BRDB_REVIEW_CONTRACT_v0_1.md` (FROZEN, unchanged), `BRDB_SIRE_BMS_EVIDENCE_V01_REAL_RACE_20261105.md`

## 1. 目的・責務

**PACIから任意の1レース全出走馬を受け取り、①父産駒、②母父、③父系×母父系の組合せ、④兄姉・近親という血統根拠を、⑤が出典・条件・母数・不確実性を保持して解釈・統合する。**

BRDB側が血統条件適性について「好材料・懸念・判断保留」の説明と根拠参照を提供し、RaceNoteはその結果を他要素と統合して予想する。RaceNoteに①〜④の統計の**再集計を要求しない**。BRDBは予想勝率、着順、買い目、印を生成しない。**全出走馬比較アルゴリズムと順位付けは未確定で本candidate対象外。**

## 2. 現在の境界

- ①②の履歴統計取得は `src/run_brdb_sire_bms_evidence.py` v0.2 で研究用実装済み。③④は未実装。
- この文書は⑤の**出力項目・意味・未実装時の表現**を固定するだけで、⑤の判断ロジック自体は**未実装**。本番の `brdb-review-v0.1`、BRDB CURRENT、RaceNote、PWA、Newspaperは一切変更しない。
- 事実（pedigree facts）、履歴観測（evidence）、解釈（factors）、予想（RaceNote側）は明確に分離。

## 3. 入力／race-level出力

一つの対象レースについて、canonical `race_key`、`target_date`、`venue_code`、`surface_code`（芝=1/ダート=2）、`distance_m`、`course_code`、`field_size` を保持。

出力トップレベル：
- `contract_version`: `brdb-integrated-blood-review-v0.2-candidate`
- `release_status`: `RESEARCH_CANDIDATE`
- `race`: 対象条件と出走登録頭数
- `as_of_exclusive`: 対象日。全履歴出走の `race_date < target_date` を強制
- `source_generations`: `brdb`, `jrdb_analysis`, `paci`。未使用・未解決はnull。
- `horses`: 出走登録全馬分を馬番順、1馬1件で返す
- `aggregate_coverage`: `field_size`, `reviewed_horses`。一致しない場合は完了扱いしない

馬は `horse_id`（JRDB血統登録番号）で厳密に識別し、馬名によるfallbackは**禁止**。実行時には同一馬ID・馬番の重複、登録頭数と配列件数、as-ofと血統profile日付を検証する。対象日後の結果・後日判明した情報を遡及投入しない。

## 4. 馬単位の返却項目

| 項目 | 内容 | 未実装／根拠不足 |
|---|---|---|
| `horse_id`, `horse_no`, `horse_name` | ID、馬番、表示馬名 | 名前はnull可。IDは必須 |
| `status` | `AVAILABLE`, `PARTIAL`, `INSUFFICIENT_EVIDENCE`, `NO_PEDIGREE`, `AS_OF_UNVERIFIED` | 推測補完禁止 |
| `pedigree_facts` | 父・母・母父と公式父系/母父系コード | 欠損値null |
| `components` | `sire`, `broodmare_sire`, `pairing`, `relatives` | **4枠必須**。availability + evidence_ids |
| `evidence` | 元条件・走数・一意馬数・基準値・率・区間・source・as-of | 根拠がなければ [] |
| `factors` | `positive`, `negative`, `unknown` | 判断ロジック未実装なら3配列とも [] |
| `summary` | ①〜④を解釈した血統面の短評 | 判断ロジック未実装ならnull |
| `coverage` | 4項目の入力利用状況 | ③④はNOT_IMPLEMENTED |
| `confidence` | `UNASSESSED`, `DESCRIPTIVE_ONLY`, `LIMITED`, `SUPPORTED` | 判断ロジック未実装ならUNASSESSED |

`components` および `coverage` の状態は `AVAILABLE`, `LOW_SAMPLE`, `NO_SAMPLE`, `NOT_IMPLEMENTED`, `SOURCE_UNAVAILABLE`, `AS_OF_UNVERIFIED`。**未実装・データ未取得・0走・少数例を混同しない**。母父だけ情報が豊富でも、父の `NO_SAMPLE` / `LOW_SAMPLE` はそのまま残す。

## 5. 根拠 evidence の最小契約

個々の根拠には `evidence_id`（同一馬で一意）、`component`、`evidence_kind`、`scope_key`、`condition`、`observations`、`sample_status`、`as_of_exclusive`、`source_generation`、`source_name`、`overlap_group` を持たせる。

- `evidence_kind`: `OBSERVED_CONDITIONAL_RESULT` / `PEDIGREE_FACT` / `REVIEWED_TAXONOMY`。血統事実と適性仮説を同一視しない。
- `observations`: `unique_horses`, `starts`, `wins`, `top3`, `win_rate`, `top3_rate`, `top3_wilson95`, `baseline_starts`, `baseline_top3_rate`, `top3_delta_pp`。件数0で率・区間はnull、0%と偽装しない。実績以外の根拠ではobservations=null可。
- `sample_status`: `DESCRIPTIVE` / `LOW_SAMPLE` / `NO_SAMPLE` / `NOT_APPLICABLE`。DESCRIPTIVEは**件数区分のみ**、好材料の認定ではない。
- `overlap_group` は根拠が同じ出走母集団を共有する可能性の追跡に用いる任意タグ。nullは独立を保証しない。
- 出所・集計期間・各条件・一意馬数・区間を明示し、集計の一部を表示側で再計算させない。
- ①父の5階層：`VENUE_COURSE_EXACT` → `VENUE_DISTANCE` → `VENUE_BAND` → `ALL_VENUES_DISTANCE` → `ALL_VENUES_BAND`。**すべて対象と同じ芝ダ**。上位条件の欠損を下位条件で代入せず、5件を別根拠で返す。`best_supported_scope` は廃止済み。
- ②母父は芝/ダート各々、および各芝ダ×距離帯を個別に返す。②の別芝ダ集計は①の父適性を補完するものではない。

## 6. 要因 factors と禁止事項

各factorは `factor_id`、`direction`（POSITIVE/NEGATIVE/UNKNOWN）、`statement`、`evidence_ids`、`interpretation_status` の組。根拠IDは同一馬evidenceへの参照に限定し、未知要因だけは空参照も可（③未実装など）。

`interpretation_status` = `OBSERVATION_ONLY` / `HYPOTHESIS_NOT_VALIDATED` / `VALIDATED_CONDITION_TREND` / `INSUFFICIENT_EVIDENCE`。

- **正負の判断規則・統計閾値・文章生成は今回作らない。** したがって現段階ではfactor配列は空、summary=null、confidence=UNASSESSED。
- 予想勝率、数値スコア、印、順位を付けない。
- 父系の近さを理由に異なる種牡馬の成績を合算しない。③④を実装しても①の欠損を帳消しにしない。
- 父/BMS/配合/近親は歴史的な同一出走を共有し得る。**根拠数だけで独立性や確信度を水増ししない**。
- `NOT_IMPLEMENTED` や `NO_SAMPLE` は血統面のマイナス要因ではない。

## 7. 将来の受入条件

1. PACIの全馬/馬番/ID/血統事実が正しく揃い、出走登録全頭を1件ずつ返す。
2. ①の5階層と芝ダ固定、②の芝ダ×距離帯、期間・as-ofが source と一致する。
3. ③④は未実装なら `NOT_IMPLEMENTED` とし、0走や根拠不足と区別。
4. evidence_idの存在・一意性・要因参照・区間・出典と、母数0のnullを自動テスト。
5. 決定的JSON、単馬/全馬での意味の一致を検証。
6. ③④の仕様/成果を確認してから統合判定の具体的な規則を追加し、予想への重みはRaceNote側で決定。
7. 実データ再演・速度計測・利用文言の確認、ユーザーによる採用承認が完了するまで現行v0.1と本番は変更しない。

この仕様は**⑤の出力契約のみ**。モデルやReview本体の開発完了を意味しない。
