CREATE OR ALTER PROCEDURE dbo.usp_JV_Expand_MT_Win5Target
AS
BEGIN
    SET NOCOUNT ON

    /* leg_no 範囲チェック（IF側にもありますが、念のため） */
    IF EXISTS (
        SELECT 1
        FROM dbo.IF_JV_Win5Target
        WHERE leg_no < 1 OR leg_no > 5
    )
    BEGIN
        RAISERROR(N'IF_JV_Win5Target の leg_no が 1～5 の範囲外です。', 16, 1)
        RETURN
    END

    BEGIN TRY
        BEGIN TRAN

        /* IFにあるキー(win5_date, leg_no)を入れ直す（冪等） */
        DELETE t
        FROM dbo.MT_Win5Target AS t
        INNER JOIN dbo.IF_JV_Win5Target AS s
            ON s.win5_date = t.win5_date
           AND s.leg_no    = t.leg_no

        INSERT INTO dbo.MT_Win5Target
        (
              win5_date
            , leg_no
            , race_id
        )
        SELECT
              s.win5_date
            , s.leg_no
            , s.race_id
        FROM dbo.IF_JV_Win5Target AS s

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
