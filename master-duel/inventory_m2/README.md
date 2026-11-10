# M2 所持入力とDrive HEAD切替の安全ゲート

基準日: 2026-11-10。既存の P1 SQLite、P2 zip_store、P3 voice_staging を再利用し、不足していた正本HEAD・ZIP結合と昇格前検証を追加する。ここにあるPythonモジュールは**Driveを書き換えない**。外部から正本を取得・保存する作業は、接続済みGoogle Driveの操作で別途行う。

## 公開API

- validate_head / target_from_head：scope、writer_policy、世代、スナップショットID・DriveファイルID、ZIP/DB SHA、SQLite整合性を確認。
- preview_inventory：入力したカード名を正規化照合し、現在値と更新後を表示。未解決、曖昧、重複は全体保留。
- prepare_inventory：本人確認後のpreview SHAとバッチを再照合し、既存P3/P2を通してプライベートな候補ZIPを生成。保存やHEAD切替は行わない。
- build_verified_head：元HEAD再観測、元ZIP、バックアップ独立取得、新ZIP独立取得、各SHA・schema・SQLite整合性、件数・ファイルID独立性を確認して、HEAD**提案**JSONだけを生成。
- verify_activated_head：操作者がDriveにHEADを書き込み、別要求で再取得した結果が提案と完全一致するか検査。

## 正本の保存手順（単一ライター限定）

1. Google Driveの GPT/MasterDuel/DB/ を一覧し、MD_CURRENT_HEAD.jsonを取得。名称検索で0件でも、フォルダを列挙して確認。HEADに記載の実ZIPを取得して target_from_head で検証。
2. 所持申告があったカードのみバッチ化。18件の優先候補は質問の候補であり、未回答の枚数をDBへ書かない。CSVならヘッダー raw_name,owned_count を用いる。UNKNOWNを確認済0枚と混同しない。
3. preview_inventory でカード名・枚数・差分を本人が確認し、承認後に prepare_inventory にpreview SHAを渡す。出張は現段階では個々の構成カードを登録し、パッケージ定義はM5で追加。
4. Drive上で元ZIPの**新規バックアップ**を作成して独立取得。候補ZIPも**元を上書きせず新規保存**し独立取得。2つの異なる新規Drive IDを控える。
5. HEADを再取得して変更がないと確認し、build_verified_headで提案を構築。原本HEAD自体も別名でバックアップし、**単一ライターを維持**して直前にもう一度HEADと世代を確認してから既存HEADを書き換える。Driveにatomic CASがないため、読取と書込間の競合は防げない。
6. 別API要求でHEADを再取得し verify_activated_head で確認。新HEADが指すZIPも独立取得し、SHAとSQLiteを検証。通信不明・競合・不一致では成功と扱わない。旧HEAD・旧ZIP・バックアップを保全して調査する。

## 安全境界・残工程

公開GitHubはコード・架空データ・件数と非秘密ハッシュの監査だけ。日本語効果全文、個人の実所持枚数、実DBはDriveの非公開正本に限定する。プレビューSHAは**人の確認の証明ではない**ので承認の判断は操作者が行う。本実装はP2の保存を代行せず、Drive CAS・強制単一ライターを提供しない。実数登録は本人の申告が必要。禁止制限との合算はM3、出張構成はM5、テーマ発掘はM6。

テスト: master-duelディレクトリで python -m unittest discover -s inventory_m2/tests -v
