# 競艇note販売運用台帳 ForwardTrial専用分析台帳

Updated: 2026-09-13

## 目的

`ForwardTrial_Ver0.1` の全レース、真正forward、掲載群を混在させず、結果参照前に固定された予想・販売選別と公式結果を監査可能な形で蓄積する。予想仕様や販売ルールの変更を行う仕組みではなく、検証・集計専用とする。

## 正本と対象

- 正本: Googleスプレッドシート `競艇note販売運用台帳`
- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- 専用タブ: `FT2_` 接頭辞の14タブ
- 初回対象: 2026-09-01、09-02、09-03、09-05、09-06、09-07、09-08（336R）
- 時刻基準: `Asia/Tokyo`

日次の最新累計値や最新記帳日は本書へ固定せず、正本Google Sheetsから都度取得する。

## 入力と結合

必須入力は、日次の公式出走表、事前予想、2連単1点販売選別、公式結果、BOAT RACE公式開催メタの5種類。予想根拠明細は任意の監査資料とする。主キーは `日付×会場×R×仕様版` で、同一キーはupsertし重複を作らない。開催メタは開催日×会場をキーに開催名、グレード大分類、公式source URLをFreezeする。

入力日付、対象会場の全R（各会場12R）、会場集合、キー一意性、仕様版、freeze日時、結果キーのいずれかが不整合ならfail-closedで停止する。結果から予想・販売選別・freezeを補完または変更しない。

## 集計層

- Raw: 仕様上のForwardTrial対象
- Genuine: Rawかつ公式締切予定日時より前にfreeze済み
- Published: Genuineかつ掲載区分が有料または無料

CSVのみはRaw/Genuineの対象になり得るがPublishedには含めない。freezeが締切予定日時以後のレースは `CONTAMINATED` とし、データを削除せず真正forward集計から除外する。

回収額は的中払戻のみとし、返還額は別列で保持する。利益は `回収額 + 返還額 - 投資額`、回収率は集計目的に合わせて的中払戻ベースで算出する。

## タブ構成

1. `FT2_README`
2. `FT2_取込管理`
3. `FT2_開催メタ`
4. `FT2_全R明細`
5. `FT2_日別集計`
6. `FT2_会場別集計`
7. `FT2_会場日目別集計`
8. `FT2_グレード別集計`
9. `FT2_判定構造別集計`
10. `FT2_販売選別検証`
11. `FT2_Score検証`
12. `FT2_Freeze監査`
13. `FT2_ダッシュボード`
14. `FT2_集計監査`

## Atomic Aggregate Set

次の9タブを1世代として扱う。

- `FT2_日別集計`
- `FT2_会場別集計`
- `FT2_会場日目別集計`
- `FT2_グレード別集計`
- `FT2_判定構造別集計`
- `FT2_販売選別検証`
- `FT2_Score検証`
- `FT2_Freeze監査`
- `FT2_ダッシュボード`

`FT2_全R明細` 更新後は、9タブを全GENUINE明細から同一処理で上書き再生成する。一部だけの更新、前日集計値への差分加算を通常運用にしない。

`FT2_集計監査` は各9タブについて、stable key集合から決定する `aggregate_generation_id`、source raw/genuine/contaminated/exacta件数、max対象日、出力行数、検証状態を記録する。9行のgeneration / source件数 / max対象日が一致しない場合は `集計不整合` とし、完了にしない。

## 初回固定受入値

| 指標 | 件数 | 的中 | 投資 | 回収 |
|---|---:|---:|---:|---:|
| 全R | 336 | - | - | - |
| Raw | 81 | 29 | 8,100円 | 7,910円 |
| Genuine | 78 | 29 | 7,800円 | 7,910円 |
| Published | 60 | 23 | 6,000円 | 6,140円 |

追加の固定値は、Genuine利益+110円・回収率101.4%、有料39R/19的中/3,900円→4,930円、無料21R/4的中/2,100円→1,210円、CSVのみ18R/6的中/1,800円→1,770円、構造KPI 59/78→38/59→29/38、締切後freeze 3R（2026-09-03徳山1〜3R）とする。

これらは初回fixtureの回帰値であり、最新累計値ではない。

## 実装の役割分担

### `src/forward_trial_analysis_import.py`

- 日次CSV preflight
- 正規化 / join
- source / date / key / freeze監査
- GENUINE / CONTAMINATED判定
- grade監査
- 派生集計値生成
- aggregate audit用情報生成
- 固定fixture回帰値検査

Google認証・Sheets書込みを持たない。

### `src/forward_trial_chat_ledger.py`

- 既存 `FT2_全R明細` とのfrozen列比較
- stable-key upsert
- 全明細からAtomic Aggregate Set再構成
- `FT2_集計監査` 再構成
- 既存販売台帳 / 販売掲載明細 / 派生view mirror
- connector-neutralな決定論的書込計画生成

認証情報を持たない。

### 接続済みGoogle Drive / Sheets

Work / Chatの接続済みコネクタを認証I/O層として使用する。Driveから日次原本を取得し、Git正本moduleで作った書込計画をネイティブGoogle Sheetsへ反映してread-backする。I/O層へ別の集計・判断ロジックを持たせない。

Googleサービスアカウント、`GPT_GDRIVE_SERVICE_ACCOUNT_JSON`、旧 `run_forward_trial_chat_import.py`、旧台帳import Issue / Actionsは廃止済みであり使用しない。

## 日次完了トランザクション

日次完了はトランザクション境界として扱う。

1. Drive種別別フォルダからracecard / prediction / sales-selection / resultの4原本を固定する。
2. 原本preflight、正規化、source/date/key/freeze/grade監査を行う。
3. `FT2_全R明細` をstable keyでupsertする。
4. `FT2_開催メタ` / `FT2_Freeze監査` を更新する。
5. Atomic Aggregate Set 9タブを全明細から同一generationで全再生成する。
6. `FT2_集計監査` を更新する。
7. 既存販売台帳をmirrorする。
8. Google Sheetsへwriteし、全対象をread-backする。
9. generation/source件数、FT2_ID重複0、掲載=有料+無料、grade、formula error 0を検証する。
10. すべて成功した後だけ `FT2_取込管理=完了` とする。

全R明細upsertだけなら `明細取込済`。本体write中は `集計再生成中`。1枚でも不一致なら `集計不整合`、途中例外は `エラー`、公式grade未解決は `未分類 + 要確認` とする。

再実行時もstable-key upsertと全再生成により件数・投資・回収を二重加算しない。

明細の存在、日別集計に最新日があること、または `FT2_取込管理` の表示だけを単独で完了根拠にしない。

## 開催グレード

`src/fetch_boatrace_event_meta.py` はBOAT RACE公式日別レース一覧だけを参照し、開催名と `一般/G2/G1/SG/その他/未分類` をFreezeする。推測は禁止し、未取得は `未分類 + 要確認` とする。G1/SGを除外せず、グレード別集計に少数標本警告を付ける。

## 予想・販売研究との境界

本分析台帳はControlの記録・集計・監査を担当する。予想ルール・販売ルールを結果後に書き換える仕組みではない。

Shadow-S、PairGate、OpponentScore等の研究候補は `ForwardTrial_司令室運用・会場選別・Shadow検証.md` に従い、真正forward比較とする場合は結果参照前に別version / 別資産としてfreezeする。過去Controlを結果後に並べ替えた分析をShadow forward実績へ混ぜない。

## テスト

```bash
python boat-racing/src/forward_trial_analysis_import.py \
  --manifest source_manifest.json \
  --output forward_trial_analysis.json
python -m unittest discover -s boat-racing/tests -v
```

コード変更時はstable-key idempotency、Atomic Aggregate Setの同世代監査、既存日不変、freeze/grade/source fail-closedを回帰確認する。
