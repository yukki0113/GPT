--* BackupToTempTable
drop table [IF_JV_PAY]
GO
 
--* RestoreFromTempTable
create table [dbo].[IF_JV_PAY] (
  [race_id] char(12) not null
  , [data_kubun] char(1)
  , [make_date] char(8)
  , [tansyo0_umaban] char(2)
  , [tansyo0_pay] int
  , [tansyo0_ninki] int
  , [tansyo1_umaban] char(2)
  , [tansyo1_pay] int
  , [tansyo1_ninki] int
  , [tansyo2_umaban] char(2)
  , [tansyo2_pay] int
  , [tansyo2_ninki] int
  , [fukusyo0_umaban] char(2)
  , [fukusyo0_pay] int
  , [fukusyo0_ninki] int
  , [fukusyo1_umaban] char(2)
  , [fukusyo1_pay] int
  , [fukusyo1_ninki] int
  , [fukusyo2_umaban] char(2)
  , [fukusyo2_pay] int
  , [fukusyo2_ninki] int
  , [fukusyo3_umaban] char(2)
  , [fukusyo3_pay] int
  , [fukusyo3_ninki] int
  , [fukusyo4_umaban] char(2)
  , [fukusyo4_pay] int
  , [fukusyo4_ninki] int
  , primary key (race_id)
);

