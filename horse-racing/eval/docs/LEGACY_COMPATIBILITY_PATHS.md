# Eval legacy / compatibility paths

Last reviewed: 2026-09-13

この文書はrepositoryに残る旧workflow・互換経路を、新しいChat / Workスレッドが現行標準と誤認しないための一覧です。

現行標準は `horse-racing/eval/README.md`、`.gpt/WORKFLOW.md`、`.gpt/HANDOFF.md` を優先します。

## 1. `.github/workflows/eval_image_enrich_chat.yml`

Status: **COMPATIBILITY / NON-STANDARD**

旧combined経路:

```text
[EVAL_IMAGE_ENRICH_REQUEST]
image Base64 chunks in Issue comments
-> Actions OCR
-> PACI fetch
-> enrichment
```

現在、ユーザーがChatへ画像を直接添付する通常運用は:

```text
C: direct OCR
-> OCR validation PASS
-> D: [EVAL_PACI_ENRICH_REQUEST]
```

combined workflowは、画像搬送からOCR/PACIまで1つのimmutable Actions runへ固定する等の明示要件がある場合だけ使用する。

## 2. `.github/workflows/eval_ocr_chat.yml`

Status: **COMPATIBILITY / CONDITIONAL D**

`[EVAL_OCR_REQUEST]` はGitHub media artifactをActions内でOCRする旧/互換経路。

通常はmedia artifactをA: Read/Auditで回収し、通常規模ならC: local/direct OCRを使用する。

次の場合のみ利用価値がある。

- GitHub内artifact chainを維持する
- runner Tesseract環境を固定する
- 多数画像・長時間OCR
- immutable OCR runを正式監査証跡として残す

## 3. `.github/workflows/eval_jrdb_dataset_issue.yml`

Status: **RETIRED FOR CURRENT OPERATION / DO NOT USE AS CURRENT SOT**

このworkflowは `[EVAL_JRDB_DATASET]` Issueを受け、repository内の旧Excel ledgerを読む設計を持つ。

既定値:

```text
horse-racing/eval/ledger/Eval表集計・検証.xlsx
```

さらに旧Excelの `レース分析` から対象raceを抽出し、JRDB BAC/SEDを取得してdataset化する。

現在の継続台帳正本はネイティブGoogle Sheets `Eval表集計・検証` であり、GitHub上のxlsxは移行前snapshotである。そのため、このworkflowを現行台帳からのdataset生成経路として使用してはいけない。

現在のPhase2 / 結果取込では用途に応じて次を使う。

- Phase2 pre-race: `build_phase2_jrdb_kyi_features.py` / training / previous / feature bundle
- Phase2 post-race: `backfill_phase2_sed.py`
- `全馬データ` 結果取込: `docs/README_jrdb_horse_results_import.md` + `export_jrdb_eval_horse_results.py` + native Google Sheets

workflow file自体は歴史的再現・旧artifact参照のため残っているが、新規requestを発行しない。

## 4. Manual workflows

以下のmanual workflowは人間によるGitHub UI操作・非常時の予備経路であり、Chat標準経路ではない。

```text
.github/workflows/eval_media_manual.yml
.github/workflows/jra_results_manual.yml
```

## 5. 判断原則

repositoryにworkflowが存在すること自体は、現在の標準経路であることを意味しない。

新規スレッドでは必ず:

```text
README
-> CONTEXT
-> WORKFLOW
-> HANDOFF
-> target source/workflow
```

を確認し、A/B/C/D routingと外部正本の定義を優先する。
