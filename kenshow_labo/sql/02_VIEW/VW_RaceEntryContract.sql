CREATE OR ALTER VIEW dbo.VW_RaceEntryContract
AS
SELECT
    main.[race_id]
    , main.[race_date] AS [日付]
    , main.[track_name] AS [競馬場名]    
    , main.[race_no] AS [R]
    , main.[race_name] AS [レース名]
    , main.[race_class] AS [クラス]
    , main.[grade] AS [グレード]
    , main.[surface_type] AS [芝／ダ]
    , main.[distance_m] AS [距離]
    , main.[meeting] AS [開催]
    , dturn.[text] AS [回り]
    , dring.[text] AS [内／外]
    , dbaba.[text] AS [馬場]
    , dweather.[text] AS [天気]
    , main.[frame_no]
    , main.[horse_no]
    , main.[horse_name]
    , main.[sex]
    , main.[age]
    , main.[jockey_name]
    , main.[carried_weight]
    , main.[race_name_raw]
    , main.[race_class_full]
    
    -- CD類
    , main.[id]
    , dcourse.[code] as jyo_cd
    , dsurface.[code] as surface_type
    , main.[turn]
    , main.[course_inout]
    , main.[going]
    , main.[weather]
    , main.[horse_id]
FROM
    TR_RaceEntry main
LEFT JOIN MT_CodeDictionary dcourse
    ON dcourse.code_type = 'RACE_COURSE'
    AND dcourse.[text] = main.[track_name]
LEFT JOIN  MT_CodeDictionary dsurface
    ON dsurface.code_type = 'SHIBA_DIRT'
    AND dsurface.[text] = main.[surface_type]
LEFT JOIN  MT_CodeDictionary dturn
    ON dturn.code_type = 'TURN_DIR'
    AND dturn.[code] = main.[turn]
LEFT JOIN  MT_CodeDictionary dring
    ON dring.code_type = 'COURSE_RING'
    AND dring.[code] = main.[course_inout]
LEFT JOIN  MT_CodeDictionary dbaba
    ON dbaba.code_type = 'BABA'
    AND dbaba.[code] = main.[going]
LEFT JOIN  MT_CodeDictionary dweather
    ON dweather.code_type = 'WEATHER'
    AND dweather.[code] = main.[weather]
