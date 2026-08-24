--* BackupToTempTable
drop table [IF_Nk_ApplyLog]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_Nk_ApplyLog
(
      id                INT IDENTITY(1,1) NOT NULL
    , import_batch_id    UNIQUEIDENTIFIER NOT NULL
    , race_id            CHAR(12)         NOT NULL
    , applied_at         DATETIME2(0)     NOT NULL CONSTRAINT DF_IF_Nk_ApplyLog_applied_at DEFAULT (SYSDATETIME())
    , inserted_rows      INT              NOT NULL
    , message            NVARCHAR(4000)   NULL

    CONSTRAINT PK_IF_Nk_ApplyLog PRIMARY KEY (id)
);
GO

CREATE INDEX IX_IF_Nk_ApplyLog_batch
ON dbo.IF_Nk_ApplyLog (import_batch_id, applied_at DESC);
GO
