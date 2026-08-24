--* BackupToTempTable
drop table [IF_JV_Win5Target]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_JV_Win5Target
(
      win5_date     date     NOT NULL
    , leg_no        tinyint  NOT NULL
    , race_id       char(12) NOT NULL
    , source_kubun  char(1)  NULL
    , make_ymd      char(8)  NULL

    , CONSTRAINT PK_IF_JV_Win5Target PRIMARY KEY (win5_date, leg_no)
    , CONSTRAINT UQ_IF_JV_Win5Target_RaceId UNIQUE (race_id)
    , CONSTRAINT CK_IF_JV_Win5Target_LegNo CHECK (leg_no BETWEEN 1 AND 5)
);
GO