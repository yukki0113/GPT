CREATE OR ALTER PROCEDURE dbo.usp_JV_Expand_All
AS
BEGIN
    SET NOCOUNT ON

    BEGIN TRY
        /* 1) 血統マスタ */
        EXEC dbo.usp_JV_Expand_MT_HorsePedigree

        /* 2) WIN5対象マスタ */
        EXEC dbo.usp_JV_Expand_MT_Win5Target

        /* 3) レース結果（TR_RaceResult） */
        EXEC dbo.usp_JV_Expand_TR_RaceResult

        /* 4) 払戻（単勝/複勝のみ） */
        EXEC dbo.usp_JV_Expand_TR_Payout
    END TRY
    BEGIN CATCH
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
