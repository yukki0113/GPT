# JRDB Common Raw Reader v0.1

## 1. 目的

中央競馬プロジェクトで JRDB Raw / PACI を読む固定長処理を、RaceNote・Eval・PWA・検証/指数開発から独立した共通責務へ移す。

共通基盤の正本は SQLite ではなく、以下の2点とする。

1. **データ原典:** JRDB Raw / PACI
2. **読み方の正本:** `src/jrdb_raw.py`

Consumer ごとの SQLite / CSV / JSON は、Common Raw Reader から生成される派生物として扱う。

```text
JRDB Raw / PACI
      |
      v
Common JRDB Raw Reader
      |
      +-- RaceNote formatter
      +-- Eval enrichment
      +-- PWA/index builder
      +-- Raw history access
```

## 2. v0.1 の責務

`src/jrdb_raw.py` は次のみを担当する。

- CP932 固定長 field 読み取り
- 1-based byte offset による field parse
- race key / race-horse key / result key の生成
- PACI の CRLF 込み固定長形式と、annual Raw の line body 形式の両方の分割
- BAC / KYI / CHA / CYB / SED / SKB / ZED / ZKB / UKC の neutral parse
- ZIP 内の canonical member 列挙
- record-length audit

以下は担当しない。

- JRDB code の日本語 label 化
- RaceNote の JSON grouping / token compression
- Eval 固有列への変換
- PWA index / Ability / Edge 等の特徴量生成
- 予想ロジック

## 3. SED/ZED・SKB/ZKB

JRDB 固定長定義では、ZED は SED と同一フォーマット、ZKB は SKB と同一フォーマットとされる。

そのため Common Reader では、

- `Parser.sed()` と `Parser.zed()`
- `Parser.skb()` と `Parser.zkb()`

を同一 byte layout として扱う。

Consumer 側は「今走結果」か「提供済み前走」かという意味上の違いを、source kind / as-of policy で管理する。

## 4. race key の扱い

レースキーの `日` は JRDB 仕様上 TYPE F（16進数1桁）を取り得る。

したがって、Common Reader は race key を文字列のまま保持し、`day_raw` を10進数へ強制変換しない。

## 5. annual Raw history access

`src/jrdb_raw_history.py` は Common Reader 上の最初の横断アクセス層である。

### `get_horse_runs()`

```python
get_horse_runs(
    raw_root,
    horse_id,
    before="2026-09-06",
    limit=8,
)
```

動作:

1. `before` は排他的上限とする。
2. 新しい年から SED annual ZIP を見る。
3. ZIP 内 member も新しい日から見る。
4. horse_id / date は固定位置で先に filter する。
5. 一致行だけ `Parser.sed()` で parse する。
6. `limit` 件集まった時点で走査を終了する。
7. archive / member / year の provenance を返す。

このモジュールは Canonical SQLite を必須依存にしない。

将来、Raw 横断検索量が増えた場合は `horse_id -> year/member/offset` だけを持つ小型 locator index を追加してよい。ただし Raw 本体の代替 DB にはしない。

## 6. 精度再監査

v0.1 では以下を再確認した。

### 仕様突合

- KYI record length: 1024 bytes（CR/LF含む）
- BAC: 現行実データは 184 bytes（CR/LF含む）
- CHA: 64 bytes
- CYB: 96 bytes
- SED/ZED: 376 bytes
- SKB/ZKB: 304 bytes
- UKC body: 290 bytes（ZIP内固定長では CR/LF を含め292 bytesとして扱う）
- KYI previous result links: relative 204/220/236/252/268
- KYI previous race links: relative 284/292/300/308/316
- race key の `日` は文字列保持
- numeric field は負号を許容

### 2024 annual Raw 実データ走査

Drive 上の2024年 annual Rawを用い、Common Readerで全件走査した。

| kind | records | length errors |
|---|---:|---:|
| BAC | 3,454 | 0 |
| KYI | 47,181 | 0 |
| SED | 47,181 | 0 |
| CHA | 47,181 | 0 |
| CYB | 47,181 | 0 |
| SKB | 47,181 | 0 |
| UKC | 47,181 | 0 |

### characterization tests

`tests/test_jrdb_raw_common.py`

- BAC/KYI byte offsets
- previous 1-5 link position
- signed numeric parse
- SED=ZED / SKB=ZKB compatibility
- UKC parse
- PACI CRLF block / annual line-body split
- malformed record-length audit
- cross-year horse history / before-exclusive leakage guard

`tests/test_jrdb_raw_racenote_compat.py`

- current RaceNote `Parser` と Common `Parser` の BAC/KYI/ZED/ZKB parsed dict 完全一致を固定する。

## 7. 移行方針

v0.1 の追加時点では、既存 production consumer の import は変更しない。

移行は次の順序で行う。

1. Common Reader characterization test を固定
2. RaceNote `racenote_jrdb.py` の固定長 helper / `Parser` を Common Reader import に置換
3. RaceNote base schema v0.2 semantic regression
4. Eval PACI enrichment の `Parser` / fixed-record reader を Common Reader へ置換
5. PWA/index builder の重複 parser を段階的に置換
6. 必要に応じて history locator index を追加

**Parser 共通化と RaceNote schema変更は同時に行わない。**

## 8. SQLite の位置づけ

全面 Canonical SQLite は Common Reader の必須層にしない。

今回の2024 PoCでは SQLite SELECT 自体は高速だったが、Drive からの取得・展開を含む通常の1R利用では Raw 直読に対して劇的なE2E優位は確認できなかった。

一方、PWA・指数開発など大量反復検索では Consumer 専用 SQLite が有効である。

したがって今後も、

```text
Raw -> Common Reader -> Consumerに必要な最小DB/JSON/CSV
```

を基本とする。
