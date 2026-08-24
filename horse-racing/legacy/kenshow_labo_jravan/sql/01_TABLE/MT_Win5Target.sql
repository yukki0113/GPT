--* BackupToTempTable
drop table [MT_Win5Target]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.MT_Win5Target
(
      win5_date  date     NOT NULL
    , leg_no     tinyint  NOT NULL
    , race_id    char(12) NOT NULL

    , CONSTRAINT PK_MT_Win5Target PRIMARY KEY (win5_date, leg_no)
    , CONSTRAINT UQ_MT_Win5Target_RaceId UNIQUE (race_id)
    , CONSTRAINT CK_MT_Win5Target_LegNo CHECK (leg_no BETWEEN 1 AND 5)
)
GO

CREATE INDEX IX_MT_Win5Target_RaceId
    ON dbo.MT_Win5Target (race_id)
GO

CREATE INDEX IX_MT_Win5Target_Date_LegNo
    ON dbo.MT_Win5Target (win5_date, leg_no);
GO