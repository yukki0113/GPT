# M6-7 初期実装：完全レシピ表示と採否理由（2026-11-12）

## 到達点

- `engine_m6/deck_review.py`: SHAピンされた非公開SQLiteから**実際に構築された候補の各MAIN/EXカード**を日本語名、採用枚数、MDレアリティ、所持既知状態、採用理由、根拠ID付きで返す。
- 登録済み所持台帳の採否を全件照合し、見送り理由もカード名付きで表示。未登録所持を0枚と推定しない。
- MAIN/EXの枚数、候補ID、カード存在、DB原本SHA、候補と所持監査の世代整合が一致しなければfail-closed。
- `recipe_markdown`でMAIN/EX一覧と登録済み所持カード全件の見送り一覧を作成。
- `make_private_review_archive`でJSON/Markdown入りの別ZIPとSHA manifestのバイト列を決定的に生成。実デッキ個票は**private Driveにのみ保存**し公開Git/CIには載せない。
- `integration.integrate_private_deck`で新規生成候補がある場合に`full_reviews`, `review_markdowns`, `review_archive`, `review_manifest_raw`を返す。旧M6-5のproposal ZIPはそのまま残す。
- `tests/test_m6_7.py`に架空データの回帰を追加。

## 受入状況と残課題

**コード反映済み、実Generation5のM6-6再実行・Drive新規アーカイブ保存・独立読み戻しは未実施。したがってM6-7受入PASSではない。**

既存M6-6 ZIPは候補カード詳細を保存しておらず、後から特定レシピを完全復元できない。新たな実行では最新HEADを前後で取得し、最新DB/sidecar/CPのSHAを照合して統合処理を再実行する。返された`review_archive`と`review_manifest_raw`を**新規名**でprivate Driveへ保存し、それぞれSHA/bytesの独立読み戻しを確認する。過去アーカイブは上書きしない。

`selection_reason`は構築時の暫定注釈を正確に転記したものであり、効果やルートの実戦検証を意味しない。単に採用候補であることを「採用理由が戦術的に正しい」と言い換えない。残りM6-7では軍貫の実効性、現行MD規制、素材・ロック・初動・EX1枠と他テーマの実利用受入を継続する。
