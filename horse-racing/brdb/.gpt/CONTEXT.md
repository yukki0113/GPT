# BRDB project context

## Mission (updated 2026-11-20)

BRDB は RaceNote の**過去走中心の評価を補完する独立した血統evidence lane**である。目的は既走馬の条件変化・血統/配合/近親を別視点から評価する材料を増やすこと、および**新馬戦・未出走馬**において過去走がないために従来Zとして扱っていた領域を研究することである。

馬の能力・人気・馬券妙味に関する優位性は未実証。単純な加点や「血統が良いから買い」は禁止する。騎手プロファイルDBも将来の独立evidence laneであり、統合・印・自信度・オッズ比較はRaceNoteの責務とする。

**基本設計・ゲート正本**: `docs/BRDB_BASIC_DESIGN_AND_RESEARCH_POLICY_20261120.md`。旧計画のPhase表よりこの文書の目的・研究順序を優先する。

## Current status / boundaries

- Phase 1 CURRENT / Reader 実装済み。固定 `brdb-review-v0.1` と read-only consumer contractは維持。
- ①父・②母父・③配合・④近親、D3/D4、M7 全頭研究候補、馬場横断研究 v0.6 等は段階ごとに受入範囲と未検証要件が異なる。README/個別監査資料に基づき評価し、完了を一括宣言しない。
- M6予測価値ゲート #2395 はOPEN/BLOCKED。M7 consumer/production #2628 はOPEN。Draft #2655 はresearch-only、Draft #2643は血統表示候補である。
- `AS_OF_UNVERIFIED`、`prediction_safe=false`、`production_authorized=false` の研究結果を、RaceNote予想・CURRENT・Newspaper/PWA本番へ移さない。
- 新馬戦の専用特徴量・初出走母集団・実証評価は**これからの開発目標**であって実装済みではない。
- private M7 horse-level recordsはpublic Git/Issues/CI artifactsへ出さない。

## Durable principles

1. Canonical identity はJRDB 8桁 `horse_id`。対象fieldは `race_key` と `horse_no` も厳格照合。馬名fallback・推測ID禁止。
2. 事実、歴史成績、説明的な相関、未検証仮説、予測的結論を分離し、provenance/coverage/as-of/uncertaintyを保持する。
3. 対象レース**全頭**を契約の基本とする。RaceNoteの既存選抜馬・市場人気で絞らない。
4. `NO_SAMPLE` / `LOW_SAMPLE` / `SOURCE_UNAVAILABLE` / `AS_OF_UNVERIFIED` を欠陥隠蔽や0点に使わない。
5. 父/母父/配合/近親は比較母集団や重複を保持する。5つの包含関係にあるスコープを合算しない。
6. 現在の祖先関係を過去時点へ遡及しない。歴史時点の特徴量・分類・結果の可用性は独立検証を要する。
7. 新馬戦では一般の産駒勝率を初戦適性に読み替えず、レース区分と個体初出走を区別する。
8. BRDB/騎手DB/過去走のスコアを単純加算しない。統合は分離された研究検証の後。
9. BRDBは予想印、順位、確率、RaceNote自信度を生成しない。PWAは表示surfaceであり血統ロジック正本ではない。
10. JRDB既存parserと共通 `tools/data-storage/` を再実装しない。consumerはParquetを直接joinせずReader/contract経由。
11. research→prediction→productionは別ゲート。凍結契約を暗黙変更せず、独立の時系列検証・consumer regression・明示承認が必要。
12. GitHubの最新 `main` を仕様正本とし、Drive等のprivateデータとは責務を分離する。

## Existing baseline and legacy detail

- Initial immutable pedigree generation `eeca93556584a5b8`; stable Drive CURRENT `BloodReviewDB_CURRENT.zip` (既存運用条件維持)。
- RRDB inheritance: `docs/BRDB_RRDB_INHERITANCE_v0_1.md`。
- JRDB UKC: horse_id、sire/dam/BMS name + years、父系/母父系コード。RaceNoteにはpedigree identity/P2 historical contextがある。
- ステータスの正式証跡: `docs/BRDB_MILESTONE_RECONCILIATION_20261116.md`（追記含む）および関連PR/Issue。過去値は変更しない。
