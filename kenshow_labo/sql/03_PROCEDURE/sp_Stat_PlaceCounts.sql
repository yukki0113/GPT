CREATE OR ALTER PROCEDURE dbo.sp_Stat_PlaceCounts
(
      @region          NVARCHAR(10) = N'ALL'   -- 'CENTRAL' / 'LOCAL' / 'ALL'
    , @date_from       DATE         = NULL
    , @date_to         DATE         = NULL     -- 期間終端（含む）
    , @jyo_cd          CHAR(2)      = NULL
    , @grade_cd        CHAR(2)      = NULL
    , @surface         NVARCHAR(1)  = NULL     -- '芝' / 'ダ'
    , @race_name_like  NVARCHAR(100)= NULL     -- 例: N'有馬記念'

    -- WHERE追加
    , @distance_from   SMALLINT     = NULL     -- 距離FROM（含む）
    , @distance_to     SMALLINT     = NULL     -- 距離TO（含む）
    , @baba_text       NVARCHAR(20) = NULL     -- 馬場状態（例：N'良', N'稍重', N'重', N'不良'）
    , @win5_flg        TINYINT      = NULL     -- 0/1（NULLなら条件なし）

    , @min_starts      INT          = 1
)
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH Src AS
    (
        SELECT
              N'CENTRAL' AS region
            , v.race_id
            , v.[日付]
            , v.[レース名]
            , v.jyo_cd
            , v.grade_cd
            , v.WIN5_flg
            , v.[芝/ダ]
            , v.[距離]
            , v.[馬場]
            , v.[枠番]
            , v.[騎手]
            , v.[父]
            , v.[脚質]
            , v.[着順]

            -- 切り口追加に必要な列
            , v.[性]
            , v.[齢]
            , v.[人気]
            , v.[斤量]
            , v.[馬体重]
            , v.horse_id
        FROM dbo.VW_RaceResultContract AS v

        UNION ALL

        SELECT
              N'LOCAL' AS region
            , v.race_id
            , v.[日付]
            , v.[レース名]
            , v.jyo_cd
            , v.grade_cd
            , v.WIN5_flg
            , v.[芝/ダ]
            , v.[距離]
            , v.[馬場]
            , v.[枠番]
            , v.[騎手]
            , v.[父]
            , v.[脚質]
            , v.[着順]

            -- 切り口追加に必要な列
            , v.[性]
            , v.[齢]
            , v.[人気]
            , v.[斤量]
            , v.[馬体重]
            , v.horse_id
        FROM dbo.VW_RaceResultContract_Local AS v
    )
    SELECT
          s.region
        , s.race_id
        , s.[日付]
        , s.[レース名]
        , s.jyo_cd
        , s.grade_cd
        , s.WIN5_flg
        , s.[芝/ダ]
        , s.[距離]
        , s.[馬場]
        , s.[枠番]
        , s.[騎手]
        , s.[父]
        , s.[脚質]
        , s.[着順]

        -- ② 切り口追加に必要な列
        , s.[性]
        , s.[齢]
        , s.[人気]
        , s.[斤量]
        , s.[馬体重]
        , s.horse_id
    INTO #Base
    FROM Src AS s
    WHERE
            (@region = N'ALL' OR s.region = @region)
        AND (@date_from IS NULL OR s.[日付] >= @date_from)
        AND (@date_to   IS NULL OR s.[日付] < DATEADD(DAY, 1, @date_to)) -- 終端含む
        AND (@jyo_cd    IS NULL OR s.jyo_cd = @jyo_cd)
        AND (@grade_cd  IS NULL OR s.grade_cd = @grade_cd)
        AND (@surface   IS NULL OR s.[芝/ダ] = @surface)
        AND (@race_name_like IS NULL OR s.[レース名] LIKE N'%' + @race_name_like + N'%')

        -- WHERE追加
        AND (@distance_from IS NULL OR s.[距離] >= @distance_from)
        AND (@distance_to   IS NULL OR s.[距離] <= @distance_to)
        AND (@baba_text     IS NULL OR s.[馬場] = @baba_text)
        AND (@win5_flg      IS NULL OR s.WIN5_flg = @win5_flg);
    
    /* 前走（全地域統合：中央＋地方＋海外含む）を付与 */

    -- #Base に出てくる馬だけ対象にする（性能対策）
    SELECT DISTINCT
        b.horse_id
    INTO #HorseList
    FROM #Base AS b
    WHERE b.horse_id IS NOT NULL;

    -- 履歴（中央＋地方）を列を揃えて作る
    ;WITH Hist AS
    (
        SELECT
            v.horse_id
            , v.race_id
            , v.[日付]          AS race_date
            , v.[クラス]        AS class_text
            , v.jyoken_cd4      AS jyoken_cd4
            , v.grade_cd        AS grade_cd
            , v.[芝/ダ]         AS surface
            , v.[距離]          AS distance_m
        FROM dbo.VW_RaceResultContract AS v
        WHERE v.horse_id IN (SELECT horse_id FROM #HorseList)

        UNION ALL

        SELECT
            v.horse_id
            , v.race_id
            , v.[日付]          AS race_date
            , v.[クラス]        AS class_text
            , v.jyoken_cd4      AS jyoken_cd4
            , v.grade_cd        AS grade_cd
            , v.[芝/ダ]         AS surface
            , v.[距離]          AS distance_m
        FROM dbo.VW_RaceResultContract_Local AS v
        WHERE v.horse_id IN (SELECT horse_id FROM #HorseList)
    )
    SELECT
        b.*
        , prev.race_id     AS prev_race_id
        , prev.race_date   AS prev_race_date
        , prev.class_text  AS prev_class
        , prev.jyoken_cd4  AS prev_jyoken_cd4
        , prev.grade_cd    AS prev_grade_cd
        , prev.surface     AS prev_surface
        , prev.distance_m  AS prev_distance_m

        -- 便利列（延長/短縮/同距離）
        , CASE
            WHEN prev.distance_m IS NULL OR b.[距離] IS NULL THEN N'(不明)'
            WHEN b.[距離] > prev.distance_m THEN N'延長'
            WHEN b.[距離] < prev.distance_m THEN N'短縮'
            ELSE N'同距離'
        END AS distance_change
    INTO #BaseEx
    FROM #Base AS b
    OUTER APPLY
    (
        SELECT TOP (1)
            h.race_id
            , h.race_date
            , h.class_text
            , h.jyoken_cd4
            , h.grade_cd
            , h.surface
            , h.distance_m
        FROM Hist AS h
        WHERE
            h.horse_id = b.horse_id
            AND (
                h.race_date < b.[日付]
                OR (h.race_date = b.[日付] AND h.race_id < b.race_id) -- 念のためのタイブレーク
            )
        ORDER BY
            h.race_date DESC
            , h.race_id   DESC
    ) AS prev;

    /* 騎手別 */
    SELECT
          COALESCE(NULLIF(LTRIM(RTRIM([騎手])), N''), N'(不明)') AS [騎手]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([騎手])), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

    /* 種牡馬（父）別 */
    SELECT
          COALESCE(NULLIF(LTRIM(RTRIM([父])), N''), N'(不明)') AS [父]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([父])), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

    /* 脚質別 */
    SELECT
          COALESCE(NULLIF(LTRIM(RTRIM([脚質])), N''), N'(不明)') AS [脚質]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([脚質])), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

    /* 枠別 */
    SELECT
          COALESCE(CONVERT(NVARCHAR(10), [枠番]), N'(不明)') AS [枠番]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(CONVERT(NVARCHAR(10), [枠番]), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

    /* ②追加：年齢別 */
    SELECT
          COALESCE(CONVERT(NVARCHAR(10), [齢]), N'(不明)') AS [年齢]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(CONVERT(NVARCHAR(10), [齢]), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [年齢] ASC;

    /* ②追加：性別（牡/牝/セ）別 */
    SELECT
          COALESCE(NULLIF(LTRIM(RTRIM([性])), N''), N'(不明)') AS [性]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM([性])), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

	/* ②追加：人気別（数が多くない前提なので“そのまま”） */
    ;WITH Pop AS
    (
        SELECT
              COALESCE(CONVERT(NVARCHAR(10), [人気]), N'(不明)') AS [人気]
            , MIN([人気]) AS min_popularity
            , COUNT(*) AS [出走数]
            , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
            , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
            , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
            , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
            , CAST(
                ROUND(
                    CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                    * 100.0
                    / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
                , 1)
            AS DECIMAL(5,1)) AS [勝率]
            , CAST(
                ROUND(
                    CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                    * 100.0
                    / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
                , 1)
            AS DECIMAL(5,1)) AS [複勝率]
        FROM #BaseEx
        GROUP BY COALESCE(CONVERT(NVARCHAR(10), [人気]), N'(不明)')
        HAVING COUNT(*) >= @min_starts
    )
    SELECT
          [人気]
        , [出走数]
        , [1着]
        , [2着]
        , [3着]
        , [着外]
        , [勝率]
        , [複勝率]
    FROM Pop
    ORDER BY
          CASE
              WHEN min_popularity IS NULL THEN 9999
              ELSE min_popularity
          END ASC;
    /* ②追加：斤量別（指定ラベル） */
    SELECT
          CASE
              WHEN [斤量] IS NULL THEN N'(不明)'
              WHEN [斤量] <= CAST(50.0 AS DECIMAL(3,1)) THEN N'~50'
              WHEN [斤量] >= CAST(60.0 AS DECIMAL(3,1)) THEN N'60~'
              ELSE
                  CASE
                      WHEN (CONVERT(INT, [斤量] * 10) % 10) = 0
                          THEN CONVERT(NVARCHAR(10), CONVERT(INT, [斤量]))
                      ELSE CONVERT(NVARCHAR(10), [斤量])
                  END
          END AS [斤量]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
    FROM #BaseEx
    GROUP BY
          CASE
              WHEN [斤量] IS NULL THEN N'(不明)'
              WHEN [斤量] <= CAST(50.0 AS DECIMAL(3,1)) THEN N'~50'
              WHEN [斤量] >= CAST(60.0 AS DECIMAL(3,1)) THEN N'60~'
              ELSE
                  CASE
                      WHEN (CONVERT(INT, [斤量] * 10) % 10) = 0
                          THEN CONVERT(NVARCHAR(10), CONVERT(INT, [斤量]))
                      ELSE CONVERT(NVARCHAR(10), [斤量])
                  END
          END
    HAVING COUNT(*) >= @min_starts
    ORDER BY
          CASE
              WHEN MIN([斤量]) IS NULL THEN 9999
              WHEN MIN([斤量]) <= CAST(50.0 AS DECIMAL(3,1)) THEN 500
              WHEN MIN([斤量]) >= CAST(60.0 AS DECIMAL(3,1)) THEN 600
              ELSE CONVERT(INT, MIN([斤量]) * 10)
          END ASC;

    /* ②追加：馬体重別（20kg帯＋端） */
    SELECT
          CASE
              WHEN [馬体重] IS NULL THEN N'(不明)'
              WHEN [馬体重] <= 399 THEN N'~399'
              WHEN [馬体重] >= 560 THEN N'560~'
              ELSE
                  CONCAT(
                      CONVERT(NVARCHAR(10), ([馬体重] / 20) * 20),
                      N'~',
                      CONVERT(NVARCHAR(10), (([馬体重] / 20) * 20) + 19)
                  )
          END AS [馬体重]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY
          CASE
              WHEN [馬体重] IS NULL THEN N'(不明)'
              WHEN [馬体重] <= 399 THEN N'~399'
              WHEN [馬体重] >= 560 THEN N'560~'
              ELSE
                  CONCAT(
                      CONVERT(NVARCHAR(10), ([馬体重] / 20) * 20),
                      N'~',
                      CONVERT(NVARCHAR(10), (([馬体重] / 20) * 20) + 19)
                  )
          END
    HAVING COUNT(*) >= @min_starts
    ORDER BY
          CASE
              WHEN MIN([馬体重]) IS NULL THEN 999999
              WHEN MIN([馬体重]) <= 399 THEN 399
              WHEN MIN([馬体重]) >= 560 THEN 560
              ELSE (MIN([馬体重]) / 20) * 20
          END ASC;

    /* ③追加：前走クラス別 */
    SELECT
        COALESCE(NULLIF(LTRIM(RTRIM(prev_class)), N''), N'(不明)') AS [前走クラス]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(prev_class)), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY [1着] DESC, [2着] DESC, [3着] DESC, [出走数] DESC;

    /* ③追加：前走距離別（距離値そのまま） */
    ;WITH PrevDist AS
    (
        SELECT
            COALESCE(CONVERT(NVARCHAR(10), prev_distance_m), N'(不明)') AS [前走距離]
            , MIN(prev_distance_m) AS min_prev_distance_m
            , COUNT(*) AS [出走数]
            , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
            , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
            , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
            , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
            , CAST(
                ROUND(
                    CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                    * 100.0
                    / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
                , 1)
            AS DECIMAL(5,1)) AS [勝率]
            , CAST(
                ROUND(
                    CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                    * 100.0
                    / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
                , 1)
            AS DECIMAL(5,1)) AS [複勝率]
        FROM #BaseEx
        GROUP BY COALESCE(CONVERT(NVARCHAR(10), prev_distance_m), N'(不明)')
        HAVING COUNT(*) >= @min_starts
    )
    SELECT
        [前走距離]
        , [出走数]
        , [1着]
        , [2着]
        , [3着]
        , [着外]
        , [勝率]
        , [複勝率]
    FROM PrevDist
    ORDER BY
        CASE
            WHEN min_prev_distance_m IS NULL THEN 99999
            ELSE min_prev_distance_m
        END ASC;
    
    /* ③追加：距離短縮／延長／同距離 */
    SELECT
        COALESCE(NULLIF(LTRIM(RTRIM(distance_change)), N''), N'(不明)') AS [距離変化]
        , COUNT(*) AS [出走数]
        , SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS [1着]
        , SUM(CASE WHEN [着順] = 2 THEN 1 ELSE 0 END) AS [2着]
        , SUM(CASE WHEN [着順] = 3 THEN 1 ELSE 0 END) AS [3着]
        , SUM(CASE WHEN ISNULL([着順], 99) >= 4 THEN 1 ELSE 0 END) AS [着外]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] = 1 THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [勝率]
        , CAST(
            ROUND(
                CAST(SUM(CASE WHEN [着順] IN (1,2,3) THEN 1 ELSE 0 END) AS DECIMAL(18, 6))
                * 100.0
                / NULLIF(CAST(COUNT(*) AS DECIMAL(18, 6)), 0)
            , 1)
        AS DECIMAL(5,1)) AS [複勝率]
    FROM #BaseEx
    GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(distance_change)), N''), N'(不明)')
    HAVING COUNT(*) >= @min_starts
    ORDER BY
        CASE COALESCE(NULLIF(LTRIM(RTRIM(distance_change)), N''), N'(不明)')
            WHEN N'短縮'   THEN 1
            WHEN N'同距離' THEN 2
            WHEN N'延長'   THEN 3
            ELSE 9
        END ASC;


END
GO
