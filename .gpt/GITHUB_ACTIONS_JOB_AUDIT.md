# GitHub Actions Job Time Audit

`yukki0113/GPT` の GitHub Actions 実行履歴から、実際に runner へ乗った job の時間を集計し、リポジトリを Private 化した場合の GitHub-hosted runner 分数を近似する共通監査ツールです。

対象ツール:

```text
.gpt/tools/github_actions_job_audit.py
```

## 目的

Workflow run の件数だけではなく、各 run の job を取得して以下を集計します。

- Workflow run の成功 / 失敗 / cancelled / skipped 件数
- job の成功 / 失敗 / cancelled / skipped 件数
- 実 runner 時間
- job ごとの1分切り上げ時間
- GitHub-hosted runner のみを対象にした Private 化時の推定分数
- workflow 別の推定分数
- runner 種別（GitHub-hosted / self-hosted / unknown）
- runner OS（Linux / Windows / macOS / unknown）

GitHub公式の job usage 表示と同じ考え方で、Private repository の GitHub-hosted runner は job 単位で次の1分へ切り上げます。self-hosted runner は Private 推定分数へ含めません。

このツールは runner の OS 別 minute multiplier や金額を計算しません。目的は「Private 化した場合に何分程度の runner quota を使いそうか」を監査することです。

## 前提

認証済み GitHub CLI が必要です。

```bash
gh auth status
```

Python は標準ライブラリのみを使用します。

## 基本実行

1か月分を監査:

```bash
python .gpt/tools/github_actions_job_audit.py --month 2026-09
```

任意期間:

```bash
python .gpt/tools/github_actions_job_audit.py \
  --from 2026-09-01 \
  --to 2026-09-30
```

既定リポジトリは `yukki0113/GPT` です。別リポジトリを対象にする場合:

```bash
python .gpt/tools/github_actions_job_audit.py \
  --repo owner/repository \
  --month 2026-09
```

## CSV / JSON 出力

job 単位の詳細CSV:

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --csv output/github_actions_job_audit_2026-09.csv
```

構造化JSONも同時出力できます。

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --csv output/github_actions_job_audit_2026-09.csv \
  --json output/github_actions_job_audit_2026-09.json
```

CSVはExcelで開きやすいよう UTF-8 BOM 付きで出力します。

## Workflow の除外 / 絞り込み

将来 Public 側へ分離した Pages workflow などを Private 換算から外したい場合は、workflow名またはYAMLパスに対する正規表現で除外できます。

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --exclude-workflow-regex 'Pages'
```

複数指定できます。

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --exclude-workflow-regex 'Pages' \
  --exclude-workflow-regex 'smoke'
```

逆に一部の workflow だけを見る場合:

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --include-workflow-regex 'JRDB|Eval'
```

## 集計仕様

### Workflow run

GitHub REST API の repository workflow-runs を `created=YYYY-MM-DD..YYYY-MM-DD` で取得します。したがって期間の基準は **workflow run の `created_at`（UTC）** です。

`conclusion=skipped` の run は runner を取得していないため、job API 呼び出し自体を省略します。

### Job

各非skipped runについて、jobs APIを `filter=all` で取得します。再実行された job attempt も監査対象です。

実行時間:

```text
completed_at - started_at
```

Private 推定分数:

```text
GitHub-hosted runner の各jobについて
ceil(duration_seconds / 60)
```

開始・終了時刻が存在する非skipped job は最低1分として扱います。

### Runner 判定

以下を使って分類します。

- `self-hosted` label → self-hosted
- `runner_group_name == GitHub Actions`
- `runner_name` が `GitHub Actions` で始まる
- `ubuntu*` / `windows*` / `macos*` label

runner種別を判定できないjobは `unknown` とし、Private推定分数には含めず警告を表示します。

## 注意点

- 現在のPublic repositoryではGitHub側に過去の「Privateだった場合のbillable minutes」は保存されていないため、これは job timestamp からの近似です。
- GitHub-hosted runner の job 単位1分切り上げは反映します。
- Windows / macOS 等の minute multiplier、larger runner の料金体系、将来のGitHub料金改定は反映しません。
- 月跨ぎで古いrunを大きく時間を空けてrerunした場合、そのrerunは元runの `created_at` が対象期間外なら取得されません。通常の月次監査では問題になりにくいですが、厳密な請求照合用途ではGitHub Billing側の実績と併用してください。

## 9月末の再評価例

2026年9月分をそのまま確認:

```bash
python .gpt/tools/github_actions_job_audit.py \
  --month 2026-09 \
  --csv output/github_actions_job_audit_2026-09.csv \
  --json output/github_actions_job_audit_2026-09.json
```

その時点で `Estimated private GitHub-hosted minutes` と workflow別内訳を見れば、環境整備ラッシュが落ち着いた後の平常運用に近い数字でPrivate化を再検討できます。
