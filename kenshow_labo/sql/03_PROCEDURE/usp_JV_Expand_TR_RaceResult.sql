CREATE OR ALTER PROCEDURE dbo.usp_JV_Expand_TR_RaceResult
AS
BEGIN
    SET NOCOUNT ON

    /* 対象 race_id：IF_JV_Race と IF_JV_RaceUma の共通部分のみ */
    IF OBJECT_ID('tempdb..#TargetRace') IS NOT NULL
        DROP TABLE #TargetRace

    SELECT DISTINCT r.race_id
    INTO #TargetRace
    FROM dbo.IF_JV_Race AS r
    INNER JOIN dbo.IF_JV_RaceUma AS u
        ON u.race_id = r.race_id

    BEGIN TRY
        BEGIN TRAN

        /* 冪等：対象 race_id の結果を入れ直す */
        DELETE t
        FROM dbo.TR_RaceResult AS t
        INNER JOIN #TargetRace AS x
            ON x.race_id = t.race_id

        /* INSERT：ヘッダ×馬（WIN5はMT参照でフラグ化） */
        INSERT INTO dbo.TR_RaceResult
        (
              race_id
            , horse_no

            , race_date
            , ymd
            , jyo_cd
            , race_no

            , race_name
            , jyoken_name
            , grade_cd
            , jyoken_syubetu_cd
            , jyoken_cd4

            , track_cd
            , distance_m
            , hasso_time
            , weather_cd
            , baba_siba_cd
            , baba_dirt_cd

            , win5_flg

            , frame_no
            , horse_id
            , horse_name
            , sex_cd
            , age
            , jockey_code
            , jockey_name
            , carried_weight
            , odds
            , popularity

            , finish_time_raw
            , finish_time

            , weight_raw
            , horse_weight

            , weight_diff_raw
            , horse_weight_diff

            , pos_c1
            , pos_c2
            , pos_c3
            , pos_c4

            , finish_pos
            , final_3f_raw
            , final_3f
        )
        SELECT
              r.race_id
            , u.horse_no

            , TRY_CONVERT(DATE, STUFF(STUFF(r.ymd, 5, 0, '-'), 8, 0, '-')) AS race_date
            , r.ymd
            , r.jyo_cd
            , r.race_num

            , r.race_name
            , r.jyoken_name
            , r.grade_cd
            , r.jyoken_syubetu_cd
            , r.jyoken_cd4

            , r.track_cd
            , r.distance_m
            , r.hasso_time
            , r.weather_cd
            , r.baba_siba_cd
            , r.baba_dirt_cd

            , CASE WHEN w.race_id IS NOT NULL THEN CAST(1 AS TINYINT) ELSE CAST(0 AS TINYINT) END AS win5_flg

            , u.frame_no
            , CASE WHEN u.horse_id IS NULL THEN NULL ELSE LEFT(u.horse_id, 10) END AS horse_id
            , u.horse_name
            , u.sex_cd
            , u.age
            , u.jockey_code
            , u.jockey_name
            , u.carried_weight
            , u.odds
            , u.popularity

            , u.finish_time_raw
            , CASE
                WHEN NULLIF(LTRIM(RTRIM(u.finish_time_raw)), N'') IS NULL
                    THEN NULL

                /* 数字だけ（例：1132, 2011）を想定：分(可変) + 秒(2桁) + 1/10秒(1桁) */
                WHEN TRY_CONVERT(INT, LTRIM(RTRIM(u.finish_time_raw))) IS NOT NULL
                    AND LEN(LTRIM(RTRIM(u.finish_time_raw))) >= 3
                    THEN
                        TRY_CONVERT(
                            TIME(2),
                            CONCAT(
                                N'00:',
                                RIGHT(
                                    N'00' + CASE
                                                WHEN LEN(LTRIM(RTRIM(u.finish_time_raw))) > 3
                                                    THEN LEFT(LTRIM(RTRIM(u.finish_time_raw)), LEN(LTRIM(RTRIM(u.finish_time_raw))) - 3)
                                                ELSE N'0'
                                            END,
                                    2
                                ),
                                N':',
                                SUBSTRING(LTRIM(RTRIM(u.finish_time_raw)), LEN(LTRIM(RTRIM(u.finish_time_raw))) - 2, 2),
                                N'.',
                                RIGHT(LTRIM(RTRIM(u.finish_time_raw)), 1),
                                N'0'
                            )
                        )

                /* それ以外の形式は一旦 NULL（必要なら後で対応追加） */
                ELSE NULL
            END AS finish_time
            , u.weight_raw
            , TRY_CONVERT(SMALLINT, NULLIF(LTRIM(RTRIM(u.weight_raw)), N'')) AS horse_weight

            , u.weight_diff_raw
            , TRY_CONVERT(SMALLINT, NULLIF(LTRIM(RTRIM(u.weight_diff_raw)), N'')) AS horse_weight_diff

            , u.pos_c1
            , u.pos_c2
            , u.pos_c3
            , u.pos_c4
            
            , u.finish_pos
            , u.final_3f_raw
            , CASE
                WHEN NULLIF(LTRIM(RTRIM(u.final_3f_raw)), N'') IS NULL
                    THEN NULL
                WHEN LTRIM(RTRIM(u.final_3f_raw)) LIKE N'%.%'
                    THEN TRY_CONVERT(DECIMAL(3,1), LTRIM(RTRIM(u.final_3f_raw)))
                WHEN TRY_CONVERT(INT, LTRIM(RTRIM(u.final_3f_raw))) IS NULL
                    THEN NULL
                ELSE
                    CAST(TRY_CONVERT(INT, LTRIM(RTRIM(u.final_3f_raw))) / 10.0 AS DECIMAL(3,1))
                END AS final_3f
          FROM dbo.IF_JV_RaceUma AS u
        INNER JOIN dbo.IF_JV_Race AS r
            ON r.race_id = u.race_id
        INNER JOIN #TargetRace AS x
            ON x.race_id = r.race_id
        LEFT JOIN dbo.MT_Win5Target AS w
            ON w.race_id = r.race_id

        COMMIT
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK

        DECLARE @ErrorMessage NVARCHAR(4000)
        DECLARE @ErrorSeverity INT
        DECLARE @ErrorState INT

        SELECT
              @ErrorMessage  = ERROR_MESSAGE()
            , @ErrorSeverity = ERROR_SEVERITY()
            , @ErrorState    = ERROR_STATE()

        RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState)
        RETURN
    END CATCH
END
GO
