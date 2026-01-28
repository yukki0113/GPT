--* BackupToTempTable
drop table [IF_JV_RaceUma]
GO
 
--* RestoreFromTempTable
create table [dbo].[IF_JV_RaceUma] (
  [race_id] char(12) not null
  , [horse_no] int not null
  , [frame_no] int
  , [horse_id] CHAR(10)
  , [horse_name] nvarchar(30)
  , [sex_cd] char(1)
  , [age] int
  , [jockey_code] char(5)
  , [jockey_name] nvarchar(10)
  , [carried_weight] decimal(3, 1)
  , [odds] decimal(6, 2)
  , [popularity] int
  , [finish_pos] int
  , [finish_time_raw] nvarchar(16)
  , [weight_raw] nvarchar(8)
  , [weight_diff_raw] nvarchar(8)
  , [pos_c1] int
  , [pos_c2] int
  , [pos_c3] int
  , [pos_c4] int
  , [final_3f_raw] nvarchar(8)
  , [data_kubun] char(1)
  , [make_date] char(8)
  , [ymd] char(8)
  , primary key (race_id,horse_no)
);