CREATE OR ALTER PROCEDURE dbo.usp_JV_Expand_MT_HorsePedigree
AS
BEGIN
    SET NOCOUNT ON

    BEGIN TRY
        BEGIN TRAN

        /* 既存行を更新（IF側の値で上書き） */
        UPDATE t
        SET
              t.horse_name = s.horse_name
            , t.sire       = s.sire
            , t.dam        = s.dam
            , t.dam_sire   = s.dam_sire
            , t.dam_dam    = s.dam_dam
            , t.sire_sire  = s.sire_sire
            , t.sire_dam   = s.sire_dam
        FROM dbo.MT_HorsePedigree AS t
        INNER JOIN dbo.IF_JV_HorsePedigree AS s
            ON s.horse_id = t.horse_id
        WHERE
               ISNULL(t.horse_name, N'') <> ISNULL(s.horse_name, N'')
            OR ISNULL(t.sire,       N'') <> ISNULL(s.sire,       N'')
            OR ISNULL(t.dam,        N'') <> ISNULL(s.dam,        N'')
            OR ISNULL(t.dam_sire,   N'') <> ISNULL(s.dam_sire,   N'')
            OR ISNULL(t.dam_dam,    N'') <> ISNULL(s.dam_dam,    N'')
            OR ISNULL(t.sire_sire,  N'') <> ISNULL(s.sire_sire,  N'')
            OR ISNULL(t.sire_dam,   N'') <> ISNULL(s.sire_dam,   N'')

        /* 無い行を追加（積み上げ型：削除はしない） */
        INSERT INTO dbo.MT_HorsePedigree
        (
              horse_id
            , horse_name
            , sire
            , dam
            , dam_sire
            , dam_dam
            , sire_sire
            , sire_dam
        )
        SELECT
              s.horse_id
            , s.horse_name
            , s.sire
            , s.dam
            , s.dam_sire
            , s.dam_dam
            , s.sire_sire
            , s.sire_dam
        FROM dbo.IF_JV_HorsePedigree AS s
        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dbo.MT_HorsePedigree AS t
            WHERE t.horse_id = s.horse_id
        )

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
