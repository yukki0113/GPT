# Issue #2212 — PACI UKC監査（集計報告）

Status: **2025–2026年UKC内容の監査完了**（2025年は年次集約ZIP、2026年は保存済みPACI）  
Date: 2026-10-27 JST  
Source main: `19d755988efc10d072789fb0224b1841546ab9b6`

## 入力と走査

#2210 / Actions run `40434315900` / artifact `12703600471` の108 IDを固定し、108行・108 unique・8桁IDを検証。入力SHA-256は `c3361fc60fee3e752b7e34f51b108462dfd8ba10a1b7bfafa63b5bf375acc830`。

Drive canonical folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r` を直接列挙し、91件を取得。すべて2026年の `PACI26*.zip`（2026-01-04〜2026-10-25）で、2025年分は0件。列挙91件はfolder fetchの100件上限より少ない。キーワード検索0件を不存在の根拠には使わなかった。

91/91 ZIPを走査、UKC member 91、39,543レコード、パースエラー0。各ZIPのDrive ID、サイズ、SHA-256、member、レコード数は監査artifactの `paci_inventory_audit.json` に記録した。列挙済みファイルの取得不能・破損は0件。未列挙の日付にファイルが存在しないとは推定しない。

同じ `00_raw` の `UKC/UKC_2025.zip` を別途確認。109 UKC member（2025-01-05〜2025-12-28）、47,239レコードをパースエラー0で走査し、固定108 IDとの一致は0件。ZIP SHA-256は `554f1bf8f72a48b9b6462e1b7d1c4448383ce078c3c9b420006bb21e8558dad5`。ユーザー確認により、この年次ZIPは2025年の日次PACI内UKCをまとめたものとして、UKC内容監査の2025年入力に採用する。2025年PACIコンテナ自体のmetadata/inventoryは監査対象外。

## 108頭の結果

| 判定 | 頭数 |
| --- | ---: |
| 2026年UKCで `horse_id` 完全一致 | 104 |
| `NOT_FOUND_IN_SCANNED` | 4 |
| 合計 | **108** |

104頭は計396回観測。馬名、父・母・母父、生年月日、父系/母父系コードの非空数はいずれも104。semantic profile変更は2頭で、変更列は `owner_name` のみ。血統列変更は0。2026年観測を2025年レース時点の利用可能情報とは扱わない。

BRDB CURRENT generation `eeca93556584a5b8` の既存resolver・祖先グラフで確定canonical IDの接続を監査した結果、父77/104、母77/104、母父12/104。父母それぞれ最大到達世代は0/1/2が父27/62/15、母27/56/21。未解決は既存masterでガードを満たす候補がなく、親名の取得をID解決と混同しない。

## 検証・制限

`PYTHONPATH=/workspace/scratch/brdb-pylibs python -m unittest discover -s horse-racing/brdb/tests -q` → **66 PASS、0 FAIL、0 ERROR**。Python 3.12.14、DuckDB 1.1.3、PyArrow 25.0.1。既存 `jrdb_ukc.parse_ukc_record` と `brdb_parent_relation` / `brdb_ancestor_graph` を使用。

行別108件のJSON・CSV・Parquetと元入力を含む監査ZIPは承認済みのDrive `blood_review` フォルダに保存した。取得リンクは依頼者にこの会話で直接提示する。アップロード後の再取得SHA-256は `8c7d6ac9418a42331db0bccbe9ccf69977352a3c452901a85177f695ca0f81b6` で元ZIPと一致。GitHubブランチにはコード・テスト・集計を置く。2026年UKCでの発見は2025年時点の利用可能性を証明しない。BRDB CURRENT、PWA、Newspaper、RaceNote、Blood Review v0.1は変更していない。
