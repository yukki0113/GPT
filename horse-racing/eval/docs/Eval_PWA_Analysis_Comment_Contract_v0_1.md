# Eval PWA Analysis Comment Contract v0.1

Status: ACCEPTED  
Accepted: 2026-09-12

## 1. Purpose

Eval完成CSVをJRDB Newspaper / PWAへ渡す際、既知の研究条件に該当する、または該当可能性が高い注目馬だけに事前分析コメントを付与し、PWA上でEval値からモーダル参照できるようにする。

目的は「Eval値そのもの」と「そのEvalをどう読むべきか」を分離し、新聞本体を情報過多にせず、注目馬だけを素早く発見できるようにすること。

## 2. Ownership / boundary

### Eval research side owns

- 注目馬の選定
- 既知条件の判定
- 条件コード付与
- 分析タイトル・分析コメント生成
- 条件が未確定の場合の `*_PRE` 明示
- コメント生成時点のas-of管理

### Newspaper merge owns

- PWA提出CSVのexact join
- CSV分析列を `addons.eval.analysis` へ透過的に格納
- 欠損・重複・馬名不一致等の監査

### PWA owns

- Eval値の通常表示
- `addons.eval.analysis.comment` が存在する馬だけEval値をリンク/ボタン化
- tap/click時のモーダル表示

PWAは条件判定を再実装しない。コメントの有無から研究条件を推測しない。

## 3. Source immutability

次の既存資産は変更しない。

1. OCR 5列中間CSV
   - `date`
   - `venue`
   - `race_no`
   - `horse_no`
   - `eval`
2. PACI付与済みEval完成CSVの既存列意味

PWA提出用はEval完成CSVから派生させる。

標準ファイル名:

`YYYYMMDD_Eval_PWA提出CSV_v0_1.csv`

## 4. Added CSV columns

PWA提出CSVでは既存Eval完成CSVの末尾に次の6列を追加する。

| column | type / rule | purpose |
|---|---|---|
| `eval_analysis_status` | `NONE` / `WATCH` / `MATCH` | 分析状態 |
| `eval_analysis_codes` | `;` 区切り文字列 | 条件コード。複数可 |
| `eval_analysis_title` | text | モーダル見出し |
| `eval_analysis_comment` | text | 人間向け事前分析本文 |
| `eval_analysis_version` | text | 判定・コメント仕様version |
| `eval_analysis_asof` | ISO-8601 datetime | コメント生成時点 |

### Non-highlighted horses

通常馬は次とする。

- `eval_analysis_status = NONE`
- `eval_analysis_codes = ""`
- `eval_analysis_title = ""`
- `eval_analysis_comment = ""`
- `eval_analysis_version = phase2-comment-v0.1`
- `eval_analysis_asof = <generation time>`

PWAのリンク判定は `eval_analysis_comment` の非空判定のみを使用する。

## 5. Status semantics

### NONE

現時点でPWA表示対象の分析コメントなし。

### WATCH

既知条件の一部を満たすが、オッズ等の未取得要素があり正式条件成立をまだ確定できない、または研究上注視すべき事前構造がある。

### MATCH

コメント生成時点で必要な条件がすべて観測可能で、定義済み条件を満たす。

`MATCH` は「馬券推奨」「的中保証」を意味しない。

## 6. Initial condition codes

### H1_PRE

Forward H1の事前候補。

H1定義:

- Eval順位1位
- 1位Eval - 2位Eval = 0～4
- 最終単勝オッズ 5.0～9.9

PWA提出時点で最終単勝オッズが未確定の場合、最初の2条件を満たした馬は `WATCH / H1_PRE` とする。

コメント本文には必ず「最終単勝5.0～9.9倍ならH1 Forward対象」等、未確定条件を明示する。

### H1_MATCH

コメント生成時点で最終単勝オッズを含むH1全条件が観測・成立している場合のみ使用する。

### H2_PRE

Forward H2の事前候補。

H2定義:

- Eval順位2位
- 最終単勝オッズ 10.0～19.9

最終単勝オッズ未確定時は `WATCH / H2_PRE` とする。

### H2_MATCH

コメント生成時点で最終単勝オッズを含むH2全条件が観測・成立している場合のみ使用する。

## 7. Supplemental analysis codes

Phase2 JRDB feature bundleの整備に伴い、調教、休養、適性、展開、前走条件等の補助コードを追加してよい。

ただし次を守る。

- Discovery中の特徴を自動的な買い条件へ昇格させない
- 補助コードは「説明材料」であり、単独で馬券ルールを意味しない
- 新しい正式条件コードは研究定義を先に文書化してから使用する
- 結果を見た後に当日のコメント・コードを書き換えない

## 8. Comment policy

コメントは事前情報だけで作成する。

禁止:

- レース結果を知った後の後付け説明
- 同一サンプルの発見結果を確定ルールのように表現すること
- `H1_PRE` を `H1_MATCH` のように表現すること
- 「買い」「鉄板」等、研究状態を超えた断定

推奨構成:

1. Eval位置・差
2. 注目条件
3. JRDB事前特徴量による支持材料 / リスク材料
4. 未確定条件があれば明記

タイトルは短く、本文はスマホモーダルで読みやすい長さを基本とする。

## 9. Newspaper JSON mapping

CSVの分析列はNewspaper merge時に次へ格納する。

コメントなし:

```json
{
  "addons": {
    "eval": {
      "eval": 52,
      "analysis": null,
      "source": "Eval表",
      "source_date": "2026-09-12"
    }
  }
}
```

コメントあり:

```json
{
  "addons": {
    "eval": {
      "eval": 52,
      "analysis": {
        "status": "WATCH",
        "codes": ["H1_PRE"],
        "title": "H1 Forward事前候補",
        "comment": "Eval1位、2位との差2。調教指数21.5でレース1位、前走から14日。最終単勝5.0～9.9倍ならH1 Forward対象。現時点ではオッズ条件未確定。",
        "version": "phase2-comment-v0.1",
        "asof": "2026-09-12T09:00:00+09:00"
      },
      "source": "Eval表",
      "source_date": "2026-09-12"
    }
  }
}
```

`eval_analysis_codes` はCSV読込時に `;` で分割しJSON arrayへ変換する。

## 10. PWA display contract

- `addons.eval` が存在すればEval値を表示する
- `addons.eval.analysis.comment` が空/nullなら従来どおり通常文字列
- 非空ならEval値をリンク/ボタン相当のUIにする
- tap/clickで既存dialog思想を利用した分析モーダルを開く
- モーダルには最低限、馬名、Eval値、analysis title、comment、codesを表示する
- 全馬にアイコンやボタンを置かず、注目馬だけリンク化する
- analysisが無い旧JSONでも表示を壊さない

## 11. Audit requirements

PWA提出CSV生成時に最低限確認する。

- 元Eval完成CSVと行数・canonical keyが一致
- 分析列追加によって既存Eval/PACI値を変更していない
- `NONE` 行はcomment空
- comment非空行はstatusが `WATCH` または `MATCH`
- `WATCH/MATCH` 行はtitle/comment/version/asofが非空
- codesは空要素を持たない
- asofは対象レース結果より前の生成時点

Newspaper mergeでは既存のEval exact join監査を維持する。

## 12. Versioning

初版:

- CSV contract: `Eval PWA submission v0.1`
- analysis version: `phase2-comment-v0.1`

列追加・status意味変更・JSON mapping変更時はversionを上げる。
