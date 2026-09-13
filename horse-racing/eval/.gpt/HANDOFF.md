# Eval project thread handoff / bootstrap

Last reviewed: 2026-09-13

この文書は、Chatスレッドの会話量上限・引っ越し・担当交代が発生しても、過去チャット全文へ依存せずEvalプロジェクトの思想・標準運用・主要module・安全条件を復元するための入口です。

静的文書へ「最後に処理した開催日」等の短命な状態は固定しません。日次の画像・CSV・run IDはその時点の依頼・artifact・外部台帳から解決し、ここには長期に維持すべき契約だけを置きます。

## 1. 新しいスレッドで最初に読む順序

1. repository root `.gpt/GITHUB_OPERATION_POLICY.md`
2. `horse-racing/eval/README.md`
3. `horse-racing/eval/.gpt/CONTEXT.md`
4. `horse-racing/eval/.gpt/WORKFLOW.md`
5. 本 `HANDOFF.md`
6. OCRを扱う場合 `docs/OCR_Validation_Contract.md`
7. Phase2研究を扱う場合:
   - `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md`
   - `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md`
   - `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md`
8. PWA分析コメントを扱う場合:
   - `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
   - `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md`
9. 結果取込を扱う場合 `docs/README_jrdb_horse_results_import.md`
10. repositoryに残る旧workflowを判断する場合 `docs/LEGACY_COMPATIBILITY_PATHS.md`

その後、必ずlatest `main` の対象source / tests / workflowを実物確認する。READMEだけを見てsourceを推測しない。

version付きcontractとsource `VERSION` / output schemaが一致しない場合は、古いdocumentへsourceを合わせず、実装・tests・docsを監査してcurrent contractを確定する。

## 2. プロジェクトの中心思想

### 2.1 OCR値は「検証される対象」であり、検証基準ではない

PACI joinが成功しても、`date + venue + race_no + horse_no` の同一性が確認できるだけでEval数値のOCR正しさは保証されない。

したがって正式完成条件は次のANDとする。

```text
ocr_validation_status == ok
AND
paci_join_validation_status == success
```

OCR error / `requires_review` が残る場合、PACIへ進めて形式上joinできても正式完成扱いにしない。

### 2.2 画像側の独立情報をvalidationに使う

Eval表の順位色は画像凡例を正本とし、固定順序は次のとおり。

```text
red(1位) -> blue(2位) -> orange(3位) -> green(4位) -> yellow(5位)
```

この順序をOCR数値から推定してはいけない。同値tieは合法。最低順位の着色境界と無色セルが同値になることも合法。

2026-09-05に `24->94`, `21->91`, `23->93`, `29->99` 等の2/9先頭桁誤読が実運用で確認されたため、`9x` は機械置換せず独立再読する。色順位矛盾・着色1桁・digit component不整合等も再読トリガーに使う。再読根拠が弱ければfail-closedでmanual reviewとする。

### 2.3 識別キーと文字OCRを分離する

OCR中間CSVは以下5列だけを正規契約とする。

```text
date,venue,race_no,horse_no,eval
```

R番号はパネル位置、馬番は行位置で確定する。馬名文字列はOCRしない。正式馬名・レース条件・馬属性は後段JRDB PACIからcanonical keyで付与する。

### 2.4 事前情報と結果情報を混ぜない

Phase2のForward/事前分析では、現在レース後にしか分からないSED、確定着順、確定人気、確定オッズ、払戻等を事前特徴量へ混入させない。

PACIのKYI/CHA/CYB/BAC/ZED等、対象時点で提供済みの開催前情報を明示的なavailability class付きで使用する。前走情報はKYIのresult keyとPACI ZEDをexact-linkし、馬名近似や日付推測fallbackをしない。

結果時点のSED backfillは別レイヤーとして扱い、事前特徴量との境界を維持する。

### 2.5 JRDB固定長定義をEval側へ複製しない

JRDB固定長BYTE位置の正本はJRDB common parser / adapter側。Eval側Phase2 moduleは既にparseされた値を研究schemaへ投影するconsumerとし、必要なfieldが無ければJRDB共通Parser側へ追加する。Eval側で固定長offsetを直読みして局所仕様を増やさない。

### 2.6 Discoveryと正式ルールを分離する

Phase2で見つかった特徴・セル・条件を、同一標本を見てそのままForward購入条件へ昇格させない。Discovery特徴はまず説明材料として扱い、正式条件は定義文書を先に固定してから使用する。

PWA側はEval研究条件を再実装しない。Eval側が条件判定・analysis code/commentを所有し、Newspaper/PWAは契約どおり透過格納・表示する。

### 2.7 完成CSVとPWA提出CSVを分離する

PACI付与済み完成CSVは既存Eval/PACI列を保持する入力正本。PWA提出CSVはそこから派生する配布成果物であり、analysis列を追加しても既存列値を書き換えない。

注目馬の条件判定・コメント文は研究側の責務とし、transport moduleへH1/H2等の研究ロジックを埋め込まない。PWA提出時の詳細は `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md` を正本とする。

## 3. 毎週の標準作業: Eval画像 -> 完成CSV -> PWA提出CSV

ユーザーがChatへ当日のEval画像を直接添付し「完成CSV」を依頼した場合、標準は次。PWA連携を行う通常運用では完成CSVの後にPWA提出CSVまで派生生成する。

```text
1. A: latest main / current docs / sourceを確認
2. C: Chat/ローカルで `src/extract_eval_table.py` / `src/eval_ocr/` を実行
3. 5列OCR CSV + validation JSONを生成
4. validation.status == ok を確認
5. D: `[EVAL_PACI_ENRICH_REQUEST]` でActions SecretsからPACI取得・enrichment
6. A: `EVAL_PACI_ENRICH_RESULT` / run / artifactを監査・回収
7. 完成CSV + auditを確定
8. C: Eval研究側で注目馬analysis overlayを作成
9. C: `src/build_eval_pwa_submission.py` でPWA提出CSV + auditを生成
10. PWA提出CSVと、最高Eval・主要code件数・目立つ馬をまとめた簡潔なスレッドサマリを返す
```

画像が直接添付されている場合、画像取得IssueやOCR Issueを追加で作らない。OCRのみ、または完成CSVのみを明示された場合はその段階で停止してよい。

### OCR必須確認

最低限:

```text
race_panels == detected_venues * 12
missing_eval == 0
eval_out_of_range == 0
duplicate_keys == 0
color_top_set_violations == 0
color_order_violations == 0
color_same_color_inconsistencies == 0
ocr_manual_review_required == 0
status == ok
```

開催数は画像レイアウトに従う。通常は2会場=24R、3会場=36R。

### PACI必須確認

通常 `fail_on_unmatched=true`。

```text
fetch_exit_code == 0
enrich_exit_code == 0
collect_exit_code == 0
joined_horses == input_rows
unmatched_horses == 0
duplicate_keys == 0
```

`race_headcount_mismatches` は必ず確認し、0でなければ警告として明示する。

PACI ZIPをユーザーへ要求しない。取得はActions Secrets `JRDB_USER` / `JRDB_PASSWORD` を使うD経路。

### PWA提出必須確認

`docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` と `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md` に従い、最低限:

```text
source_rows == output_rows
source canonical keys == output canonical keys
existing source columns unchanged
unknown analysis key == 0
NONE -> comment blank
WATCH/MATCH -> codes/title/comment/version/asof present
```

同値tie等で研究側のEval順位定義を完成CSVから一意に再現できない場合、馬番順等の便宜的tie-breakでcondition codeを固定しない。current research定義を確認し、解決不能ならreview対象とする。

### 通常返却物

- `YYYYMMDD_Eval_完成CSV.csv`
- 完成CSV audit JSON
- `YYYYMMDD_Eval_PWA提出CSV_v0_1.csv`
- PWA提出CSV audit JSON（監査が必要な実行では保持）
- スレッド上の簡潔な当日分析サマリ
- OCR 5列CSV / OCR validation JSONは監査用補助成果物

PWAサマリは全候補を長く列挙せず、最高Eval、主要analysis code件数、3～5頭程度の目立つ馬、極端値/警告を中心とする。詳細はPWAモーダルを主な閲覧面とする。

## 4. GitHub実行経路

root `GITHUB_OPERATION_POLICY.md` のA/B/C/Dを適用する。

- **A Read / Audit**: main、file、commit、Issue RESULT、run、artifact metadata、SHA、diff。Issue不要。
- **B Git Change**: Python/tests/docs/config/workflow等UTF-8テキスト変更。direct create/update/delete。`[gpt-git-update]` は標準でない。
- **C Pure Deterministic Execution**: 手元画像のOCR、PWA提出CSV build、CSV/JSON変換、focused test、固定入力監査等。Secrets不要・通常規模ならローカル優先。
- **D Actions-Native Execution**: Secrets、認証外部取得、正式artifact chain、長時間/大容量、runner固定、immutable監査run等。

EvalでDを維持する代表例:

1. `[EVAL_PACI_ENRICH_REQUEST]` — JRDB認証Secretsと完成CSV監査artifactが必要。
2. `[EVAL_MEDIA_REQUEST]` — X投稿取得時点のmedia/metadataをimmutable artifactとして固定したい通常収集。
3. `[EVAL_OCR_REQUEST]` — 通常標準ではない。GitHub内artifact chain、runner Tesseract固定、多数画像、明示的なimmutable OCR runが必要な場合のみ。
4. `[JRA_RESULTS_REQUEST]` — 直接取得不可、長期/大量、正式取得runが必要な場合のみ。通常規模で直接実行可能ならC。

`.github/workflows/eval_image_enrich_chat.yml` は旧combined compatibility経路。`.github/workflows/eval_jrdb_dataset_issue.yml` は旧GitHub xlsx ledgerを読むretired経路。詳細は `docs/LEGACY_COMPATIBILITY_PATHS.md`。Chatへ画像が直接添付される現在の通常運用ではC OCR + D PACI enrichmentを標準とする。

## 5. 主要module map

### 5.1 OCR / weekly operation

| module | responsibility |
|---|---|
| `src/extract_eval_table.py` | OCR親CLI、CSV/validation出力、statusをexit codeへ反映 |
| `src/eval_ocr/layout_detector.py` | 会場/Rパネル・表構造検出 |
| `src/eval_ocr/japanese_ocr.py` | 会場ヘッダーOCR・JRA会場解決 |
| `src/eval_ocr/numeric_ocr.py` | Eval数値stack OCR、digit component repair、独立再読、audit provenance |
| `src/eval_ocr/color_detector.py` | Evalセル色分類、固定順位色 |
| `src/eval_ocr/pipeline.py` | layout/OCR/colorの統合、色矛盾による二段階再読 |
| `src/eval_ocr/validator.py` | 構造・キー・値域・色順位・tie・manual reviewのfail-closed gate |
| `src/eval_ocr/csv_writer.py` | 5列CSV出力 |
| `tests/test_eval_ocr_regressions.py` | 0905障害を含むOCR回帰contract |

### 5.2 PACI enrichment

| module | responsibility |
|---|---|
| `../jrdb/src/fetch_jrdb_paci.py` | Actions Secretsで対象日PACIyymmdd.zip取得 |
| `../jrdb/src/enrich_eval_csv_with_paci.py` | OCR5列へBAC/KYI由来の正式馬名・事前レース/馬情報を付与 |
| `.github/workflows/eval_paci_enrich_chat.yml` | 認証取得、enrichment、audit、artifactを同一runへ固定 |

PACI enrichmentはAnalysis Lite / Core SQLite / current-race SEDを依存先にしない。

### 5.3 Phase2 pre-race research

| module | responsibility | current contract |
|---|---|---|
| `src/build_phase2_jrdb_kyi_features.py` | KYI事前特徴。休養、脚質、調教/厩舎判断、適性、予想ペース、展開index/rank、スタート関連、入厩、事前馬体重等 | `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md` |
| `src/build_phase2_jrdb_training_features.py` | KYI identity setへCHA/CYBをLEFT JOIN。追切・仕上・調教量等 | `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md` |
| `src/build_phase2_jrdb_previous_features.py` | KYI前走result key -> PACI ZED exact-link。距離/芝ダ/前走馬場等 | `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md` |
| `src/build_phase2_jrdb_feature_bundle.py` | 上記3componentをrace_horse_keyで1対1統合しaudit。blank/Noneは同一missingとして正規化 | component contractsを合成 |
| `tests/test_build_phase2_jrdb_*` | component/bundle契約の回帰test | tests |

KYI `training_index`、CHA `cha_workout_index`、CYB `cyb_workout_index` は別概念。片方へ統合しない。

### 5.4 PWA submission

| module | responsibility |
|---|---|
| `src/build_eval_pwa_submission.py` | 研究側analysis overlayを完成CSVへcanonical key exact mergeし、6列analysis contract・auditを生成 |
| `tests/test_build_eval_pwa_submission.py` | source不変、NONE/WATCH、unknown key fail-closed等の回帰test |

研究条件の判定ロジックはこのmoduleへ入れない。conditions / comment policyはcontractを正本とする。

### 5.5 Post-race / ledger

| module | responsibility |
|---|---|
| `src/backfill_phase2_sed.py` | Phase2研究行へSED結果を結果時点layerとしてbackfill |
| `../jrdb/src/export_jrdb_eval_horse_results.py` | Google Sheets `全馬データ` 向け1頭1行結果CSV + audit |
| `src/fetch_jra_daily_results.py` | JRA日次結果/払戻取得（現行取得元はYahoo!スポーツ） |
| `src/validate_jra_results.py` | JRA結果機械validation |

台帳正本はネイティブGoogle Sheets `Eval表集計・検証`。GitHub旧xlsxや旧Drive Excelを最新と推定しない。

## 6. 重要な契約文書

- `docs/OCR_Validation_Contract.md` — OCR安全性・固定色・2/9再読・release gate
- `docs/README_0905_OCR_FIX.md` — 2026-09-05障害の要約
- `docs/Eval_Phase2_JRDB_KYI_Features_v0_2.md` — KYI事前特徴の現行contract
- `docs/Eval_Phase2_JRDB_Training_Features_v0_1.md` — CHA/CYB事前特徴
- `docs/Eval_Phase2_JRDB_Previous_Features_v0_1.md` — 前走exact-link特徴
- `docs/Phase2_SED_Backfill_20260908.md` — 結果時点SED backfill監査
- `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md` — Eval研究側/Newspaper/PWAの責務境界とanalysis列契約
- `docs/Eval_PWA_Submission_Daily_Operation_v0_1.md` — PWA提出CSV生成・監査・スレッド簡潔サマリ
- `docs/README_jrdb_horse_results_import.md` — `全馬データ` 結果取込
- `docs/README_master_eval_media_collector.md` — X画像収集
- `docs/LEGACY_COMPATIBILITY_PATHS.md` — repositoryに残る旧/互換workflowのcurrent/legacy判定

研究条件・analysis codeの具体定義は各contractを正本とし、このhandoffへ複製しない。条件更新時の二重管理を避ける。

## 7. Canonical key

日次OCR/PACIの中心キー:

```text
date + venue + race_no + horse_no
```

Google Sheets等で文字列化するときは区切り付き:

```text
開催日|場|R|馬番
```

可変桁を区切りなしで連結しない。`1R/11番` と `11R/1番` が衝突する。

PWA提出overlay / Newspaper Eval joinでは `date + venue_code + race_no + horse_no` を使用する。Phase2 JRDB component内部ではJRDB `race_horse_key` を利用し、各componentのidentity set一致を必須にする。

## 8. スレッド引っ越し時の最小引継ぎ

通常の週次CSV作業なら、新スレッドへ過去会話全文を持ち込む必要はない。新スレッドは本書とlatest mainを読み、ユーザーから対象日の画像または完成CSVを受け取れば再開できる。

進行中作業を途中で引き継ぐ場合だけ、次を短く残す。

```text
対象日:
入力画像/ZIP:
OCR実行済み?:
OCR validation status:
5列CSV path/reference:
PACI Issue番号/request_id:
PACI run_id/artifact_name:
完成CSV生成済み?:
完成CSV reference:
PWA analysis contract/version:
analysis as-of:
analysis overlay生成済み?:
PWA提出CSV生成済み?:
highlighted_rows / code_counts:
未解決tie/rank review:
スレッド簡潔サマリ返却済み?:
未解決manual review/validation error:
Git source commit/SHA:
```

不明項目を推測で埋めない。upstream RESULT / artifactはGitHubから再監査する。

## 9. 更新時ルール

思想・標準経路・canonical key・release gate・主要moduleの責務が変わった場合、本書をREADME / CONTEXT / WORKFLOWと同時に見直す。

日次run ID、開催ごとの頭数、単発の検証結果など短命な情報は本書へ蓄積しない。必要な恒久障害知見だけcontract/testへ昇格させる。
