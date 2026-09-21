# keirin context

## Goal

競輪の5〜10年Historical基盤を構築し、独自予想ロジックの研究・検証へ利用する。生データ自体の販売・転載を目的としない。

## Source rule

- 公開ページで閲覧できる、URLが規則的、HTML取得できる、だけでは正式sourceにしない。
- 自動取得、長期保存、内部商用分析（有償note予想の生成を含む）に使える条件を確認してから approved に昇格する。
- source未承認時にbulk crawlを開始しない。
- 正式source決定後もアクセス間隔、robots、利用条件、取得時点をauditへ記録する。

## Current source review (2026-09-22)

- WINTICKET: Historical到達性・項目は良好。ただし現行利用規約に営利目的利用およびプログラム等の解析行為に関する禁止規定があるため正式sourceにしない。
- KEIRIN.JP: 公式一次情報。サイトポリシーは私的使用/引用等を除く複製・転用を制限し、私的利用を超える無断利用で第三者から対価を得ることを断っている。許諾なしのbulk commercial sourceにはしない。
- OddsPark: Historical到達性はあるが、サイトポリシーが私的使用以外の無断複製等を広く禁止。正式sourceにしない。
- 楽天Kドリームス: Historicalのライン・コメント等は有用だが、サイト利用条件が私的使用・無断転載/コピー等を制限。正式sourceへの昇格は許諾確認が必要。
- KeirinDB: 年次CSV販売を確認。2022〜2025等が存在し、レース/出走/結果/払戻を収録するがライン無し。購入条件・派生利用許諾・対象年数を確認して補助候補とする。

## Engineering rule

keirin_historical.raw はprovider-neutral。各source recordの policy_status=approved を必須とし、未承認sourceにはHTTPアクセスしない。
