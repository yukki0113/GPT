# keirin context

## Goal

競輪の5〜10年Historical基盤を構築し、独自予想ロジックの研究・検証へ利用する。生データ自体の販売・転載を目的としない。

## Source rule

- 公開ページで閲覧できることだけでは正式sourceにしない。
- 自動取得・保存・利用条件を確認し、用途ごとの許諾状態を明示する。
- 原本・正規化しただけのデータは外部配布・販売しない。
- 取得済みRawは再取得を避け、アクセス負荷を最小化する。
- 429/403/5xxの増加、明示的なアクセス制限、サービス支障の兆候があれば停止する。

## KEIRIN.JP inquiry result (user-provided, 2026-09-22)

回答要旨:
- 加工データの提供はない。
- データそのもの、または正規化しただけのデータの配布・販売は禁止。
- 個人の予想への使用は個人利用の範疇として許可。
- 機械取得は明確な禁止ではないが、サービス提供に支障があるアクセスと判断された場合はサーバアクセスを制限する場合がある。

Project interpretation:
- Historical取得・非公開保存・個人予想研究: personal_research_approved
- Raw / normalized data redistribution or sale: prohibited
- 独自予想印・指数等の有料販売: commercial_output_pending
- automated acquisition: conservative rate-limited access only; no circumvention

## Technical findings

- https://keirin.jp/pc/raceschedule?scym=MM&scyy=YYYY は2016年HistoricalでもHTTP 200。
- 旧Dataplaza raceprogram / raceresult は2016年例でHTTP 500のため新collectorでは使用しない。
- 月間日程の各開催セルには /pc/racelist 向け encp があり、公式JS PJ0201.js は encp + disp=PJ0301/PJ0302 をPOSTする。
- 2016-01いわき平のPOST遷移はHTTP 200。返却HTMLには開催日・各Rナビゲーション・出走表一覧・結果一覧に相当するHistorical情報が含まれる。
- よって月次Raw PoCは「月間日程1 GET + 開催ごと1 POST」を基本とし、レースごとの大量アクセスは行わない。
