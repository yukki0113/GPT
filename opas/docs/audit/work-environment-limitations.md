# OPAS Work調査環境上の制約

更新日: 2026-10-09

## 結論

ChatGPT Workの調査用ブラウザからOPASへ直接接続したところ、ログイン前画面へ到達する前のTLS接続段階で失敗した。

確認したURL:

- https://reserve.opas.jp/osakashi_ren/Welcome.cgi
- https://reserve.opas.jp/osakashi/Welcome.cgi

両方で確認された結果:

- `502 Bad Gateway`
- `OpenSSL Error: unsafe legacy renegotiation disabled`

## 扱い

- この結果だけでOPASサイト自体の障害とは断定しない。
- 認証情報の問題ではない。ログイン画面到達前に失敗している。
- TLS検証の無効化、認証回避、互換性を強制する迂回策は行わない。
- Workブラウザによる実機UI調査は現時点で利用しない。
- 実機一次資料はユーザー端末で取得したスクリーンショット・操作記録を使用する。
- Workは公開資料調査、取得済み証拠の整理、設計・独立デモ作業に利用する。

## セキュリティ・運用原則

- ID、パスワード、暗証番号をChat、Git、成果物へ記載しない。
- 予約確定、取消、利用者情報変更、更新申請、メール送信等の状態変更を自動化しない。
- 大量アクセス、スクレイピング、認証回避、非公開API探索を行わない。
