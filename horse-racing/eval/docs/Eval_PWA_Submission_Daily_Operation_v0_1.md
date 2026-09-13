# Eval PWA Submission Daily Operation v0.1

Status: CURRENT  
Reviewed: 2026-09-13

## 1. Purpose

Eval完成CSVを受け取った後、既知の研究条件に該当する・該当見込みの注目馬だけへ事前分析コメントを付与し、JRDB Newspaper / PWAへ渡す `PWA提出CSV` を生成する日次運用を定義する。

分析列の意味・WATCH/MATCH・analysis code・Newspaper JSON mapping・PWA表示責務は次を正本とする。

- `Eval_PWA_Analysis_Comment_Contract_v0_1.md`

本書はそのcontractを日次作業へ落とす運用手順であり、条件定義を複製しない。

## 2. Standard input / output

入力:

- `YYYYMMDD_Eval_完成CSV.csv`
- 当日時点で利用可能なEval研究条件・Phase2事前特徴

標準出力:

- `YYYYMMDD_Eval_PWA提出CSV_v0_1.csv`
- PWA提出CSV audit JSON（監査が必要な実行では保持）
- Chatスレッド上の簡潔な当日分析サマリ

PWA提出CSVは完成CSVを置換するものではない。完成CSVは既存列意味を保持した正本入力であり、PWA提出CSVはそこから派生する配布用成果物。

## 3. Ownership

### Eval research side

- 注目馬の選定
- condition code判定
- WATCH / MATCH判定
- analysis title / comment作成
- Phase2事前特徴による支持材料・リスク材料の選択
- as-ofの確定

### `build_eval_pwa_submission.py`

- 完成CSVの全行・全既存値を維持
- 研究側overlayをcanonical keyでexact merge
- 6つのanalysis列を末尾へ追加
- NONE行の初期化
- status/comment/code整合validation
- sourceに存在しないanalysis keyをfail-closed
- 行数・status/code件数等のaudit生成

このmoduleはH1/H2等の研究条件そのものを判定しない。研究条件をtransport moduleへ埋め込まない。

### Newspaper / PWA

`Eval_PWA_Analysis_Comment_Contract_v0_1.md` の責務境界どおり、研究条件を再実装しない。

## 4. Canonical key

PWA提出生成時のoverlay joinは次を使用する。

```text
date + venue_code + race_no + horse_no
```

馬名近似や曖昧joinをしない。overlay keyが完成CSVに存在しない場合は推測せずerrorにする。

## 5. Analysis overlay

研究側は、コメントを表示する馬だけ次のようなJSON overlayを作成する。

```json
{
  "entries": [
    {
      "date": "2026-09-13",
      "venue_code": "06",
      "race_no": 4,
      "horse_no": 7,
      "status": "WATCH",
      "codes": ["H1_PRE"],
      "title": "H1 Forward事前候補",
      "comment": "最終単勝条件は未確定。"
    }
  ]
}
```

コメントなしの馬をoverlayへ列挙する必要はない。builderが `NONE` として補完する。

### Ranking / tie guard

`Eval順位1位/2位` 等の条件は、その研究条件で採用している順位定義に従う。

完成CSVに順位列が無く、同値tie等で順位定義を一意に再現できない場合、馬番順等の便宜的tie-breakを研究条件そのものとして固定しない。current research contract / ledger定義を確認し、解決できなければ当該condition codeの自動付与を保留してreview対象とする。

## 6. Builder command

```bash
python horse-racing/eval/src/build_eval_pwa_submission.py \
  --eval-csv YYYYMMDD_Eval_完成CSV.csv \
  --analysis-json YYYYMMDD_Eval_PWA分析overlay.json \
  --output YYYYMMDD_Eval_PWA提出CSV_v0_1.csv \
  --audit-json YYYYMMDD_Eval_PWA提出CSV_v0_1.audit.json \
  --analysis-version phase2-comment-v0.1 \
  --asof 2026-09-13T09:00:00+09:00
```

analysis overlayが0件の場合は `--analysis-json` を省略できる。その場合も全行へanalysis contract列を追加し、statusは `NONE` となる。

## 7. Daily audit gate

最低限確認する。

```text
source_rows == output_rows
source canonical keys == output canonical keys
existing source columns unchanged
analysis columns appended only
unknown analysis key == 0
invalid analysis status/comment combination == 0
```

さらにauditの以下をスレッド確認に使う。

- `highlighted_rows`
- `status_counts`
- `code_counts`
- `analysis_version`
- `analysis_asof`

結果を知った後に当日analysis comment / codeを都合よく書き換えない。

## 8. Standard Chat summary

PWA提出CSVを返すときは、CSVリンクだけで終了せず、スレッドにも「ざっと見る用」の短い分析サマリを添える。

標準は次。

1. 当日の最高Evalと、必要なら上位3～5頭
2. WATCH / MATCHおよび主要analysis code件数
3. その中で特に目立つ馬を3～5頭程度
4. 異常に高いEval、極端なEval差、強い/弱い調教、長期休養等の明瞭な特徴
5. 入力・監査上の警告があれば明示

全コメント対象馬の長い内訳は通常スレッドへ展開しない。詳細はPWAのEvalリンク→モーダルを主な閲覧面とする。

例:

```text
最高Evalは○○R △△の86。H1_PRE 7頭、H2_PRE 24頭。
特に□□はEval差が小さい一方で調教指数がレース上位。
90台後半等の極端値やデータ警告はなし。詳細はPWAコメント参照。
```

`Eval97` のような通常より明らかに目立つ値が出た場合は、件数集計より優先して冒頭で明示する。

## 9. No hindsight / no recommendation inflation

スレッドサマリもPWAコメントと同じas-of制約に従う。

- 当日事前情報だけで記述する
- `*_PRE` を成立済み条件として書かない
- WATCHを買い推奨へ読み替えない
- Discovery特徴を確定ルールのように扱わない
- レース結果後に事前コメントを改変しない

## 10. Thread handoff

新スレッドでは、PWA提出CSV作業を行う前に次を読む。

1. `horse-racing/eval/README.md`
2. `.gpt/CONTEXT.md`
3. `.gpt/WORKFLOW.md`
4. `.gpt/HANDOFF.md`
5. `docs/Eval_PWA_Analysis_Comment_Contract_v0_1.md`
6. 本書
7. `src/build_eval_pwa_submission.py` とtests

進行中の開催を引き継ぐ場合は最低限次を残す。

```text
対象日:
完成CSV reference:
analysis contract/version:
analysis as-of:
overlay生成済み?:
PWA提出CSV生成済み?:
highlighted_rows / code_counts:
未解決tie/rank review:
スレッド簡潔サマリ返却済み?:
```

短命な当日件数や馬名は本書へ固定しない。
