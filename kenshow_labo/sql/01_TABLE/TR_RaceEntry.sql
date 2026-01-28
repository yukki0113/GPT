--* BackupToTempTable
drop table [TR_RaceEntry]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.TR_RaceEntry
(
      id             INT IDENTITY(1,1) NOT NULL
    , race_id        CHAR(12)          NOT NULL  -- 例：202512210610（12桁）
    , race_no        TINYINT           NOT NULL  -- 1～12(R)想定

    -- レース情報（出馬表時点で分かる範囲）
    , race_date      DATE              NOT NULL
    , race_name      NVARCHAR(50)      NOT NULL
    , race_class     NVARCHAR(20)      NULL
    , grade          NVARCHAR(4)       NULL  -- G1/G2/G3/JG1/L など
    , track_name     NVARCHAR(3)       NOT NULL
    , surface_type   NVARCHAR(10)      NOT NULL
    , distance_m     SMALLINT          NOT NULL
    , meeting        NVARCHAR(20)      NULL
    , turn           NVARCHAR(1)       NULL
    , course_inout   NVARCHAR(1)       NULL
    , going          NVARCHAR(1)       NULL
    , weather        NVARCHAR(1)       NULL

    -- 出走馬情報
    , frame_no       TINYINT           NULL      -- 未確定は NULL
    , horse_no       TINYINT           NOT NULL  -- 未確定は 101～（例：101～）
    , horse_id       CHAR(10)          NULL
    , horse_name     NVARCHAR(30)      NOT NULL
    , sex            NVARCHAR(1)       NULL
    , age            TINYINT           NULL
    , jockey_name    NVARCHAR(10)      NULL
    , carried_weight DECIMAL(3,1)      NULL

    -- 管理情報（軽量）
    , race_name_raw  NVARCHAR(50)      NULL
    , race_class_full NVARCHAR(100)    NULL
    , scraped_at     DATETIME2(0)      NOT NULL
                     CONSTRAINT DF_TR_RaceEntry_scraped_at DEFAULT (SYSDATETIME())
    , source_url     NVARCHAR(500)     NULL

    CONSTRAINT PK_TR_RaceEntry PRIMARY KEY (id)
);
GO

CREATE UNIQUE INDEX UX_TR_RaceEntry_race_horseno
ON dbo.TR_RaceEntry (race_id, horse_no);
GO

CREATE UNIQUE INDEX UX_TR_RaceEntry_race_horseid
ON dbo.TR_RaceEntry (race_id, horse_id);
GO