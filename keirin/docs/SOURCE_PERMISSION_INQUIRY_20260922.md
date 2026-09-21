# Keirin Historical data permission inquiry — 2026-09-22

## Primary inquiry route

KEIRIN.JP / JKA の一般問い合わせ窓口を第一候補とする。

- E-mail: webmaster@keirin-autorace.or.jp
- 目的: 公開ページのスクレイピング許可だけを尋ねるのではなく、Historical分析用データの正式な提供・利用許諾ルートが存在するか確認する。
- JKAの競輪情報システム部は、競輪情報システムの運用管理・レース結果等の情報蓄積管理を所管しているため、必要に応じて適切な担当部署への転送を依頼する。

## Inquiry points

1. 過去5〜10年程度の競輪レースについて、出走表・選手情報・レース結果・払戻等のデータを研究/分析用途で利用する正式な提供方法があるか。
2. ライン/並び情報、選手コメント等の事前情報を含む提供方法があるか。
3. 公開Webページから機械的に取得することが許可される場合、許可される対象・頻度・保存期間・アクセス条件は何か。
4. 取得データを非公開の分析DBへ長期保存できるか。
5. データそのものを転載・再販売せず、独自に算出した予想指数・印・分析結果を有料note等で提供する用途に利用できるか。
6. 利用申請、契約、料金、クレジット表記等が必要か。
7. JKAが直接提供していない場合、正式にデータ提供を受けられる事業者・窓口があるか。

## Draft inquiry

Subject: 競輪の過去レース情報の分析利用・データ提供可否について

公益財団法人JKA ご担当者様

競輪の過去レースデータを用いた個人のデータ分析・予想研究を検討しており、データの正式な利用方法について確認したくご連絡いたしました。

想定している用途は、過去5〜10年程度の出走表、選手情報、レース結果、払戻、可能であればライン・並び等の事前情報を、非公開の分析用データベースに保存し、独自の予想ロジックや指数の研究・検証に利用するものです。

取得した出走表や数値データそのものを転載・再配布・販売する予定はありません。一方、将来的に、これらのデータを内部分析に用いて独自に算出した予想印・指数・分析結果のみを、有料note等で提供する可能性があります。

KEIRIN.JPのサイトポリシーに、私的利用の範囲を超えた無断利用についての記載があることは確認しております。そのため、無断での大量取得を行うのではなく、以下について正式な方法をご教示いただけますでしょうか。

- 過去レース情報を分析用途で利用できるデータ提供・契約・申請制度の有無
- 公開Webページからの自動取得が認められる場合の条件
- 非公開DBへの長期保存の可否
- 生データを公開せず、独自分析結果のみを有償提供する用途での利用可否
- JKA様から直接提供されていない場合、問い合わせるべき正式なデータ提供事業者・窓口

もし本件の担当部署が別にございましたら、お手数ですが適切な窓口をご案内いただけますと幸いです。

よろしくお願いいたします。

## Decision rule after reply

- explicit permission / licensed route confirmed -> source adapter implementation and one-month full Raw PoC
- permission requires contract -> obtain terms/cost/coverage before implementation
- public page automation denied but licensed dataset introduced -> use licensed dataset
- no official/licensed route -> do not bulk crawl restricted public sites; re-evaluate project data strategy
