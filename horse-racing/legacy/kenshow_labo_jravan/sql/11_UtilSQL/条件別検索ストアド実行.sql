EXEC dbo.sp_Stat_PlaceCounts
    @region = N'CENTRAL'
    , @min_starts = 3                     -- 母数フィルタ（1なら全件）
    ,@race_name_like = N'シンザン'   -- レース名(LIKE)
    -- 	, @date_from = '2016-01-01'       -- 期間FROM（含む）
    --  , @date_to   = '2025-12-31'       -- 期間TO（含む）
    --  , @surface = N'ダ'                -- N'芝' , N'ダ'
      , @jyo_cd = '08'                  -- '01' : 札幌, '02' : 函館, '03' : 福島, '04' : 新潟, '05' : 東京, '06' : 中山, '07' : 中京, '08' : 京都, '09' : 阪神, '10' : 小倉
    --  , @distance_from = 1800           -- 距離FROM（含む）
    --  , @distance_to = 1800             -- 距離TO（含む）
    --  , @baba_text = N'良'              -- 馬場状態（例：N'良', N'稍重', N'重', N'不良'）
    --  , @win5_flg = NULL                -- 0/1（NULLなら条件なし）
;
