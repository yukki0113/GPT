# BRDB M6 — RaceNote v0.5.6 Freeze再利用・P1-7前向きデータ受入境界（2026-11-04）

## 現状

**2026-10-10／11の旧v0.5.2予想JSON：未発見。48レースの台帳上のFreezeラベルだけでは、予測値の同時点証拠にはならない。P1-7予測改善検証はHOLD。**

既存の検証台帳には2026-10-10／11、各24Rの合計48Rについて`TRUE_FORWARD`、`PRE_RESULT_FROZEN`が記録されているが、元予想JSON本体、時点の独立証明および確率予測は確認できていない。現在の正本Google Drive `GPT/horse-racing/00_raw` の `predictions/archive` は競艇向け月次保存物で、RaceNoteの当日予想原本ではない。Driveの`racenote/archive/provisional`を辿っても旧日次元JSONは確認できず、GitHub Issueの存在も具体的な元JSONのByte証明ではない。検索MISSを「不存在」と断定しない。

## 既存RaceNote v0.5.6の正本機構を利用する

現行 `horse-racing/jrdb/docs/racenote/RACENOTE_V056_FORWARD_PACI_RUNTIME_20261030.md` および `src/racenote_v056_single_day.py` に準拠する。

1. 開催前、受入済みPACIと市場／結果が混入していないReaderを用意。
2. RaceNote既存Prediction Freeze `daily/YYYYMMDD/v056_day/v056/frozen/records.json` と `day_handoff.json` を作成／main反映。これはRaceNoteだけが担う。
3. 既存Confidence Freezeは別工程。BRDBは予想著述・Freeze・Confidenceを書き換えない。
4. BRDB研究ではGitHub上の実物Freezeを**read-only**で取り込み、`src/audit_brdb_m6_v056_freeze_evidence.py` によりschema/status/market-blind/未結果閲覧／SHA／race・horse rosterの構造を照合する。
5. GitHub API上の該当コミット作成時刻、推奨はGitHub Actionsとmain永続化完了時刻、発走時刻、Freeze内容の同一バイト、事前特徴の入手可能性を**独立した外部監査**で確認する。入力JSONに`timestamp`や`signed_source_attestation=true`を書くだけでは足りない。
6. 研究候補の馬別確率は**別個の研究用レコード**にする。既存v0.5.6の印・Confidenceを勝率に勝手に換算せず、現在のRaceNoteの既存出力に`p_win`があるとみなさない。

## 研究用ペア確率の契約（候補）

`brdb-p1-7-pre-race-pairs-v0.1` JSONは`target_date`、`prediction_safe=false`、`source_freeze_records_sha256`を持ち、各レースの全頭に`venue`、`race_no`、`horse_no`、`p_baseline`（非血統）と`p_blood_challenger`（血統追加）を持つ。値は有限の0〜1間で、各レースの合計を両モデルそれぞれ1にする。対象馬の過不足・重複・Freeze不一致をすべて拒否する。

実モデルの事前予測がないときはファイルを作成しない。合成Fixtureを過去予測として流用しない。後から実際の着順を見て印を勝率に変換しない。

実在する`p_baseline`/`p_blood_challenger`があっても**この受入モジュールは必ず`prediction_safe=false`、`p1_7_log_loss_evaluable=false`**を返す。外部サービスの配信・保存時刻や学習時点の真正性は実ファイルだけでは証明できない。今後別の独立監査と予測モデル受入を追加しなければ実測比較しない。

## テスト／安全境界

- `src/audit_brdb_m6_v056_freeze_evidence.py`：RaceNote現行Freezeを変更しない構造・SHA検査。CLIは`--v056-root`、任意`--pairs`、`--out`、`--require-prediction-safe`。
- `tests/test_audit_brdb_m6_v056_freeze_evidence.py`：**合成データだけ**を使う5件の回帰テスト。SHA改変拒否、結果閲覧済み・馬番重複拒否、確率合計・馬の欠損拒否、自己申告証明による昇格拒否。
- BRDB CURRENT、Blood Score、RaceNote、PWA、新聞、馬券予想への変更は禁止。**予測差分の統計結果はまだない。**

## 今後の必要手順

- 次回の開催前v0.5.6 forward日に、実PACIから既存T1→Prediction Freeze→Confidence Freezeの監査済み証跡を作る。ただし前向き運用自体はRaceNoteの既存専用担当が行い、BRDBが自動で起動しない。
- 完全な非血統ベースラインの**馬別確率**が既存運用に存在するか独立確認し、なければ新たなモデル・別系統の確率校正と事前Freezeの設計審査を行う。既存Confidence=A/B/Cは勝利確率ではない。
- さらに血統追加モデルについて、時点安全な血統特徴・学習分割・馬IDの完全一致がある場合に限りペア評価を開始。
- 2016〜2025年のpre-race血統証跡は依然0件で、P1-5血統効果・P1-6複数年度ウォークフォワード・P1-7追加価値の予測効果はすべてHOLD。

## 実装検証（2026-11-04）

- 固定ソースコミット：`ed6934828a478557fec02f5c71060bb687e6d218`。
- [Issue #2393](https://github.com/yukki0113/GPT/issues/2393)：`DATA_STORAGE_FALLBACK_RESULT status=PASS`。
- [GitHub Actions run #41782618778](https://github.com/yukki0113/GPT/actions/runs/41782618778)：job `completed/success`、artifact `data-storage-fallback-41782618778`を確認。合成回帰テスト5件PASS。
- 実データのv0.5.6前向きPrediction Freeze・元JSON・馬別確率の新規監査は実行していない。テスト合格は**将来の受入検査機能の合格**であり、予測データの利用資格やP1-5/6/7予測の完了ではない。
