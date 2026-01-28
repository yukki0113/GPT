using ImportRaceEntries.Netkeiba.Models;
using KenshowLabo.Tools.Db;
using Microsoft.Data.SqlClient;
using System.Data;

namespace ImportRaceEntries.Netkeiba {
    /// <summary>
    /// netkeiba IFテーブル（IF_Nk_RaceHeader / IF_Nk_RaceEntryRow）への投入を担います。
    /// </summary>
    public sealed class IfNetkeibaRepository {
        private readonly string _connectionString;

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public IfNetkeibaRepository(string connectionString) {
            _connectionString = connectionString;
        }

        /// <summary>
        /// IF_Nk_RaceHeader と IF_Nk_RaceEntryRow に投入します（同一import_batch_idで束ねます）。
        /// </summary>
        public void InsertIf(NetkeibaRaceHeaderRaw header, List<NetkeibaRaceEntryRowRaw> rows) {
            // 入力チェック
            if (header == null) {
                throw new ArgumentNullException(nameof(header));
            }

            if (rows == null) {
                throw new ArgumentNullException(nameof(rows));
            }

            if (rows.Count == 0) {
                throw new ArgumentException("rows is empty.", nameof(rows));
            }

            // トランザクション内でヘッダ＋明細を一括投入
            DbUtil.ExecuteInTransaction(
                _connectionString,
                (SqlConnection conn, SqlTransaction tx) => {
                    // 1) Header INSERT
                    Console.WriteLine("[DEBUG] header before insert:"
                        + " meeting=" + header.MeetingRaw
                        + " turn=" + header.TurnRaw
                        + " class=" + header.RaceClassRaw
                        + " head=" + header.HeadCountRaw
                        + " start=" + header.StartTimeRaw
                        + " dir=" + header.TurnDirRaw
                        + " ring=" + header.CourseRingRaw
                        + " ex=" + header.CourseExRaw
                        + " detail=" + header.CourseDetailRaw
                        + " surface=" + header.SurfaceTypeRaw
                        + " dist=" + header.DistanceMRaw
                    );

                    InsertHeader(conn, tx, header);

                    // 2) Rows Bulk Insert
                    BulkInsertRows(conn, tx, rows);
                }
            );
        }

        /// <summary>
        /// 取り込み後に IF→TR 展開ストアドを呼びます（任意）。
        /// </summary>
        public void ApplyToTr(Guid importBatchId) {
            DbUtil.ExecuteStoredProcedure(
                this._connectionString,
                "dbo.sp_ApplyNetkeibaRaceEntry",
                (SqlParameterCollection p) => {
                    p.Add(DbUtil.CreateParameter("@import_batch_id", SqlDbType.UniqueIdentifier, importBatchId));
                },
                0
            );
        }

        /// <summary>
        /// IF_Nk_RaceHeader に1行INSERTします（トランザクション内）。
        /// </summary>
        private static void InsertHeader(SqlConnection conn, SqlTransaction tx, NetkeibaRaceHeaderRaw header) {
            const string sql = @"
                INSERT INTO dbo.IF_Nk_RaceHeader
                (
                      import_batch_id
                    , race_id
                    , race_no_raw
                    , race_date_raw
                    , race_name_raw
                    , track_name_raw
                    , surface_distance_raw
                    , scraped_at
                    , source_url
                    , source_file
                    , created_at

                    -- 追加（RaceExtras）
                    , meeting_raw
                    , turn_raw
                    , race_class_raw
                    , head_count_raw

                    , start_time_raw
                    , turn_dir_raw
                    , course_ring_raw
                    , course_ex_raw
                    , course_detail_raw

                    , surface_type_raw
                    , distance_m_raw
                )
                VALUES
                (
                      @import_batch_id
                    , @race_id
                    , @race_no_raw
                    , @race_date_raw
                    , @race_name_raw
                    , @track_name_raw
                    , @surface_distance_raw
                    , @scraped_at
                    , @source_url
                    , @source_file
                    , @created_at

                    -- 追加（RaceExtras）
                    , @meeting_raw
                    , @turn_raw
                    , @race_class_raw
                    , @head_count_raw

                    , @start_time_raw
                    , @turn_dir_raw
                    , @course_ring_raw
                    , @course_ex_raw
                    , @course_detail_raw

                    , @surface_type_raw
                    , @distance_m_raw
                );
                ";

            // DbUtil に実行を委譲（Repository側からSqlCommandを排除）
            DbUtil.ExecuteNonQuery(
                conn,
                tx,
                sql,
                (SqlParameterCollection p) => {
                    p.Add(DbUtil.CreateParameter("@import_batch_id", SqlDbType.UniqueIdentifier, header.ImportBatchId));
                    p.Add(DbUtil.CreateParameter("@race_id", SqlDbType.Char, header.RaceId));
                    p.Add(DbUtil.CreateParameter("@race_no_raw", SqlDbType.NVarChar, header.RaceNoRaw));
                    p.Add(DbUtil.CreateParameter("@race_date_raw", SqlDbType.NVarChar, header.RaceDateRaw));
                    p.Add(DbUtil.CreateParameter("@race_name_raw", SqlDbType.NVarChar, header.RaceNameRaw));
                    p.Add(DbUtil.CreateParameter("@track_name_raw", SqlDbType.NVarChar, header.TrackNameRaw));
                    p.Add(DbUtil.CreateParameter("@surface_distance_raw", SqlDbType.NVarChar, header.SurfaceDistanceRaw));
                    p.Add(DbUtil.CreateParameter("@scraped_at", SqlDbType.DateTime2, header.ScrapedAt));
                    p.Add(DbUtil.CreateParameter("@source_url", SqlDbType.NVarChar, header.SourceUrl));
                    p.Add(DbUtil.CreateParameter("@source_file", SqlDbType.NVarChar, header.SourceFile));
                    p.Add(DbUtil.CreateParameter("@created_at", SqlDbType.DateTime2, DateTime.Now));

                    // 追加（RaceExtras）
                    p.Add(DbUtil.CreateParameter("@meeting_raw", SqlDbType.NVarChar, header.MeetingRaw));
                    p.Add(DbUtil.CreateParameter("@turn_raw", SqlDbType.NVarChar, header.TurnRaw));
                    p.Add(DbUtil.CreateParameter("@race_class_raw", SqlDbType.NVarChar, header.RaceClassRaw));
                    p.Add(DbUtil.CreateParameter("@head_count_raw", SqlDbType.NVarChar, header.HeadCountRaw));

                    p.Add(DbUtil.CreateParameter("@start_time_raw", SqlDbType.NVarChar, header.StartTimeRaw));
                    p.Add(DbUtil.CreateParameter("@turn_dir_raw", SqlDbType.NVarChar, header.TurnDirRaw));
                    p.Add(DbUtil.CreateParameter("@course_ring_raw", SqlDbType.NVarChar, header.CourseRingRaw));
                    p.Add(DbUtil.CreateParameter("@course_ex_raw", SqlDbType.NVarChar, header.CourseExRaw));
                    p.Add(DbUtil.CreateParameter("@course_detail_raw", SqlDbType.NVarChar, header.CourseDetailRaw));

                    p.Add(DbUtil.CreateParameter("@surface_type_raw", SqlDbType.NVarChar, header.SurfaceTypeRaw));
                    p.Add(DbUtil.CreateParameter("@distance_m_raw", SqlDbType.NVarChar, header.DistanceMRaw));
                }, 30
            );
        }

        /// <summary>
        /// IF_Nk_RaceEntryRow に一括投入します（トランザクション内）。
        /// </summary>
        private static void BulkInsertRows(SqlConnection conn, SqlTransaction tx, List<NetkeibaRaceEntryRowRaw> rows) {
            // DataTable作成
            DataTable dt = CreateRowDataTable(rows);

            // DbUtilに委譲
            DbUtil.BulkInsertDataTable(
                conn,
                tx,
                "dbo.IF_Nk_RaceEntryRow",
                dt,
                (SqlBulkCopyColumnMappingCollection m) => {
                    m.Add("import_batch_id", "import_batch_id");
                    m.Add("row_no", "row_no");
                    m.Add("nk_horse_id", "nk_horse_id");
                    m.Add("jv_horse_id", "jv_horse_id");
                    m.Add("frame_no_raw", "frame_no_raw");
                    m.Add("horse_no_raw", "horse_no_raw");
                    m.Add("horse_name_raw", "horse_name_raw");
                    m.Add("sex_age_raw", "sex_age_raw");
                    m.Add("jockey_name_raw", "jockey_name_raw");
                    m.Add("carried_weight_raw", "carried_weight_raw");
                },
                5000,
                0,
                SqlBulkCopyOptions.Default
            );
        }

        /// <summary>
        /// BulkInsert用のDataTableを作成します。
        /// </summary>
        private static DataTable CreateRowDataTable(List<NetkeibaRaceEntryRowRaw> rows) {
            DataTable dt = new DataTable();

            dt.Columns.Add("import_batch_id", typeof(Guid));
            dt.Columns.Add("row_no", typeof(int));
            dt.Columns.Add("nk_horse_id", typeof(string));
            dt.Columns.Add("jv_horse_id", typeof(string));
            dt.Columns.Add("frame_no_raw", typeof(string));
            dt.Columns.Add("horse_no_raw", typeof(string));
            dt.Columns.Add("horse_name_raw", typeof(string));
            dt.Columns.Add("sex_age_raw", typeof(string));
            dt.Columns.Add("jockey_name_raw", typeof(string));
            dt.Columns.Add("carried_weight_raw", typeof(string));

            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                DataRow row = dt.NewRow();

                row["import_batch_id"] = r.ImportBatchId;
                row["row_no"] = r.RowNo;
                row["nk_horse_id"] = (object?)r.NkHorseId ?? DBNull.Value;
                row["jv_horse_id"] = (object?)r.JvHorseId ?? DBNull.Value;
                row["frame_no_raw"] = (object?)r.FrameNoRaw ?? DBNull.Value;
                row["horse_no_raw"] = (object?)r.HorseNoRaw ?? DBNull.Value;
                row["horse_name_raw"] = (object?)r.HorseNameRaw ?? DBNull.Value;
                row["sex_age_raw"] = (object?)r.SexAgeRaw ?? DBNull.Value;
                row["jockey_name_raw"] = (object?)r.JockeyNameRaw ?? DBNull.Value;
                row["carried_weight_raw"] = (object?)r.CarriedWeightRaw ?? DBNull.Value;

                dt.Rows.Add(row);
            }

            return dt;
        }

        public int CleanupOldIfData(DateTime cutoffDate, DateTime cutoffScrapedAt) {
            const string sql = @"
                ;WITH Target AS
                (
                    SELECT h.import_batch_id
                    FROM dbo.IF_Nk_RaceHeader h
                    WHERE
                        (h.race_date_norm IS NOT NULL AND h.race_date_norm < @cutoffDate)
                        OR
                        (h.race_date_norm IS NULL AND h.scraped_at < @cutoffScrapedAt)
                )
                DELETE r
                FROM dbo.IF_Nk_RaceEntryRow r
                INNER JOIN Target t
                    ON t.import_batch_id = r.import_batch_id;

                ;WITH Target AS
                (
                    SELECT h.import_batch_id
                    FROM dbo.IF_Nk_RaceHeader h
                    WHERE
                        (h.race_date_norm IS NOT NULL AND h.race_date_norm < @cutoffDate)
                        OR
                        (h.race_date_norm IS NULL AND h.scraped_at < @cutoffScrapedAt)
                )
                DELETE l
                FROM dbo.IF_Nk_ApplyLog l
                INNER JOIN Target t
                    ON t.import_batch_id = l.import_batch_id;

                DELETE h
                FROM dbo.IF_Nk_RaceHeader h
                WHERE
                    (h.race_date_norm IS NOT NULL AND h.race_date_norm < @cutoffDate)
                    OR
                    (h.race_date_norm IS NULL AND h.scraped_at < @cutoffScrapedAt);
                ";

            int affected = DbUtil.ExecuteNonQuery(
                this._connectionString,
                sql,
                (SqlParameterCollection p) => {
                    p.Add(DbUtil.CreateParameter("@cutoffDate", SqlDbType.Date, cutoffDate.Date));
                    p.Add(DbUtil.CreateParameter("@cutoffScrapedAt", SqlDbType.DateTime2, cutoffScrapedAt));
                },
                30
            );

            return affected;
        }

    }
}
