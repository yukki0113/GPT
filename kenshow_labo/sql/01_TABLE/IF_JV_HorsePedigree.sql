--* BackupToTempTable
drop table [IF_JV_HorsePedigree]
GO
 
--* RestoreFromTempTable
CREATE TABLE dbo.IF_JV_HorsePedigree
(
      horse_id    char(10)       NOT NULL  -- JVの血統番号（KettoNum）
    , horse_name  nvarchar(100)  NULL
    , sire        nvarchar(100)  NULL
    , dam         nvarchar(100)  NULL
    , dam_sire    nvarchar(100)  NULL
    , dam_dam     nvarchar(100)  NULL
    , sire_sire   nvarchar(100)  NULL
    , sire_dam    nvarchar(100)  NULL

    , data_kubun  char(1)        NULL
    , make_date   char(8)        NULL

    , CONSTRAINT PK_IF_JV_HorsePedigree PRIMARY KEY (horse_id)
);

CREATE INDEX IX_IF_JV_HorsePedigree_HorseName
    ON dbo.IF_JV_HorsePedigree (horse_name);
GO
