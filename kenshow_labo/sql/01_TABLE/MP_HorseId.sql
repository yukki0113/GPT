--* BackupToTempTable
drop table [MP_HorseId]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.MP_HorseId
(
      nk_horse_id   CHAR(10)        NOT NULL
    , jv_horse_id   CHAR(10)        NOT NULL

    -- 由来：'NKID'（既知）/'NAME'（馬名一致）/'MANUAL'（手動修正）など
    , source        NVARCHAR(20)    NOT NULL

    -- 100=確実（手動や公式対応）、80=馬名一致など
    , confidence    TINYINT         NOT NULL CONSTRAINT DF_MP_HorseId_confidence DEFAULT (100)

    , created_at    DATETIME2(0)    NOT NULL CONSTRAINT DF_MP_HorseId_created_at DEFAULT (SYSDATETIME())
    , updated_at    DATETIME2(0)    NOT NULL CONSTRAINT DF_MP_HorseId_updated_at DEFAULT (SYSDATETIME())

    CONSTRAINT PK_MP_HorseId PRIMARY KEY (nk_horse_id)
);
GO

CREATE UNIQUE INDEX UX_MP_HorseId_jv
ON dbo.MP_HorseId (jv_horse_id);
GO
