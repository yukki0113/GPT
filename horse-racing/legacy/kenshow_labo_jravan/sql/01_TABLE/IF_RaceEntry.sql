--* BackupToTempTable
drop table [IF_RaceEntry]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_RaceEntry
(
      race_id        CHAR(12)          NOT NULL
    , horse_id       BIGINT            NOT NULL

    , race_no        TINYINT           NOT NULL
    , race_date      DATE              NOT NULL
    , race_name      NVARCHAR(50)      NOT NULL
    , race_class     NVARCHAR(20)      NULL
    , classSimple    NVARCHAR(20)      NULL
    , track_name     NVARCHAR(3)       NOT NULL
    , surface_type   NVARCHAR(10)      NOT NULL
    , distance_m     INT               NOT NULL
    , meeting        NVARCHAR(12)      NULL
    , turn           NVARCHAR(1)       NULL
    , course_inout   NVARCHAR(1)       NULL
    , going          NVARCHAR(1)       NULL
    , weather        NVARCHAR(1)       NULL

    , frame_no       INT               NULL
    , horse_no       INT               NOT NULL  -- 未確定は 101～118
    , horse_name     NVARCHAR(30)      NOT NULL
    , sex            NVARCHAR(1)       NULL
    , age            INT               NULL
    , jockey_name    NVARCHAR(10)      NULL
    , carried_weight DECIMAL(3,1)      NULL

    , scraped_at     DATETIME2(0)      NOT NULL
                     CONSTRAINT DF_IF_RaceEntry_scraped_at DEFAULT (SYSDATETIME())
    , source_url     NVARCHAR(500)     NULL

    CONSTRAINT PK_IF_RaceEntry PRIMARY KEY (race_id, horse_id)
);
GO

CREATE INDEX IX_IF_RaceEntry_race
ON dbo.IF_RaceEntry (race_id);
GO
