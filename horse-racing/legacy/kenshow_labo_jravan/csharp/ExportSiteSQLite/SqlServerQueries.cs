namespace ExportSiteSQLite
{
    /// <summary>
    /// SQL Server 抽出SQL群。
    /// </summary>
    public static class SqlServerQueries
    {
        /// <summary>
        /// dim_race（過去：結果あり）を VW_RaceResultContract から作る。
        /// </summary>
        public const string DimRaceHistory = @"
            SELECT
                v.race_id                                  AS race_id
                , CONVERT(char(10), v.[日付], 23)            AS race_date
                , v.jyo_cd                                   AS jyo_cd
                , CAST(v.race_no AS int)                     AS race_no
                , MAX(v.[レース名])                          AS race_name
                , MAX(v.[場名])                              AS track_name
                , MAX(v.[芝/ダ])                             AS surface_type
                , MAX(CONVERT(int, v.[距離]))                AS distance_m
                , MAX(v.[クラス])                            AS class_simple
                , MAX(CONVERT(int, v.WIN5_flg))              AS win5_flg
            FROM dbo.VW_RaceResultContract AS v
            WHERE v.[日付] BETWEEN @from_date AND @to_date
            AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
            GROUP BY
                v.race_id
                , v.[日付]
                , v.jyo_cd
                , CAST(v.race_no AS int)
            ORDER BY
                v.[日付] DESC
                , v.jyo_cd
                , CAST(v.race_no AS int);
        ";

        /// <summary>
        /// fact_race_result（過去）を VW_RaceResultContract から作る。
        /// </summary>
        public const string RaceResultHistory = @"
            SELECT
                v.race_id                                  AS race_id
                , CAST(v.horse_id AS nvarchar(32))           AS horse_id
                , v.[馬名]                                   AS horse_name
                , TRY_CONVERT(int, v.[馬番])                 AS umaban
                , TRY_CONVERT(int, v.[枠番])                 AS wakuban
                , TRY_CONVERT(int, v.[着順])                 AS finish_pos
                , CASE
                      WHEN v.[走破時計] IS NULL THEN NULL
                      ELSE CONVERT(varchar(12), v.[走破時計], 108)
                  END                                        AS time_text
                , CAST(NULL AS nvarchar(50))                 AS margin_text
                , v.[騎手]                                   AS jockey_name
                , TRY_CONVERT(decimal(4,1), v.[斤量])         AS weight_carried
                , TRY_CONVERT(decimal(10,2), v.[オッズ])       AS odds
                , TRY_CONVERT(int, v.[人気])                 AS popularity
            FROM dbo.VW_RaceResultContract AS v
            WHERE v.[日付] BETWEEN @from_date AND @to_date
            AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
            ORDER BY
                v.race_id
                , TRY_CONVERT(int, v.[着順])
                , TRY_CONVERT(int, v.[馬番]);
        ";

        /// <summary>
        /// fact_payout（MVP: 単勝/複勝）を VW_RaceResultContract から作る。
        /// 注意：複勝3頭分の正規化は TR_Payout の構造確認後に拡張する。
        /// </summary>
        public const string PayoutHistoryWinPlace = @"
            WITH P AS
            (
                SELECT
                    v.race_id                     AS race_id
                    , N'単勝'                       AS bet_type
                    , CAST(v.[馬番] AS nvarchar(20)) AS combo_text
                    , TRY_CONVERT(int, v.[単勝払戻]) AS payout_yen
                    , TRY_CONVERT(int, v.[単勝人気]) AS popularity
                FROM dbo.VW_RaceResultContract AS v
                WHERE v.[日付] BETWEEN @from_date AND @to_date
                AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
                AND v.[単勝払戻] IS NOT NULL

                UNION ALL

                SELECT
                    v.race_id                      AS race_id
                    , N'複勝'                        AS bet_type
                    , CAST(v.[馬番] AS nvarchar(20)) AS combo_text
                    , TRY_CONVERT(int, v.[複勝払戻]) AS payout_yen
                    , TRY_CONVERT(int, v.[複勝人気]) AS popularity
                FROM dbo.VW_RaceResultContract AS v
                WHERE v.[日付] BETWEEN @from_date AND @to_date
                AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
                AND v.[複勝払戻] IS NOT NULL
            )
            SELECT race_id, bet_type, combo_text, payout_yen, popularity
            FROM P
            WHERE payout_yen IS NOT NULL
            ORDER BY race_id, bet_type, combo_text;
        ";

        /// <summary>
        /// dim_race（週末：出馬表あり）を VW_RaceEntryContract から作る。
        /// </summary>
        public const string DimRaceWeekend = @"
            SELECT
                v.race_id                                   AS race_id
                , CONVERT(char(10), v.[日付], 23)             AS race_date
                , v.jyo_cd                                    AS jyo_cd
                , CAST(TRY_CONVERT(int, v.[R]) AS int)        AS race_no
                , MAX(v.[レース名])                           AS race_name
                , MAX(v.[競馬場名])                           AS track_name
                , MAX(v.[芝／ダ])                             AS surface_type
                , MAX(TRY_CONVERT(int, v.[距離]))             AS distance_m
                , MAX(v.[クラス])                             AS class_simple
                , MAX(CASE WHEN v.[race_id] IS NOT NULL THEN 0 ELSE 0 END) AS win5_flg
            FROM dbo.VW_RaceEntryContract AS v
            WHERE v.[日付] BETWEEN @from_date AND @to_date
            AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
            GROUP BY
                v.race_id
                , v.[日付]
                , v.jyo_cd
                , v.[R]
            ORDER BY
                v.[日付]
                , v.jyo_cd
                , TRY_CONVERT(int, v.[R]);
        ";

        /// <summary>
        /// fact_race_entry（週末）を VW_RaceEntryContract から作る。
        /// </summary>
        public const string RaceEntryWeekend = @"
            SELECT
                v.race_id                                   AS race_id
                , CAST(v.horse_id AS nvarchar(32))            AS horse_id
                , v.horse_name                                AS horse_name
                , TRY_CONVERT(int, v.horse_no)                AS umaban
                , TRY_CONVERT(int, v.frame_no)                AS wakuban
                , v.jockey_name                               AS jockey_name
                , CAST(NULL AS nvarchar(50))                  AS trainer_name
                , TRY_CONVERT(decimal(4,1), v.carried_weight) AS weight_carried
            FROM dbo.VW_RaceEntryContract AS v
            WHERE v.[日付] BETWEEN @from_date AND @to_date
            AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
            ORDER BY v.race_id, TRY_CONVERT(int, v.horse_no);
        ";

        /// <summary>
        /// fact_race_expectation（週末）を TR_RaceExpectation から作る（race_id は週末対象に限定）。
        /// </summary>
        public const string ExpectationWeekend = @"
            SELECT
                t.race_id                                   AS race_id
                , TRY_CONVERT(int, t.horse_no)                AS umaban
                , CAST(t.horse_id AS nvarchar(32))            AS horse_id
                , t.horse_name                                AS horse_name
                , TRY_CONVERT(decimal(9,6), t.ability)        AS ability
                , TRY_CONVERT(decimal(9,6), t.mult_course)    AS mult_course
                , TRY_CONVERT(decimal(9,6), t.mult_style)     AS mult_style
                , TRY_CONVERT(decimal(9,6), t.mult_frame)     AS mult_frame
                , TRY_CONVERT(decimal(9,6), t.mult_blood)     AS mult_blood
                , TRY_CONVERT(decimal(9,6), t.mult_jockey)    AS mult_jockey
                , TRY_CONVERT(decimal(9,6), t.expected_raw)   AS expected_raw
                , TRY_CONVERT(decimal(9,2), t.expected_100)   AS expected_100
            FROM dbo.TR_RaceExpectation AS t
            WHERE t.race_id IN
            (
                SELECT DISTINCT v.race_id
                FROM dbo.VW_RaceEntryContract AS v
                WHERE v.[日付] BETWEEN @from_date AND @to_date
                AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
            )
            ORDER BY t.race_id, TRY_CONVERT(int, t.horse_no);
        ";

        /// <summary>
        /// dim_horse_pedigree（週末出走馬限定）を MT_HorsePedigree から作る。
        /// </summary>
        public const string PedigreeWeekendOnly = @"
            SELECT
                CAST(p.horse_id AS nvarchar(32)) AS horse_id
                , p.sire                           AS sire
                , p.dam                            AS dam
                , p.sire_sire                      AS siresire
            FROM dbo.MT_HorsePedigree AS p
            WHERE p.horse_id IN
            (
                SELECT DISTINCT v.horse_id
                FROM dbo.VW_RaceEntryContract AS v
                WHERE v.[日付] BETWEEN @from_date AND @to_date
                AND v.jyo_cd IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@jyo_cds, ','))
                AND v.horse_id IS NOT NULL
            );
        ";
    }
}
