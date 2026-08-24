CREATE OR ALTER PROCEDURE dbo.sp_GenerateRaceEntryFromRaceResult
(
      @race_id CHAR(12)
)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRAN;

        ------------------------------------------------------------
        -- 1) 対象レース存在チェック
        ------------------------------------------------------------
        IF NOT EXISTS (
            SELECT 1
            FROM dbo.VW_RaceResultContract AS v
            WHERE v.race_id = @race_id
        )
        BEGIN
            RAISERROR(N'指定された race_id が VW_RaceResultContract に存在しません。', 16, 1);
            ROLLBACK;
            RETURN;
        END

        ------------------------------------------------------------
        -- 2) レース単位キー（VW_Track結合用）を取得
        ------------------------------------------------------------
        DECLARE @jyo_cd CHAR(2);
        DECLARE @track_cd SMALLINT;
        DECLARE @kyori SMALLINT;
        DECLARE @shibadirt TINYINT;     -- 芝=1 / ダ=2
        DECLARE @weather_cd TINYINT;
        DECLARE @going_cd TINYINT;

        SELECT TOP (1)
              @jyo_cd      = v.jyo_cd
            , @track_cd    = TRY_CONVERT(SMALLINT, v.track_cd)
            , @kyori       = TRY_CONVERT(SMALLINT, v.[距離])
            , @weather_cd  = TRY_CONVERT(TINYINT, v.weather_cd)
            , @shibadirt   =
                CASE
                    WHEN TRY_CONVERT(INT, v.baba_siba_cd) IS NOT NULL AND TRY_CONVERT(INT, v.baba_siba_cd) <> 0 THEN 1
                    WHEN TRY_CONVERT(INT, v.baba_dirt_cd) IS NOT NULL AND TRY_CONVERT(INT, v.baba_dirt_cd) <> 0 THEN 2
                    ELSE NULL
                END
            , @going_cd    =
                CASE
                    WHEN TRY_CONVERT(INT, v.baba_siba_cd) IS NOT NULL AND TRY_CONVERT(INT, v.baba_siba_cd) <> 0 THEN TRY_CONVERT(TINYINT, v.baba_siba_cd)
                    WHEN TRY_CONVERT(INT, v.baba_dirt_cd) IS NOT NULL AND TRY_CONVERT(INT, v.baba_dirt_cd) <> 0 THEN TRY_CONVERT(TINYINT, v.baba_dirt_cd)
                    ELSE NULL
                END
        FROM dbo.VW_RaceResultContract AS v
        WHERE v.race_id = @race_id;

        IF @jyo_cd IS NULL OR @track_cd IS NULL OR @kyori IS NULL OR @shibadirt IS NULL
        BEGIN
            RAISERROR(N'VW_Track結合に必要なキーが不足しています（jyo_cd/track_cd/距離/ShibaDirt）。', 16, 1);
            ROLLBACK;
            RETURN;
        END

        ------------------------------------------------------------
        -- 3) VW_Track から回り/内外などを取得（無ければNULLのまま）
        ------------------------------------------------------------
        DECLARE @turn_dir_cd NVARCHAR(1);
        DECLARE @course_ring_cd NVARCHAR(1);

        SELECT TOP (1)
              @turn_dir_cd     = TRY_CONVERT(NVARCHAR(1), t.TurnDirCD)
            , @course_ring_cd  = TRY_CONVERT(NVARCHAR(1), t.CourseRingCD)
        FROM dbo.VW_Track AS t
        WHERE t.JyoCD      = @jyo_cd
          AND t.Kyori      = @kyori
          AND t.ShibaDirt  = @shibadirt
          AND t.TrackCD    = @track_cd;

        ------------------------------------------------------------
        -- 4) 既存の仮装出馬表を削除（race_id単位で置換）
        ------------------------------------------------------------
        DELETE FROM dbo.TR_RaceEntry
        WHERE race_id = @race_id;

        ------------------------------------------------------------
        -- 5) VIEW → TR_RaceEntry 生成INSERT
        ------------------------------------------------------------
        INSERT INTO dbo.TR_RaceEntry
        (
              race_id
            , race_no
            , race_date
            , race_name
            , race_class
            , track_name
            , surface_type
            , distance_m
            , meeting
            , turn
            , course_inout
            , going
            , weather
            , frame_no
            , horse_no
            , horse_id
            , horse_name
            , sex
            , age
            , jockey_name
            , carried_weight
            , scraped_at
            , source_url
        )
        SELECT
              v.race_id
            , TRY_CONVERT(TINYINT, v.race_no)            AS race_no
            , TRY_CONVERT(DATE, v.[日付])                AS race_date
            , LEFT(v.[レース名], 50)                     AS race_name
            , LEFT(v.[クラス], 20)                       AS race_class
            , LEFT(v.[場名], 3)                          AS track_name

            , CASE WHEN @shibadirt = 1 THEN N'芝'
                   WHEN @shibadirt = 2 THEN N'ダ'
                   ELSE NULL
              END                                       AS surface_type

            , TRY_CONVERT(SMALLINT, v.[距離])            AS distance_m

            , NULL                                      AS meeting
            , @turn_dir_cd                               AS turn
            , @course_ring_cd                            AS course_inout
            , TRY_CONVERT(NVARCHAR(1), @going_cd)         AS going
            , TRY_CONVERT(NVARCHAR(1), @weather_cd)       AS weather

            , TRY_CONVERT(TINYINT, v.[枠番])             AS frame_no
            , TRY_CONVERT(TINYINT, v.[馬番])             AS horse_no
            , v.horse_id                                 AS horse_id
            , LEFT(v.[馬名], 30)                         AS horse_name
            , LEFT(v.[性], 1)                            AS sex
            , TRY_CONVERT(TINYINT, v.[齢])               AS age
            , LEFT(v.[騎手], 10)                         AS jockey_name
            , TRY_CONVERT(DECIMAL(3,1), v.[斤量])        AS carried_weight

            , SYSDATETIME()                              AS scraped_at
            , N'GENERATED:VW_RaceResultContract'         AS source_url
        FROM dbo.VW_RaceResultContract AS v
        WHERE v.race_id = @race_id;

        IF @@ROWCOUNT = 0
        BEGIN
            RAISERROR(N'INSERT対象が0件でした。', 16, 1);
            ROLLBACK;
            RETURN;
        END

        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
        BEGIN
            ROLLBACK;
        END

        -- 互換性低い環境でも通るよう、THROWは使いません
        DECLARE @msg NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@msg, 16, 1);
    END CATCH
END
GO
