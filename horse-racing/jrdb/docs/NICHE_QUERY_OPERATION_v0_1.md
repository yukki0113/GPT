# JRDB Niche Query Runner v0.1 — 運用契約

Status: implementation / **synthetic integration acceptance required** (see Actions audit). 2026-11-14.

## 目的と正本

チャットで自然言語のニッチな集計条件を受け、GPTが形式を確定した `QuerySpec` JSONを受け取る固定の実行口。**集計のたびに専用Pythonや日替わりmanifestをGitHubへ追加しない。** プロジェクト固有の集計アダプターは `horse-racing/jrdb/src/niche_query/`、DuckDB / Parquet / SHA検証 / Driveの転送は `tools/data-storage/` を正本とする。

- 入力: Google Drive canonical Analysis v1.4 CURRENT tar.xz（`current.json` と世代manifestを含む）。公開可否・ライセンスを確認。
- 入力 fingerprint: connected Drive connectorによる同じ登録フォルダのexact-name確認、前後metadata、native fetchした実バイトのSHA-256。`tools/data-storage/scripts/build_dynamic_drive_request.py`を使用。
- Archive展開: `tools/data-storage/scripts/safe_unpack_staged_archive.py`。自前のtar parserを追加しない。
- 世代選択: `resolve_analysis_generation.py`。CURRENT pointerからmanifest、対象年の参照行だけをSHA/size検証。**過去世代が混在するobjectsディレクトリの全globを禁止**。
- SQL: allowlist検証済みQuerySpecのみ。`compile_query.py` が固定のSELECTを組み立て、`data_storage.query.execute_query`で処理。自由SQL・外部URI・DDL・DML・任意のファイルパスを受け付けない。
- 実行: local dependency check → インストール修復1回 → 保守的な `[DATA_STORAGE_FALLBACK]` Actions。Issueを発行しただけでは完了にならない。
- Gitへ元のJRDBアーカイブ/Parquetは保存せず、Actions成果物にも生データを含めない。

## QuerySpec

`config/niche_query/example_yokoyama_2yo_op_v1.json` と `example_saturnalia_2yo_heavy_v1.json` を参照する。

必須: `dataset=jrdb.analysis.current`, `as_of_generation=CURRENT_AT_REQUEST`, `date_from`, `date_to`, `filters`, `groupings`。

フィルター演算: `eq`, `ne`, `in`, `between`, `gte`, `lte`。許可列のみ。グルーピング: 通常列または整数列の非重複距離帯 `bands`（最大12帯）。グループ最大3個。`other_bucket=excluded_with_count` は範囲外を別途監査記録、`included` は「その他」に表示。`detail=true` は出走明細を最大1,000件まで出力し、切り詰めを記録。SQLのパラメータは**値**としてのみエスケープし、列名・演算子はコード側allowlist。

`age=2` は**2歳馬の出走**を表す。2歳限定競走以外への混入があり得る条件は、利用可能なJRA競走条件と独立に照合する。`race_condition_code=OP` はJRDB上のOPクラス（リステッド・重賞を含む）の指定であり、gradeコード自体がOP判定の代替にはならない。

## 母数・回収率

- `entries`: 一致した全馬行。`starts`: 取消(1/01)・除外(2/02)を除いた行。中止・失格は出走分母に含め、着外。
- `win`, `second`, `third`, `other`: 1/2/3着/それ以外（中止、失格、finish欠損を含む）。`starts = win+second+third+other`。`horses` はユニークhorse_id数。
- `win_rate`, `top2_rate`, `top3_rate`: 各度数 / starts ×100。`win_roi`, `place_roi`: 各出走馬を100円購入する仮定で **払戻円合計 / starts** が回収率（%）に等しい。NULL分母はNULL（0%とはしない）。
- 1着の単勝払戻がNULL、未知の異常区分コード、総行数/manifestの不一致はFAIL。複勝払戻NULLは少頭数非発売等もあり得るため警告と件数を出す。全件の集計値を監査し、帯外件数とグループ件数が一致するかを検査する。
- 年ごとのraw異常コード、grade、sire名称等はデータの受理範囲であり、暗黙補正しない。推定・予想では対象日の結果をpre-raceデータに混入しない。

## Actionsで実行する標準手順

1. Connected Driveから `config/drive_source_registry.json` の `jrdb.analysis.current` **のみ**を名前・親フォルダでexact match。before metadataを保持。
2. Native `fetch(download_raw_file=true)` で現在ファイルをローカルにmaterialize。after metadataを再取得。前後ID/size/modified_timeが異なれば1回だけ取り直し、それでも不整合なら停止。
3. Source snapshot JSONと指定条件のQuerySpec JSONを用意。
4. 以下のbuilderで `dynamic_public_drive_inputs` とSHA固定requestを生成（PACI取得不要、日替わりGitコミット不要）。

```bash
python horse-racing/jrdb/src/niche_query/build_request.py \
 --snapshot /mnt/data/analysis_snapshot.json \
 --spec-file horse-racing/jrdb/config/niche_query/example_yokoyama_2yo_op_v1.json \
 --date YYYY-MM-DD \
 --output /mnt/data/niche_request.json
```

5. 発行前に **匿名取得と権利条件**を判定。匿名取得が規約上認められないJRDB資産を公開GitHub Issueへ流さない。非公開なら既存のapproved artifact等の認証経路へ切り替える（勝手な公開設定変更はしない）。
6. GitHub owner権限から題名 `[DATA_STORAGE_FALLBACK] JRDB Niche Query`、本文 `niche_request.json` のJSONオブジェクトでIssue作成。
7. IssueのActionsジョブを追跡し、`fallback-audit.json status=PASS` / 全Step exit=0 / artifact取得を確認。失敗なら原因修正・再試行。**Issue起動だけでターンを終了しない**。
8. 成果物の `niche_query/query_audit.json` と `results.json` / `results.csv` を読み戻し、件数整合・世代・SQLハッシュ・帯外を再確認して、日本語表と回収率で返答。

共通Stepsは `config/niche_query/actions_template_v1.json` に固定。古い`dynamic_drive_analysis_query_template.json`の全objects globは研究分析で使わない。

## ローカル実行

展開済みAnalysisを `--analysis-root` で渡す。Pythonのインポートパスには既存 Data Storage を指定する（DuckDB 1.1.3はその requirements に従う）。

```bash
PYTHONPATH=tools/data-storage python horse-racing/jrdb/src/niche_query/run_query.py \
 --analysis-root /tmp/jrdb_analysis_unpacked \
 --spec-file horse-racing/jrdb/config/niche_query/example_saturnalia_2yo_heavy_v1.json \
 --work-dir /tmp/niche-current-only \
 --output-dir /tmp/niche-results
```

`--work-dir` は空・未使用ディレクトリを使い、再実行で既存の成果を上書きしない。

## 成果物

`query_spec.json`, `results.json`, `results.csv`, `query_audit.json`, `matching_entries.csv`（detail指定時のみ）。

監査には `generation_id`, `manifest_sha256`, `selected partition SHA`, `input_parquet_rows`, `spec_sha256`, 各SQL SHA, 件数, 帯外件数, 回収率に関係する払戻集計, unknownコード/欠損が含まれる。Drive fingerprint/commit SHA/Actions stepの実行結果はData Storage共通fallback auditと合わせて照合。

## テスト・受入条件

- Stdlib: `python -m unittest discover -s horse-racing/jrdb/tests -p test_niche_query_v1.py -v`
- DuckDB synthetic: `horse-racing/jrdb/tests/niche_query_actions_smoke.py --output-dir <output>` (common Actions fallbackのステップとして実行可)
- 実データの回帰: 既存のサートゥルナーリア産駒/横山典弘OP結果と、同じgeneration・同じ集計定義で突合。**前回の完走ベース集計と、今回の取消除外を除く出走ベースで母数が異なり得るため、数値一致を無条件に要求しない**。
- 合成データでgeneration混入防止、SHA改竄検出、取消、ROI、帯外、道悪コード、SQL注入拒否をPASSさせる。
- 完了は実行終了、全監査PASS、成果物取得・読み戻し・会話での報告。Source取得不可/ライセンス不明の場合は機械処理の結果を捏造しない。