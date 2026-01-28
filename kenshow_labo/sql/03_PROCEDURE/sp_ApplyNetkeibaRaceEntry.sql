CREATE OR ALTER PROCEDURE dbo.sp_ApplyNetkeibaRaceEntry
(
      @import_batch_id UNIQUEIDENTIFIER = NULL
)
AS
BEGIN
    SET NOCOUNT ON;

    -----------------------------------------------------------------
    -- ★ 引数なし（NULL）の場合：ヘッダにあるBatchIDを全件処理
    -----------------------------------------------------------------
    IF @import_batch_id IS NULL
    BEGIN
        DECLARE @bid UNIQUEIDENTIFIER;

        DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
            SELECT h.import_batch_id
            FROM dbo.IF_Nk_RaceHeader h
            WHERE EXISTS (
                SELECT 1
                FROM dbo.IF_Nk_RaceEntryRow r
                WHERE r.import_batch_id = h.import_batch_id
            )
            ORDER BY h.scraped_at, h.import_batch_id;

        OPEN cur;
        FETCH NEXT FROM cur INTO @bid;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 既存ロジックをそのまま使う（1Batchずつ処理）
            EXEC dbo.sp_ApplyNetkeibaRaceEntry @import_batch_id = @bid;

            FETCH NEXT FROM cur INTO @bid;
        END

        CLOSE cur;
        DEALLOCATE cur;
        RETURN;
    END

    DECLARE @race_id CHAR(12);
    DECLARE @scraped_at DATETIME2(0);
    DECLARE @source_url NVARCHAR(500);
    DECLARE @header_exists INT = 0;
    DECLARE @missing_norm NVARCHAR(300) = N'';

    ------------------------------------------------------------
    -- 0) ヘッダ取得
    ------------------------------------------------------------
    SELECT
          @race_id    = h.race_id
        , @scraped_at = h.scraped_at
        , @source_url = h.source_url
    FROM dbo.IF_Nk_RaceHeader h
    WHERE h.import_batch_id = @import_batch_id;

    IF @race_id IS NULL
    BEGIN
        THROW 50001, 'IF_Nk_RaceHeader に該当 import_batch_id が存在しません。', 1;
    END

    IF NOT EXISTS (SELECT 1 FROM dbo.IF_Nk_RaceEntryRow r WHERE r.import_batch_id = @import_batch_id)
    BEGIN
        THROW 50002, 'IF_Nk_RaceEntryRow に明細が存在しません。', 1;
    END

    BEGIN TRY
        BEGIN TRAN;

        ------------------------------------------------------------
        -- 1) IF明細の jv_horse_id を MP_HorseId で補完（NULL行だけ）
        ------------------------------------------------------------
        UPDATE r
            SET r.jv_horse_id = m.jv_horse_id
        FROM dbo.IF_Nk_RaceEntryRow r
        INNER JOIN dbo.MP_HorseId m
            ON m.nk_horse_id = r.nk_horse_id
        WHERE
            r.import_batch_id = @import_batch_id
            AND r.jv_horse_id IS NULL
            AND r.nk_horse_id IS NOT NULL;
        
        ------------------------------------------------------------
        -- 1.5) MPで埋まらない行は「馬名 → 血統マスタ」で補完する
        --      同名が複数いる場合は horse_id 降順 TOP1 を採用する
        ------------------------------------------------------------

        -- まず対象行（未解決）を抽出し、候補と件数を一時表に作る
        IF OBJECT_ID('tempdb..#NameResolve') IS NOT NULL
        BEGIN
            DROP TABLE #NameResolve;
        END

        SELECT
              r.import_batch_id
            , r.row_no
            , LTRIM(RTRIM(REPLACE(ISNULL(r.horse_name_raw, N''), N'　', N' '))) AS horse_name_key

            -- 解決結果（候補がある場合は horse_id 降順TOP1）
            , ca.chosen_horse_id
            , ca.cand_count
        INTO #NameResolve
        FROM dbo.IF_Nk_RaceEntryRow r
        OUTER APPLY
        (
            SELECT TOP (1)
                  x.horse_id AS chosen_horse_id
                , x.cand_count
            FROM
            (
                SELECT
                      p.horse_id
                    , COUNT(*) OVER () AS cand_count
                FROM dbo.MT_HorsePedigree p
                WHERE
                    p.horse_name = LTRIM(RTRIM(REPLACE(ISNULL(r.horse_name_raw, N''), N'　', N' ')))
            ) x
            ORDER BY x.horse_id DESC
        ) ca
        WHERE
            r.import_batch_id = @import_batch_id
            AND r.jv_horse_id IS NULL
            AND NULLIF(LTRIM(RTRIM(r.horse_name_raw)), N'') IS NOT NULL;

        -- 一時表から IF明細の jv_horse_id を埋める（候補が取れた行だけ）
        UPDATE r
            SET r.jv_horse_id = nr.chosen_horse_id
        FROM dbo.IF_Nk_RaceEntryRow r
        INNER JOIN #NameResolve nr
            ON nr.import_batch_id = r.import_batch_id
           AND nr.row_no         = r.row_no
        WHERE
            r.import_batch_id = @import_batch_id
            AND r.jv_horse_id IS NULL
            AND nr.chosen_horse_id IS NOT NULL;

        -- 参考：同名候補が複数あった件数をログに残す（処理は止めない）
        DECLARE @name_resolved_count INT;
        DECLARE @name_ambiguous_count INT;

        SELECT @name_resolved_count = COUNT(*)
        FROM #NameResolve
        WHERE chosen_horse_id IS NOT NULL;

        SELECT @name_ambiguous_count = COUNT(*)
        FROM #NameResolve
        WHERE chosen_horse_id IS NOT NULL
          AND cand_count >= 2;

        IF @name_resolved_count > 0
        BEGIN
            INSERT INTO dbo.IF_Nk_ApplyLog (import_batch_id, race_id, inserted_rows, message)
            VALUES
            (
                @import_batch_id,
                @race_id,
                0,
                CONCAT(
                    N'INFO: 馬名→血統マスタで ', @name_resolved_count, N' 件補完しました',
                    N'（同名候補>=2 は ', @name_ambiguous_count, N' 件。horse_id 降順TOP1採用）'
                )
            );
        END

        INSERT INTO dbo.MP_HorseId (nk_horse_id, jv_horse_id, source, confidence)
        SELECT DISTINCT
              r.nk_horse_id
            , r.jv_horse_id
            , 'sp'
            , 60
        FROM dbo.IF_Nk_RaceEntryRow r
        WHERE
            r.import_batch_id = @import_batch_id
            AND r.nk_horse_id IS NOT NULL
            AND r.jv_horse_id IS NOT NULL
            AND NOT EXISTS
            (
                SELECT 1
                FROM dbo.MP_HorseId m
                WHERE m.nk_horse_id = r.nk_horse_id
            );

        ------------------------------------------------------------
        -- 2) 未解決チェック（jv_horse_id が1つでもNULLなら展開しない）
        ------------------------------------------------------------
        DECLARE @unresolved_count INT;

        SELECT @unresolved_count = COUNT(*)
        FROM dbo.IF_Nk_RaceEntryRow r
        WHERE
            r.import_batch_id = @import_batch_id
            AND (r.jv_horse_id IS NULL OR LTRIM(RTRIM(r.jv_horse_id)) = N'');

        IF @unresolved_count > 0
        BEGIN
            INSERT INTO dbo.IF_Nk_ApplyLog (import_batch_id, race_id, inserted_rows, message)
            VALUES
            (
                @import_batch_id,
                @race_id,
                0,
                CONCAT(N'SKIP: jv_horse_id 未解決行が ', @unresolved_count, N' 件あります（手動対応後に再実行してください）。')
            );

            COMMIT;
            RETURN 1;
        END

        ------------------------------------------------------------
        -- 3) IFヘッダの正規化：*_norm を埋める（import_batch_id単位）
        ------------------------------------------------------------
        UPDATE h
        SET
              race_no_norm =
                  COALESCE(
                      h.race_no_norm,
                      TRY_CONVERT(TINYINT, REPLACE(REPLACE(h.race_no_raw, N'R', N''), N'Ｒ', N''))
                  )

            , race_date_norm =
                  COALESCE(
                      h.race_date_norm,
                      TRY_CONVERT(DATE, NULLIF(LTRIM(RTRIM(h.race_date_raw)), N'')),
                      CASE
                          WHEN h.race_date_raw LIKE N'%年%月%日%' THEN
                              TRY_CONVERT(
                                  DATE,
                                  CONCAT(
                                      SUBSTRING(h.race_date_raw, 1, CHARINDEX(N'年', h.race_date_raw) - 1), N'-',
                                      RIGHT(N'00' + SUBSTRING(h.race_date_raw, CHARINDEX(N'年', h.race_date_raw) + 1, CHARINDEX(N'月', h.race_date_raw) - CHARINDEX(N'年', h.race_date_raw) - 1), 2), N'-',
                                      RIGHT(N'00' + SUBSTRING(h.race_date_raw, CHARINDEX(N'月', h.race_date_raw) + 1, CHARINDEX(N'日', h.race_date_raw) - CHARINDEX(N'月', h.race_date_raw) - 1), 2)
                                  )
                              )
                          WHEN h.race_date_raw LIKE N'%月%日%' THEN
                              TRY_CONVERT(
                                  DATE,
                                  CONCAT(
                                      LEFT(h.race_id, 4), N'-',
                                      RIGHT(N'00' + SUBSTRING(h.race_date_raw, 1, CHARINDEX(N'月', h.race_date_raw) - 1), 2), N'-',
                                      RIGHT(N'00' + SUBSTRING(h.race_date_raw, CHARINDEX(N'月', h.race_date_raw) + 1, CHARINDEX(N'日', h.race_date_raw) - CHARINDEX(N'月', h.race_date_raw) - 1), 2)
                                  )
                              )
                          ELSE NULL
                      END
                  )

            , track_name_norm =
                  COALESCE(
                      h.track_name_norm,
                      NULLIF(LTRIM(RTRIM(LEFT(h.track_name_raw, 3))), N'')
                  )

            , surface_type_norm =
                  COALESCE(
                      h.surface_type_norm,
                      NULLIF(LTRIM(RTRIM(h.surface_type_raw)), N''),
                      CASE
                          WHEN h.surface_distance_raw LIKE N'芝%' THEN N'芝'
                          WHEN h.surface_distance_raw LIKE N'ダ%' THEN N'ダ'
                          ELSE NULL
                      END
                  )

            , distance_m_norm =
                  COALESCE(
                      h.distance_m_norm,
                      TRY_CONVERT(SMALLINT, NULLIF(LTRIM(RTRIM(h.distance_m_raw)), N'')),
                      TRY_CONVERT(
                          SMALLINT,
                          CASE
                              WHEN h.surface_distance_raw IS NULL THEN NULL
                              WHEN PATINDEX(N'%[0-9]%', h.surface_distance_raw) = 0 THEN NULL
                              ELSE
                                  CASE
                                      WHEN CHARINDEX(N'm', h.surface_distance_raw) > 0 THEN
                                          SUBSTRING(
                                              h.surface_distance_raw,
                                              PATINDEX(N'%[0-9]%', h.surface_distance_raw),
                                              CHARINDEX(N'm', h.surface_distance_raw) - PATINDEX(N'%[0-9]%', h.surface_distance_raw)
                                          )
                                      ELSE
                                          SUBSTRING(h.surface_distance_raw, PATINDEX(N'%[0-9]%', h.surface_distance_raw), 10)
                                  END
                          END
                      )
                  )

            , race_name_norm =
                  COALESCE(
                      h.race_name_norm,
                      LEFT(
                          LTRIM(RTRIM(
                              CASE
                                  WHEN CHARINDEX(N'（', h.race_name_raw) > 0 THEN LEFT(h.race_name_raw, CHARINDEX(N'（', h.race_name_raw) - 1)
                                  WHEN CHARINDEX(N'(',  h.race_name_raw) > 0 THEN LEFT(h.race_name_raw, CHARINDEX(N'(',  h.race_name_raw) - 1)
                                  ELSE h.race_name_raw
                              END
                          )),
                          50
                      )
                  )
        FROM dbo.IF_Nk_RaceHeader h
        WHERE h.import_batch_id = @import_batch_id;
        
        ------------------------------------------------------------
        -- 3.5) ヘッダ正規化の必須項目チェック（失敗ならSKIP）
        ------------------------------------------------------------
        -- 必須normの欠落を列名で列挙（最新1件を見る想定）
        SELECT TOP (1)
            @missing_norm = CONCAT(
                  CASE WHEN h.race_no_norm      IS NULL THEN N'race_no_norm '      ELSE N'' END
                , CASE WHEN h.race_date_norm    IS NULL THEN N'race_date_norm '    ELSE N'' END
                , CASE WHEN h.track_name_norm   IS NULL THEN N'track_name_norm '   ELSE N'' END
                , CASE WHEN h.surface_type_norm IS NULL THEN N'surface_type_norm ' ELSE N'' END
                , CASE WHEN h.distance_m_norm   IS NULL THEN N'distance_m_norm '   ELSE N'' END
                , CASE WHEN h.race_name_norm    IS NULL THEN N'race_name_norm '    ELSE N'' END
            )
        FROM dbo.IF_Nk_RaceHeader h
        WHERE h.import_batch_id = @import_batch_id
        ORDER BY h.scraped_at DESC;

        IF NULLIF(LTRIM(RTRIM(@missing_norm)), N'') IS NOT NULL
        BEGIN
            INSERT INTO dbo.IF_Nk_ApplyLog (import_batch_id, race_id, inserted_rows, message)
            VALUES
            (
                @import_batch_id,
                @race_id,
                0,
                CONCAT(N'SKIP: ヘッダ正規化に失敗しました。未解決(norm NULL): ', @missing_norm, N'（HTML/抽出ロジックを確認して再実行してください）。')
            );

            COMMIT;
            RETURN 1;
        END
        
        ------------------------------------------------------------
        -- 4) TRを race_id 単位で置換
        ------------------------------------------------------------
        DELETE FROM dbo.TR_RaceEntry
        WHERE race_id = @race_id;

        ;WITH H AS
        (
            SELECT TOP (1)
                  h.race_id
                , h.race_no_norm      AS race_no
                , h.race_date_norm    AS race_date
                , h.race_name_norm    AS race_name
                , h.race_name_raw     AS race_name_raw
                , h.track_name_norm   AS track_name
                , h.surface_type_norm AS surface_type
                , h.distance_m_norm   AS distance_m

                -- 「○回開催△日目」をmeetingに寄せる
                , LEFT(
                      CONCAT(
                          NULLIF(LTRIM(RTRIM(h.meeting_raw)), N''),
                          REPLACE(REPLACE(NULLIF(LTRIM(RTRIM(h.turn_raw)), N''), N'回目', N'日目'), N' ', N'')
                      ),
                      20
                  ) AS meeting

                -- TR.turn は右/左
                , NULLIF(LTRIM(RTRIM(h.turn_dir_raw)), N'') AS turn_dir

                -- TR.course_inout は内/外
                , CASE
                    WHEN NULLIF(LTRIM(RTRIM(h.course_ring_raw)), N'') IS NULL THEN N'内'
                    WHEN h.course_ring_raw LIKE N'%外%' THEN N'外'
                    ELSE N'内'
                END AS course_inout

                , LEFT(NULLIF(LTRIM(RTRIM(h.race_class_raw)), N''), 100) AS race_class_full
                -- カテゴリ（短いほう）
                , CASE
                      WHEN h.race_name_raw LIKE N'%(G1)%' THEN N'G1'
                      WHEN h.race_name_raw LIKE N'%(G2)%' THEN N'G2'
                      WHEN h.race_name_raw LIKE N'%(G3)%' THEN N'G3'
                      WHEN h.race_name_raw LIKE N'%(L)%'  THEN N'L'
                      WHEN h.race_class_raw LIKE N'%未勝利%' THEN N'未勝利'
                      WHEN h.race_class_raw LIKE N'%新馬%'   THEN N'新馬'
                      WHEN h.race_class_raw LIKE N'%1勝%' OR h.race_class_raw LIKE N'%500万%'  THEN N'1勝'
                      WHEN h.race_class_raw LIKE N'%2勝%' OR h.race_class_raw LIKE N'%1000万%' THEN N'2勝'
                      WHEN h.race_class_raw LIKE N'%3勝%' OR h.race_class_raw LIKE N'%1600万%' THEN N'3勝'
                      WHEN h.race_class_raw LIKE N'%オープン%' THEN N'OP'
                      ELSE NULL
                  END AS race_class

                -- grade
                , CASE
                      WHEN h.race_name_raw LIKE N'%(G1)%' THEN N'G1'
                      WHEN h.race_name_raw LIKE N'%(G2)%' THEN N'G2'
                      WHEN h.race_name_raw LIKE N'%(G3)%' THEN N'G3'
                      WHEN h.race_name_raw LIKE N'%(L)%'  THEN N'L'
                      ELSE NULL
                  END AS grade

            FROM dbo.IF_Nk_RaceHeader h
            WHERE h.import_batch_id = @import_batch_id
            ORDER BY h.scraped_at DESC
        )
        INSERT INTO dbo.TR_RaceEntry
        (
              race_id
            , race_no
            , race_date
            , race_name
            , race_class
            , race_class_full
            , grade
            , track_name
            , surface_type
            , distance_m
            , meeting
            , turn
            , course_inout
            , going
            , weather
            , frame_no
            , horse_no
            , horse_id
            , horse_name
            , sex
            , age
            , jockey_name
            , carried_weight
            , race_name_raw
            , scraped_at
            , source_url
        )
        SELECT
              h.race_id
            , h.race_no
            , h.race_date
            , h.race_name
            , h.race_class
            , h.race_class_full
            , h.grade
            , h.track_name
            , h.surface_type
            , h.distance_m
            , h.meeting
            , h.turn_dir     AS turn
            , h.course_inout
            , NULL AS going
            , NULL AS weather

            , NULLIF(TRY_CONVERT(TINYINT, r.frame_no_raw), 0) AS frame_no
            , COALESCE(
                  NULLIF(TRY_CONVERT(TINYINT, r.horse_no_raw), 0),
                  TRY_CONVERT(TINYINT, 100 + r.row_no)
              ) AS horse_no

            , r.jv_horse_id AS horse_id
            , LEFT(r.horse_name_raw, 30) AS horse_name
            , CASE WHEN r.sex_age_raw IS NULL OR LEN(r.sex_age_raw) = 0 THEN NULL ELSE LEFT(r.sex_age_raw, 1) END AS sex
            , TRY_CONVERT(TINYINT, SUBSTRING(r.sex_age_raw, 2, 10)) AS age

            , NULLIF(
                LTRIM(RTRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        NULLIF(LTRIM(RTRIM(r.jockey_name_raw)), N''),
                        N'▲', N''),
                        N'△', N''),
                        N'☆', N''),
                        N'★', N''),
                        N'◇', N''),
                        N'◆', N'')
                )),
                N''
            ) AS jockey_name

            , TRY_CONVERT(DECIMAL(3,1), r.carried_weight_raw) AS carried_weight
            , h.race_name_raw AS race_name_raw
            , @scraped_at
            , @source_url
        FROM H h
        INNER JOIN dbo.IF_Nk_RaceEntryRow r
            ON r.import_batch_id = @import_batch_id;
        
        DECLARE @inserted_rows INT = @@ROWCOUNT;
        
        ------------------------------------------------------------
        -- 5) 成功ログ
        ------------------------------------------------------------
        INSERT INTO dbo.IF_Nk_ApplyLog (import_batch_id, race_id, inserted_rows, message)
        VALUES (@import_batch_id, @race_id, @inserted_rows, N'OK');

        COMMIT;
        RETURN 0;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;

        DECLARE @err NVARCHAR(4000) = CONCAT(
            N'ERROR ', ERROR_NUMBER(), N': ', ERROR_MESSAGE(),
            N' (line ', ERROR_LINE(), N')'
        );

        INSERT INTO dbo.IF_Nk_ApplyLog (import_batch_id, race_id, inserted_rows, message)
        VALUES (@import_batch_id, ISNULL(@race_id, '????????????'), 0, @err);

        THROW;
    END CATCH
END
GO
