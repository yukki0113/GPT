CREATE OR ALTER PROCEDURE dbo.usp_JV_Expand_TR_Payout
AS
BEGIN
    SET NOCOUNT ON

    IF OBJECT_ID('tempdb..#Filtered') IS NOT NULL
        DROP TABLE #Filtered

    CREATE TABLE #Filtered
    (
          race_id       CHAR(12)     NOT NULL
        , bet_type      NVARCHAR(20) NOT NULL   -- 式別
        , horse_no_1    INT          NULL       -- 馬番1
        , payout_amount INT          NULL       -- 払戻
        , popularity    INT          NULL       -- 式別人気
    )

    /* IF_JV_PAY（横持ち）→ #Filtered（縦持ち）  ※APPLY不使用 */
    INSERT INTO #Filtered (race_id, bet_type, horse_no_1, payout_amount, popularity)
    SELECT p.race_id, N'単勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.tansyo0_umaban)), N'')),
           p.tansyo0_pay, p.tansyo0_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'単勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.tansyo1_umaban)), N'')),
           p.tansyo1_pay, p.tansyo1_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'単勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.tansyo2_umaban)), N'')),
           p.tansyo2_pay, p.tansyo2_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'複勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.fukusyo0_umaban)), N'')),
           p.fukusyo0_pay, p.fukusyo0_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'複勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.fukusyo1_umaban)), N'')),
           p.fukusyo1_pay, p.fukusyo1_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'複勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.fukusyo2_umaban)), N'')),
           p.fukusyo2_pay, p.fukusyo2_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'複勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.fukusyo3_umaban)), N'')),
           p.fukusyo3_pay, p.fukusyo3_ninki
    FROM dbo.IF_JV_PAY AS p
    UNION ALL
    SELECT p.race_id, N'複勝',
           TRY_CONVERT(INT, NULLIF(LTRIM(RTRIM(p.fukusyo4_umaban)), N'')),
           p.fukusyo4_pay, p.fukusyo4_ninki
    FROM dbo.IF_JV_PAY AS p

    /* 無効行を落とす（馬番なし・払戻なし・払戻0以下） */
    DELETE FROM #Filtered
    WHERE horse_no_1 IS NULL
       OR payout_amount IS NULL
       OR payout_amount <= 0

    /* 事前チェック：同一(race_id, bet_type, horse_no_1)が複数なら異常としてエラー */
    IF EXISTS
    (
        SELECT 1
        FROM #Filtered
        GROUP BY race_id, bet_type, horse_no_1
        HAVING COUNT(*) > 1
    )
    BEGIN
        RAISERROR(N'IF_JV_PAY の展開結果に重複があります（race_id, bet_type, horse_no_1）。', 16, 1)
        RETURN
    END

    BEGIN TRY
        BEGIN TRAN

        /* 冪等：IFに入っている race_id の単勝/複勝を入れ直す */
        DELETE T
        FROM dbo.TR_Payout AS T
        INNER JOIN dbo.IF_JV_PAY AS P
            ON P.race_id = T.race_id
        WHERE T.bet_type IN (N'単勝', N'複勝')

        INSERT INTO dbo.TR_Payout
        (
              race_id
            , bet_type
            , horse_no_1
            , horse_no_2
            , horse_no_3
            , payout_amount
            , popularity
        )
        SELECT
              f.race_id
            , f.bet_type
            , f.horse_no_1
            , NULL
            , NULL
            , f.payout_amount
            , f.popularity
        FROM #Filtered AS f

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