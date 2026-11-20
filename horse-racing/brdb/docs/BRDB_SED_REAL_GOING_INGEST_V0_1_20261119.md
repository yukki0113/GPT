# BRDB — SED実馬場別履歴の正規取込 v0.1（研究候補、2026-11-19）

**Status:** 実PACI/SED 5開催日・東京芝2000m対象M7全18頭のv0.3接続再演 PASS（ローカル標準Readerのフィールド投影で予備監査）。GitHubリポジトリ上の正規 `jrdb_raw.py` での実データ統合再演、全期間・全コースの歴史ソース完備性、レビュー/Tips承認は別ゲート。

## 目的

既存 `brdb_condition_discovery.py` の `--going` に、**架空の馬場別サンプルではなく、JRDB公式SEDの実着順・馬場状態を接続**する。

`PACI` は当該開催日の出走馬・血統プロフィール（UKC/KYI）を、対応日の `SED` は確定結果と実馬場状態を持つ。`PACI` から想定馬場を取得したり、後日プロフィールで過去馬の父を推測補完することはしない。

## 正規ソース

- 共通固定長Reader: `horse-racing/jrdb/src/jrdb_raw.py` + `jrdb_ukc.py`。新しいbyte offset parserは追加しない。
- 公式定義: Drive `00_document/jrdb-specifications-oneshot-20261015.zip` 内 `061_sed_doc.txt` / `062_sedsiyo_doc.txt` / `063_sedsoku_doc.txt`。
  - 公式仕様ZIP SHA256: `79bbdf124caafe77e486d68116474713e9b71dda8ee17ce536fc0031fd7b8000`。
  - SED `track_condition_code`: `10/11/12=良`, `20/21/22=稍重`, `30/31/32=重`, `40/41/42=不良`。派生ラベルに畳む一方、コード別出現数をreceiptへ保持。
  - SED `abnormal_code`: `0=異常なし`, `1=取消`, `2=除外`, `3=中止`, `4=失格`, `5=降着`, `6=再騎乗`。**初版は正常完走(0)のみ勝・3着内の分母に含め、その他は除外数に記録。** より一般的な「全出走数」へ一致させるための異常区分ポリシーは別ゲート。
- canonical Drive PACI folder: `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`
- canonical Drive SED folder: `1mm6sU8-skS7K2XYHm2citcorUVyMyL58`
- 出力: `brdb-going-observation-input-v0.1-candidate`（v0.3既存入力契約に互換）。

## 処理契約と不変条件

1. 指定 `--paci-sed PACIYYMMDD.zip SEDYYMMDD.zip` の日付を完全一致。`YYYY-MM-DD < as_of_exclusive`、日付重複不可。
2. 既存 `Parser().kyi() / .ukc() / .sed()` と `iter_archive_records` のみ使用。欠損・破損時はfail-closed。
3. 同日の全SEDとKYIを `(race_key_raw, horse_no, blood_registration_no)` の完全一致で照合。`UKC` は8桁 `horse_id` で完全一致、父名必須。
4. 同日のUKC `data_date` はその開催日と完全一致。元ZIP raw SHAをreceiptへ保存。後日UKCへの黙示fallback禁止。
5. 芝・ダートを混ぜず、対象馬と同じ `surface_code` の実績行だけ出力。取消・中止等は `EXCLUDED`、`finish_position: null`。
6. 公式馬場コードにない値はfail-closed。`11=速良` 等の付帯差は正規出力で良にまとめ、正式ラベル表と元コード別監査値で保持。
7. `source.source_sha256` は**入力ZIP個別SHAではなく**、日付・PACI/SED各ZIP SHAから作る正規化manifestのSHA。`receipt.source_manifest` に個別raw SHAを保持。
8. PWA表示・RaceNote予想・BRDB CURRENTは非接続。`prediction_safe=false`, `research_only=true`。古いM7近親・配合の `AS_OF_UNVERIFIED` は変更しない。

## 実データ予備監査

対象: 2026-11-15 東京12R（芝2000m、18頭）、履歴として以下5日のみ（対象日SEDは一切混ぜない）。

- 2026-10-31, 2026-11-01, 2026-11-07, 2026-11-08, 2026-11-14
- PACI各5件 / SED各5件、合計SED **2,137レコード**。
- 全SED `abnormal`: 正常2,125、取消4、除外1、中止7。
- 対象芝のみ: **1,065件**（正常完走1,063、その他2）。馬場は **良937、稍重128、重0、不良0**。
- これらは5開催日の部分履歴であり、2016–2025を含む父産駒の全履歴ではない。重・不良0は「母集団中の適性ゼロ」ではなく今回取得日付の未観測。
- 同日PACI UKC/KYIとSED全件対応を監査し、対象18頭の父名をキーに既存v0.3へ接続可能。v0.3 JSON Schemaとgoing input JSON SchemaはPASS。
- **検証上の留保:** このローカル実データ再演はGitHub共通Readerの該当フィールドと同じ位置・型を使用した、一時的な読取投影による照合。正式版の `jrdb_raw.Parser` 実動作はGitHub CIでテストし、実5日分の正規Reader直接再演は別途実施すること。

## 正式利用を阻む残ゲート

1. 歴史全期間のSED・同日UKC参照をmanifest単位で揃えたcoverage検証。5日分を全期間の血統成績として誤表示しない。
2. 同じ芝ダート区分でも距離・開催場を分けた比較を追加。現在のv0.3は**全場全距離**集計なので、東京芝2000mの道悪適性を結論しない。
3. `abnormal_code` の分母規則をBRDB既存成績・JRA公式着別度数に合わせた別契約で確定。
4. 研究対象日の時点再現を独立検証（当日UKCを確認できた5日間のjoinと、全履歴の時点保証は別）。
5. 学術的/統計的な有意性や適性、レビュー・Tips文の表現、予想連携は別受入。

## 再演CLI

```bash
python horse-racing/brdb/src/brdb_sed_going_ingest.py \
  --race-json /private/race.json \
  --paci-sed /private/PACI261031.zip /private/SED261031.zip \
  --paci-sed /private/PACI261101.zip /private/SED261101.zip \
  --paci-sed /private/PACI261107.zip /private/SED261107.zip \
  --paci-sed /private/PACI261108.zip /private/SED261108.zip \
  --paci-sed /private/PACI261114.zip /private/SED261114.zip \
  --output /private/real_going_input.json \
  --receipt /private/aggregate_receipt.json
```

`/private` 出力はGitにコミットしない。既存 `src/brdb_condition_discovery.py` の `--going` へ `real_going_input.json` を渡す。
