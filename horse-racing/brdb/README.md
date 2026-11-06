# Blood Review DB (BRDB)

BRDB は、出走馬の血統を固定条件への一致抽出ではなく、**対象レースの各出走馬を同一契約でレビューする**ための中央競馬サブプロジェクトです。

## Source of truth

GitHub `yukki0113/GPT` の `main` 配下 `horse-racing/brdb/` を、BRDB の仕様・source・tests・運用書の正本とします。

血統の一次事実については既存 JRDB 資産を優先し、JRDB で不足する祖先・系譜情報だけを明示的な外部 source で補完します。BRDB は JRDB fixed-width parser を再実装しません。

## Purpose

BRDB の中心責務は次の2層です。

1. **Blood data layer**
   - 父、母、母父
   - 父系・母父系
   - 将来の3〜5代血統、クロス、地域型、類似血統等
   - 各分類の provenance / version

2. **Blood Review layer**
   - 対象レース・対象馬に対する決定的レビュー
   - review result、根拠、coverage、confidence を返す
   - PWA / RaceNote は内部 Parquet や研究ロジックを直接読まず、Review contract を読む

固定条件で「該当馬だけを抽出する」ことを主目的にしません。原則として target field の全馬を review 対象とします。

## Initial architecture

```text
JRDB / external pedigree source
        |
        v
Blood canonical data
        |
        v
Blood Review engine
        |
        v
BRDB CURRENT
        |
        v
BRDB Reader
        |
        +--> horse_id query
        |      -> review result only
        |
        +--> RaceNote / PWA
```

## RRDB inheritance

BRDB は RaceReviewDB (RRDB) の以下の成熟した consumer boundary を引き継ぎます。

- stable CURRENT artifact
- `current.json` + validated manifest
- immutable Parquet relations
- JRDB blood registration number (`horse_id`) を stable identity とする
- horse-name fallback 禁止
- DuckDB read-only query
- Reader が storage detail を隠蔽
- consumer は review result contract のみ利用
- provenance / generation / schema / logic version を必ず保持
- fail-closed

詳細は `docs/BRDB_RRDB_INHERITANCE_v0_1.md`。

## Current status

Status: **PHASE 1 COMPLETE / CURRENT READER OPERATIONAL FOUNDATION**

血統採点ロジックはまだ未実装ですが、Pedigree Fact v0.1、guarded parent-relation resolver、CURRENT pointer contract、read-only BloodReviewReader、deterministic CURRENT bundle builder まで実装済みです。

初期フェーズでは、

1. JRDB UKC / RaceNote pedigree 資産の棚卸し — 完了
2. canonical pedigree fact schema — v0.1 実装済み
3. guarded parent relation resolver — v0.1 実装済み
4. official lineage code master materialization
5. reviewed pedigree-name alias v0.1
6. UKC -> pedigree_fact generation builder
7. regional-type taxonomy
8. horse review contract
9. CURRENT / Reader 実装
10. PWA「血統詳細」modal contract

の順に進めます。

## Existing JRDB assets already confirmed

現行 JRDB には少なくとも次が存在します。

- UKC:
  - `horse_id`
  - `sire_name`
  - `dam_name`
  - `broodmare_sire_name`
  - `sire_line_code`
  - `broodmare_sire_line_code`
- RaceNote pedigree enrichment:
  - pedigree identity
  - sire / broodmare-sire historical context

BRDB はこれらを再取得・再実装せず、利用可能性と coverage を確認して再利用します。

## Bootstrap

新しい Chat / Work / Codex 作業では次を確認します。

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. `horse-racing/brdb/README.md`
3. `.gpt/CONTEXT.md`
4. `.gpt/WORKFLOW.md`
5. `docs/BRDB_RRDB_INHERITANCE_v0_1.md`
6. 対象 task の current source / tests / contract
7. JRDB を読む場合は `horse-racing/jrdb/` の current docs/source
8. Parquet / DuckDB を扱う場合は `tools/data-storage/`

過去 chat の説明だけを current truth とせず、latest `main` を優先します。


## Phase 1 implementation

- `schema/brdb_pedigree_fact_schema_v0_1.sql`
- `src/brdb_parent_relation.py`
- `tests/test_brdb_parent_relation.py`
- `docs/BRDB_PEDIGREE_FACT_SCHEMA_v0_1.md`
- `docs/BRDB_UKC_PARENT_KEY_JOIN_VALIDATION_20261021.md`
- `docs/BRDB_UKC_DAM_BMS_INCONSISTENCY_AUDIT_20261021.md`

Parent name + birth year is treated as a candidate key only. Canonical relation resolution requires independent lineage/pedigree guards and fails closed on conflict.

## Pedigree generation v0.1

The generation builder and guarded resolver are in `src/`. The pedigree tables are defined by `schema/brdb_pedigree_fact_schema_v0_1.sql`. The manifest contract is documented in `docs/BRDB_PEDIGREE_GENERATION_MANIFEST_v0_1.md` and specified in `schema/brdb_pedigree_generation_manifest_v0_1.schema.json`.

The immutable Parquet generation, manifest, and audit are stored outside Git. This foundation does not publish a production `CURRENT` pointer or change PWA/RaceNote serving.
\n\n## CURRENT / Reader v0.1\n\n- `src/brdb_pedigree_reader.py`\n- `src/build_brdb_current_bundle.py`\n- `schema/brdb_current_pointer_v0_1.schema.json`\n- `docs/BRDB_CURRENT_READER_CONTRACT_v0_1.md`\n- `tests/test_brdb_pedigree_reader.py`\n\nConsumer identity remains `horse_id` only; horse-name fallback is prohibited. The first immutable generation remains `eeca93556584a5b8`. Stable Drive CURRENT is published as `BloodReviewDB_CURRENT.zip`. Operational use resolves a freshly materialized native Drive connector handoff with `src/brdb_current.py` (A02), while the initial pinned SHA manifest remains for explicit historical replay. Native connector access and existing folder permissions are unchanged; see `docs/BRDB_A02_CONNECTOR_HANDOFF_20261102.md`. Phase 2 Blood Review logic is next.\n

## Blood Review v0.1 — non-scoring baseline

- `src/brdb_blood_review.py`\n- `src/brdb_racenote_p2_adapter.py`
- `tests/test_brdb_blood_review.py`\n- `tests/test_brdb_racenote_p2_adapter.py`
- `docs/BRDB_BLOOD_REVIEW_IMPLEMENTATION_v0_1.md`

Status: **VALIDATED / CONTRACT FROZEN**.

Review v0.1 applies the same horse_id + target_context contract to all target horses, reuses only validated pedigree Reader facts and explicitly scoped RaceNote P2 descriptive evidence, and returns status / coverage / provenance. A historical profile with an unverifiable as-of date returns `AS_OF_UNVERIFIED` without pedigree facts or P2. Scoring, regional taxonomy, inferred suitability, and PWA integration remain unimplemented.

The frozen contract is `docs/BRDB_REVIEW_CONTRACT_v0_1.md`. A fixed-input, aggregate-only replay CLI is `src/run_brdb_blood_review_field_replay.py`. Validation used the real 2025-10-26 京都1R authoritative RaceNote bundle: all 9 field records returned, 5 AVAILABLE and 4 AS_OF_UNVERIFIED; batch/single equality passed. See `collab/results/20261022_002_blood-review-v01_verification_result.md` for command, source refs and counts.

## Phase 3 closure — display design only

Status: **DESIGN/HANDOFF CLOSED — RELEASE DEFERRED** (2026-10-22).

`src/brdb_newspaper_handoff.py`, `tests/test_brdb_newspaper_handoff.py`, and `docs/BRDB_RACENOTE_PWA_INTEGRATION_v0_1.md` constitute a design/handoff foundation only. There is **no Newspaper merge, PWA modal, production daily workflow change, Release or Pages deployment** as part of this phase. The PWA is shared with other viewers; user approval of exact display contents and real-device presentation is mandatory before a separately scoped integration/release. Do not auto-publish BRDB into Kenshow_Labo or Momotaro.

## Phase 4 — Ancestor graph / cross / similarity (research only)

Status: **IMPLEMENTED FOUNDATION / COVERAGE VALIDATION PENDING**.

- `src/brdb_ancestor_graph.py`: canonical-ID-only parent graph (depth 1–5), observed cross paths and descriptive shared-ancestor similarity.
- `tests/test_brdb_ancestor_graph.py`: cycle, conflict, duplicate, missing-branch and overlap regression tests (execution pending).
- `docs/BRDB_ANCESTOR_CROSS_SIMILARITY_v0_1.md`: research/coverage/ancestor-source acceptance gates.

Existing pedigree generation and Blood Review v0.1 remain unchanged. No PWA/Newspaper release or inferred score is authorized. Source expansion and 2025 depth 2–5 coverage audit are required before Phase 4 can be called complete.


## 2026-11-05 — ①父産駒・②母父条件別実績（研究用）

- [単一PACIレース実績エンジン](src/run_brdb_sire_bms_evidence.py): PACIの1レースを指定し、父5段階（同場・同芝ダ・同コース/距離 → 同場・同芝ダ・同距離 → **同場・同芝ダ・同距離帯** → 全場・同芝ダ・同距離 → 全場・同芝ダ・同距離帯）と母父の芝ダ別・芝ダ×距離帯の、時点以前の実出走成績を読取専用で取得。**対象馬の芝ダは全5段階で固定。**
- [合成回帰テスト](tests/test_brdb_sire_bms_evidence.py): 取消/中止・対象日以降の結果除外・芝ダ混入拒否・同場距離帯・SHA改ざん等の4テスト。
- [2026-11-01東京5Rの実データ検証](docs/BRDB_SIRE_BMS_EVIDENCE_V01_REAL_RACE_20261105.md): 8/8頭で①②の実成績集計PASS、ウォーム実行約0.5〜0.6秒（元データのダウンロード時間を除く）。**PACI直接CLIの正本Readerを含むE2Eは別途確認要**。
- **適性ラベル確定や⑤全馬評価はまだ未実装**。父の少サンプルを近縁種牡馬の産駒で自動補完しない。母父実績は独立した参考根拠として保持する。各スコープを全て返し、`NO_SAMPLE`/`LOW_SAMPLE` はそのまま報告する。自動的な最良スコープ選択は行わず、予想判断はRaceNoteなどconsumerの責務。③配合・④近親は次段階。
- BRDB CURRENT、Blood Review v0.1、RaceNote、PWAには変更なし。

## 2026-11-05 — ⑤ 統合血統レビュー出力契約 v0.2 candidate

- [統合血統レビュー出力契約 v0.2 candidate](docs/BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md) — **出力仕様のみ確定**。①父/②母父/③配合/④近親の根拠と解釈を⑤が統合してRaceNoteへ渡す。RaceNote側では統計を再集計しない。
- [JSON Schema](schema/brdb_integrated_review_v0_2_candidate.schema.json) / [合成サンプル](tests/fixtures/brdb_integrated_review_v0_2_candidate_example.json) / [契約テスト](tests/test_brdb_integrated_review_contract_v02_candidate.py)。
- ③④が未実装でも明確に `NOT_IMPLEMENTED` と返せる構造。父の `NO_SAMPLE` / `LOW_SAMPLE` は母父や系統によって上書きしない。根拠IDと同一集団の重複可能性を保持する。
- ⑤の**解釈判定規則・根拠の統合・全馬比較・実行APIは未実装**。正負の要因や血統総評を勝手に生成しない。BRDBは予想スコア・印・勝率を出さず、予想上の利用判断はRaceNote側の責務。
- このcandidateは**research-only**であり、現行凍結 `brdb-review-v0.1`、BRDB CURRENT、RaceNote、PWA、新聞の本番連携は変更しない。

## 2026-11-05 — ③ 父系×母父系の組合せ分析（研究用）

- [③系統ペア集計エンジン](src/run_brdb_pairing_evidence.py) / [合成テスト](tests/test_brdb_pairing_evidence.py) / [東京5R・8頭の検証レポート](docs/BRDB_LINEAGE_PAIRING_EVIDENCE_V0_1_20261105.md)。
- ①②の全馬JSONとJRDB Analysis v1.4 CURRENTを受け取り、**父系×母父系の公式コード組合せ**について同場同コース/距離、同場距離、同場距離帯、全場距離、全場距離帯の5段階を対象芝ダ固定で集計。各段階で、組合せ、父系単独、母父系単独、同条件全体の比較値・標本情報を返す。関連系統や母父単独の実績をペアの実績に代入しない。
- 東京5R・8頭は7組合せ。ローカル実測では約0.4〜0.8秒（入力転送なし）。合成テスト5件PASS。
- **歴史UKC系統コードの当時配信時点が未検証**のため、出力は `HISTORICAL_LINEAGE_PROFILE_ASOF_UNVERIFIED` / `prediction_safe=false`。③の履歴成績は記述研究に限り、検証済みニックス・予想傾向として⑤に自動採用しない。[⑤候補契約](docs/BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md) には `AS_OF_UNVERIFIED` として接続する方針。
- 現行Blood Review v0.1、BRDB CURRENT、RaceNote、PWA、新聞の本番変更なし。④兄姉・近親と⑤統合ロジックは未実装。

## 2026-11-05 — ④ 兄姉・母方近親の類似条件実績（研究用）

- [④近親根拠エンジン](src/run_brdb_relatives_evidence.py) / [合成テスト](tests/test_brdb_relatives_evidence.py) / [東京5R実データ検証](docs/BRDB_RELATIVES_EVIDENCE_V0_1_20261105.md)。
- PACI 1レース全出走馬の母を、母名・生年・性別・母父名・公式母父系をguardにしたcanonical IDで同定。BRDBの `parent_relation` の確定IDのみから**母を共有する兄姉・母方のおじ/おば**を取得。全兄姉の認定には父ID一致も必要。馬名だけから親族を断定しない。
- ①と共通の5階層（同場コース/距離、同場距離、同場距離帯、全場距離、全場距離帯）で、**対象と同じ芝ダートのみ**の近親出走・勝ち・3着内数を返す。生年月日とレース日付が対象前、登録プロフィール日付が対象以前の候補のみ。
- 2026-11-01東京5Rでは母canonical ID **6/8頭**、母共有兄姉14頭（全兄姉1頭）、母方のおじ/おば21頭、合計35頭の近親を検出。うち21頭は対象芝中距離帯に少なくとも1走。ローカル検証で約0.65〜0.75秒（Drive転送なし）、合成テスト5件PASS。
- **研究用の歴史関係グラフは当時配信時点の完全再演保証なし**。出力 `prediction_safe=false`、⑤へは `AS_OF_UNVERIFIED`、母未同定は `SOURCE_UNAVAILABLE` として引き継ぐ方針。近親の不在・0走を「適性がない」とは判定しない。いとこ・父方近親・遠縁の完全探索は未実装。
- ④も数値の取得までであり、⑤の総合解釈ロジックは未実装。BRDB CURRENT、Blood Review v0.1、RaceNote、PWAの本番コードは変更なし。

## 2026-11-05 — ⑥ 地域ルーツ・⑦ 内包血統（設計）

- [⑥⑦ 補足レビュー設計 v0.1](docs/BRDB_REGIONAL_ROOTS_EMBEDDED_BLOOD_DESIGN_v0_1_20261105.md)。
- ⑤統合レビューにおける判断優先関係は **①〜③ ＞ ④ ≫ ⑥⑦**。これは加重点数ではなく、主根拠・補強根拠・補足洞察の**解釈と表示順**。
- ⑥: 日本/米国/欧州/南半球を出生国ではなく競馬環境由来の分類候補として扱い、父母双方の確認済み経路と未解決範囲、出典とtaxonomy versionを保持。確認できた一部の祖先だけで「米国色が強い」などと断定しない。
- ⑦: Halo / Storm Cat / トニービン / Danzig等の内包血脈・経路・深さ・観測クロスをcanonical ancestor IDベースで把握し、母父`DS`と遠祖を区別。既存ancestor graphを再利用し、完全に解決されない枝はUNKNOWN。
- Gemini資料は未検証の仮説候補。血脈/地域タグ自体を芝ダ・馬場・コース適性として即時採点しない。条件別の時系列検証がない文は仮説として限定的に記す。
- 将来の⑤には**非採点の`supplemental_insights`**を別契約版で追加する計画。⑥⑦から①〜④の評価・信頼度・結論を自動上書きしない。
- **設計のみ**。⑥⑦の実行エンジン、⑤の統合判断、schema変更、BRDB CURRENT/RaceNote/PWA本番更新は未実施。

## 2026-11-05 — D1 地域・血脈特性の候補辞書

- [D1候補辞書・受入記録](docs/BRDB_D1_TAXONOMY_HYPOTHESES_ACCEPTANCE_20261105.md)。
- [⑥地域ルーツ候補（4分類）](taxonomy/regional_roots_candidate_v0_1.json) / [⑦内包血統・適性仮説（5件）](taxonomy/embedded_blood_hypotheses_candidate_v0_1.json) / [承認ゲート検査](src/brdb_d1_catalog.py) / [合成回帰テスト](tests/test_brdb_d1_catalog.py)。
- **地域の正式対応=0件、実証された適性=0件**。Gemini参考資料からJRDB公式系統コードや祖先IDを推測割当てせず、候補全件を `CANDIDATE` として隔離。⑥⑦の候補は本番の⑤へ加点・自動表示しない。
- ①〜③ ＞ ④ ≫ ⑥⑦は数値の加重係数ではなく、将来の血統レビューの主根拠・補強・補足の優先関係。⑤への接続には独立した `supplemental_insights` 契約の受入を要する。
- D2祖先経路検索、D3条件別成績検証、D4統合レビュー接続、D5時系列検証は**未実施**。旧 `brdb-review-v0.1`、BRDB CURRENT、RaceNote、PWA、新聞は変更なし。

## 2026-11-05 — D2 祖先位置・世代・観測クロス抽出（研究用）

- [D2 祖先位置モジュール](src/brdb_d2_ancestry_positions.py) / [合成回帰テスト（10件）](tests/test_brdb_d2_ancestry_positions.py) / [受入境界と実行例](docs/BRDB_D2_ANCESTRY_POSITIONS_ACCEPTANCE_20261105.md)。
- BRDBの既存`ancestor_graph`と`ancestor_evidence`を再利用し、canonical祖先IDの`S`/`D`経路、世代、父母別coverage、同一IDの複数経路による観測クロスを記述。未解決の枝は`UNKNOWN`で保持し、名寄せ推測をしない。
- D1の地域ルーツ・Halo/Storm Cat/トニービン/Danzig候補は祖先IDの対応が未確認のため、**candidate_bloodline_matchesとregional_root_assignmentsは空**。地域ラベルや適性を自動付与しない。
- 対象日以前のプロフィール日付だけでは、当時の全祖先辺の存在を保証できない。D2は`historical_asof_status=AS_OF_UNVERIFIED`、`prediction_safe=false`に固定し、自己申告の時点検証フラグでも昇格させない。
- GitHub登録と読み戻しは確認。Python回帰テストの実行、実レースE2E、D1候補ID対応レビュー、D3条件別集計は未実施。⑤、BRDB CURRENT、RaceNote、PWAの本番処理は変更なし。

## 2026-11-05 — JRDB公式系統コード実査と⑦血脈・条件候補の再整理

- [系統対応観測辞書（13個別ラベル）](taxonomy/jrdb_lineage_ancestor_observation_candidate_v0_1.json) / [⑦優先6＋次点6の候補・条件辞書](taxonomy/embedded_blood_research_shortlist_candidate_v0_2.json) / [出典・分類境界と検証条件監査](docs/BRDB_D1_D2_ANCESTOR_CODE_RECONCILIATION_AND_HYPOTHESIS_REVIEW_20261105.md)。
- JRDB研究用血統世代`5279af0bd8226cde`の**83件公式系統コード表**をmanifest SHA付きで読み取り、JRDB公開コード表の代表項目と一致。独自の系統体系は作らず、JRDBの大・小系統を継続利用。
- 代表例: Tony Binの父・母父ラベルは1307ゼダーン系に観測、Storm Catは1108ストームバード系、Halo/SSはともに1206ヘイロー系。**系統コードは特定の祖先馬IDとは別**。Sadler's WellsおよびMr. Prospectorの名前に複数コードが観測される例は未解決監査対象。
- 研究用辞書には正式canonical祖先IDを推測入力せず`null`で保持。地域ルーツ4分類と①〜③＞④≫⑥⑦の優先関係は維持。
- 内包血統の候補は12に拡張してレビュー用に整理しただけで、D1正式仮説辞書・⑤のschema・BRDB CURRENT・RaceNote/PWA本番を更新していない。適性は一件も検証済みと認定していない。

## 2026-11-05 — D2 12候補の祖先ID・世代別coverage実測

- [実Parquet監査結果](docs/BRDB_D2_12_ANCESTOR_ID_PATH_COVERAGE_AUDIT_20261105.md)。ローカルの研究用血統世代 `5279af0bd8226cde` をmanifest SHA検証のうえ読取り専用で監査。Work/Codex/Actionsへの実行委譲は不要。
- 2022〜2024生まれの研究マスター12,018頭: 1代前73.09%、2代前46.49%、3代前8.56%、4代前0.10%、5代前0%が正式ID経路で到達可能。各世代の全理論スロットを分母とした**観測可能性**であり、個別血脈の存在率ではない。
- 12候補の個別祖先profileは全てマスターに見つからず、独立したcanonical祖先IDは未確定。正式IDによる候補含有率は「0%」ではなく**測定不能**。母父名完全一致による直接観測は別表で保管。
- 2026-11-01東京5Rの8頭は当該研究世代にhorse_id未収録。最新PACI自体の問題ではなく研究用世代のスコープ外であり、母集団から除いて扱う。
- 次は古い祖先の一意ID対応を独立監査し、当時の公開時点を保証できる範囲でD3の検証軸を選択する。⑥⑦から主評価やPWAへ加点しない。

## 2026-11-05 — 6工程の①「父・母父を中心とした種牡馬特徴マスタ」

- [①設計契約](docs/BRDB_STALLION_FEATURE_MASTER_DESIGN_V0_1_20261105.md) / [研究用候補SQL](schema/brdb_stallion_feature_master_candidate_v0_1.sql)。
- 父・母父を**必須の分析起点**とし、母母を含む遠い母系は取得できた範囲のみ補足（欠損`UNKNOWN`）。種牡馬の祖先経路を出走馬へ展開する際は父側`S+`、母父側`DS+`を使用。
- JRDB大/小系統の公式コードは既存`lineage_code_master`を使用。種牡馬個体とJRDB系統、地域ルーツ、祖先・クロス候補を別表で区分。内部subject keyとJRDB 8桁horse_idを別管理し、馬名推測で個体IDを発行しない。
- マスタ結合はBRDB研究用世代の**生成時のみ**。RaceNote/PWAは完成した⑤レビューのみ参照。
- ②12候補の登録 → ③既存BRDB結合 → ④母母ラインの任意補完 → ⑤D3条件実績検証 → ⑥D4補足コメント接続の順で進める。
- 今回は**①の設計・SQL候補のみ**。既存CURRENT、凍結Review v0.1、⑤schema、RaceNote、PWA、本番workflowのデータ/処理は変更していない。

## 2026-11-05 — 6工程② 12種牡馬の外部ID・祖先経路登録

- [工程②の登録監査・進捗](docs/BRDB_STALLION_FEATURE_MASTER_STAGE2_REGISTRATION_20261105.md)。
- [外部個体ID付き12プロフィール・祖先経路JSON](taxonomy/stallion_master_stage2_external_profiles_v0_1.json)、[登録validator](src/brdb_stage2_master_registry.py)、[合成回帰テスト](tests/test_brdb_stage2_master_registry.py)。
- JBIS各馬の**外部個体ID12件**と直接父母名24件・2代前の`SS/SD/DS/DD`名前経路48件を出典URL付きで記録。12候補間の確定した個体ID父系リンクはSunday Silence→Haloの`S` **1件のみ**。
- **JBISのID≠JRDB horse_id**。外部IDを8桁JRDB IDへ流用せず、旧祖先の個体ID一致・観測経路を偽装しない。残る親名・祖父母名は人名として出典にあるが個体ID未確認なので、クロス検出/適性採点に投入しない。
- 地域分類・適性実証・歴史的as-of認証は未実施。研究用D2の入力候補に限定し、①〜③＞④≫⑥⑦、BRDB CURRENT/Review v0.1/RaceNote/PWAの未変更を維持。

## 2026-11-05 — 6工程③ 既存BRDBと種牡馬マスタの父・母父結合（研究用）

- [工程③adapter](src/brdb_stage3_feature_adapter.py) / [10ケース合成テスト](tests/test_brdb_stage3_feature_adapter.py) / [実データ照合率監査](docs/BRDB_STAGE3_STALLION_JOIN_REAL_COVERAGE_20261105.md)。
- 既存pedigree_factの`sire_name, sire_birth_year, sire_line_code`と`broodmare_sire_name, broodmare_sire_birth_year, broodmare_sire_line_code`を厳密に照合し、父`S+`と母父`DS+`の別laneに名前観測経路を展開。ただし、外部IDとJRDB horse_idの承認済みcrosswalkは0なので**正式個体結合は0**、すべて`GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY`または未登録/矛盾。
- 研究用全132,652頭では父proxy2,579件（1.944%）、母父proxy13,533件（10.202%）。2015〜2024生45,428頭では父0件、母父1,765件（3.885%）。2022〜2024生12,018頭では父0件、母父98件（0.815%）。
- 父種牡馬・母父の**現役入口マスタを拡充する必要**があり、古い12血脈は祖先候補であって現役種牡馬マスタ全体ではない。母母`DD`は工程④で任意扱い。
- `prediction_safe=false`、`as_of=AS_OF_UNVERIFIED`、`supplemental_insights=[]`。⑤の主評価・BRDB CURRENT/RaceNote/PWA本番は変更なし。

## 2026-11-05 — ③-A 父・母父登場頻度と種牡馬マスタ登録優先順位

- [実測監査・登録候補の上位30件](docs/BRDB_STAGE3A_SIRE_BMS_REGISTRATION_PRIORITY_20261105.md)。
- BRDB研究用世代`5279af0bd8226cde`の血統収録馬を対象に、2022〜2024年生まれ12,018頭、2020〜2024年21,759頭、2015〜2024年45,428頭で父・母父を頻度集計。
- 近年3年の共通マスタ上位50件で父51.215%・母父41.504%、上位100件で父75.462%・母父58.171%の登場レーンをカバー。**別々の上位ランキングとは値が異なる。**
- ③-Bで共通上位50頭から2〜3世代の登録を始め、100頭へ拡張する案。観測氏名＋生年＋JRDB系統コードは未承認の個体キーであり、JRDB⇔外部ID同一性や適性評価を確定しない。
- ③-Aは観測・計画のみ。現行BRDB、RaceNote、PWA等の本番変更なし。

## 2026-11-05 — ③-B 共通上位50頭の祖先ネットワーク初回整備

- [③-B実測・残件優先順位の監査](docs/BRDB_STAGE3B_TOP50_PEDIGREE_ENRICHMENT_20261105.md) / [再現用研究builder](src/brdb_stage3b_top50_builder.py) / [海外種牡馬13頭のJBIS出典付き2世代辞書](taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json)。
- ③-Aの2022〜2024生まれ血統マスター上位50頭を入力。JRDB個別プロフィール37頭、JBIS個別プロフィール13頭を確認。父母の名前100/100枠、2代前の名前147/200枠、3代前の名前20/400枠まで記録。**これらは祖先の正式個体IDによる確定経路数ではない**。
- JRDBの正式祖先IDまで到達したのは1代36/100枠、2代10/200枠、3代0/400枠。person-IDの根拠がない枝を推測接続せず、祖先名前・観測生年単位で148件の調査台帳を生成した。
- 先に解くべき共通祖先はSunday Silence、ウインドインハーヘア、Kingmambo等（出現枠数を基準とした**上限影響度**で順位付け）。名前観測≠祖先の本人ID/クロス確定。
- GitHub上の再現モジュールは登録済み。ローカルの分析スクリプトで実Parquetに対する再実行・SHA一致を検証。ただしコミット済みモジュールそのもののCI/E2E実行は未実施。
- ③-Bの**初回登録バッチは作成**したが、3代の完全接続は残作業。地域型と競走条件適性の自動付与なし。BRDB CURRENT、RaceNote、PWA、本番処理は未変更。

## 2026-11-06 — ③-B継続：4共通祖先の外部個体・子孫経路照合

- [4祖先・12経路の個別照合監査](docs/BRDB_STAGE3B_PRIORITY_ANCESTOR_BRIDGE_AUDIT_20261106.md) / [出典別レジストリ v0.2](taxonomy/stage3b_priority4_bridge_candidate_v0_2.json) / [研究用経路照合モジュール](src/brdb_stage3b_priority_bridge.py) / [合成安全テスト](tests/test_brdb_stage3b_priority_bridge.py)。
- 優先4祖先（サンデーサイレンス、ウインドインハーヘア、キングマンボ、マンファス）の名前観測は上位50頭中31種牡馬・48経路。**7種牡馬のJBIS個体血統ページと4祖先のJBIS個体ページを突合した12経路**は出典裏付けを追加、残り36経路は個別監査待ち。
- JBIS source-native 10桁IDはJRDB 8桁IDではない。**正式JRDB個体祖先IDの追加確定0、JRDB⇔JBIS本人crosswalkの承認0**。父・母父マスタの正式ID解決率は今回不変で、外部出典の確証度を増やす作業。
- `AS_OF_UNVERIFIED`、`prediction_safe=false`、⑥⑦の適性・地域型の自動採点なし。BRDB CURRENT/Review v0.1/RaceNote/PWA等の本番未変更。

## 2026-11-06 — ③-B 続報：優先4祖先・48経路の外部血統出典照合

- [48/48の外部資料照合監査](docs/BRDB_STAGE3B_PRIORITY4_SOURCE_COVERAGE_COMPLETE_20261106.md) / [外部血統位置マスタ候補 v0.4](taxonomy/stage3b_priority4_bridge_candidate_v0_4.json) / [検証モジュール](src/brdb_stage3b_priority_bridge.py) / [合成回帰テスト10件](tests/test_brdb_stage3b_priority_bridge.py)。
- ③-B研究用上位50頭のうち31頭に登場する優先4祖先（Sunday Silence、Wind in Her Hair、Kingmambo、Manfath）の**名前経路48/48にJBIS個別馬血統資料を紐付け**。旧12件＋新36件（うち最終5件は5代血統表で直接確認）。
- これは**出典付き名前経路の資料確認率**。JRDB⇔JBIS本人crosswalk承認0件・JRDB canonical祖先ID追加0件であり、ID系統グラフの到達率は不変（1代36/100、2代10/200、3代0/400）。
- ローカルの独立スロット監査で48枠の既存位置・馬名との整合を確認。コミット済みvalidatorのPython unittest/E2Eは未実行のためPASS表記しない。予想時点のas-ofも未証明、⑤の適性採点/BRDB CURRENT/RaceNote/PWAには接続なし。

## 2026-11-06 — ③-B 個体同定クロスウォークと26経路ハイブリッド伝播

- [研究用の多項目同定・共有経路の監査レポート](docs/BRDB_STAGE3B_JRDB_JBIS_CROSSWALK_AND_HYBRID_PATH_AUDIT_20261106.md) / [JRDB↔JBIS identity crosswalk 2件](taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json) / [照合ガード](src/brdb_stage3b_identity_crosswalk.py) / [DuckDB read-only audit runner](src/run_brdb_stage3b_crosswalk_audit.py) / [ハイブリッド祖先経路伝播](src/brdb_stage3b_hybrid_propagation.py)。
- 研究世代の実Parquetから、ディープインパクト（JRDB `02100816` ↔ JBIS `0000742976`）、キングカメハメハ（JRDB `01103460` ↔ JBIS `0000729458`）について、完全な生年月日・性別・父母名と父母生年等を複数ガードで照合し、JRAも外部確認出典として記録。
- 子孫本人2件の外部同定により、上位50研究マスタの**直接4経路＋JRDB解決済み中間個体を介した22経路＝26/48経路**を source-qualified hybrid path としてローカル検証。13種牡馬に伝播。残り22/48は中間個体同定が不足。**正式JRDB祖先IDは増えていない**（0）、JRDB canonical 1～3代経路充足率も変わらない。
- [クロスウォーク回帰テスト11件](tests/test_brdb_stage3b_identity_crosswalk.py)、[ハイブリッド経路回帰テスト6件](tests/test_brdb_stage3b_hybrid_propagation.py)を登録。実Parquet SHA・2プロフィール8項目・既存50マスタの26経路は独立ローカル実証済みだが、コミット済みPython回帰テストとrunnerの実行は未実施。
- 本人同定を他の29種牡馬に自動拡大しない。外部IDは`JBIS:`のまま保持し、過去時点AS_OF未検証、`prediction_safe=false`。BRDB CURRENT/Review/RaceNote/PWA/新聞には接続しない。

## 2026-11-06 — ③-B 第2回：JRDB⇔JBISの5個体対応と29/48経路

- [③-B第2回個体対応監査](docs/BRDB_STAGE3B_IDENTITY_CROSSWALK_BATCH2_20261106.md) / [研究用5個体crosswalk v0.2](taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_2.json) / [5個体・既存48経路の照合モジュール](src/brdb_stage3b_crosswalk_batch2_audit.py) / [DuckDB実Parquet再実行入口](src/run_brdb_stage3b_batch2_from_parquet.py)。
- 既存のDeep Impact、King Kamehamehaに加え、**ダイワメジャー、ハーツクライ、エピファネイア**のJRDB個体IDとJBIS個体IDを、実Parquet氏名・完全生年月日・性別・父母・公式系統コードと公開一次資料を照合して研究用に登録（2→5件）。
- 優先4祖先の既存48名前経路のうち、**前26＋今回3＝29経路（60.42%）**について混合JRDB/JBIS出典チェーンを確保。残り19経路は人物接続待ち。JRDB正式旧祖先IDは0追加。JRDB source generation`5279af0bd8226cde`・top50研究JSONのSHAを固定。
- ローカル独立auditの実Parquet確認とローカル回帰テスト7件はPASS。**コミット済みGitHub Pythonモジュールそのものは未実行**。歴史的as-of未認証、`prediction_safe=false`、CURRENT/Review/RaceNote/PWAへは接続なし。
