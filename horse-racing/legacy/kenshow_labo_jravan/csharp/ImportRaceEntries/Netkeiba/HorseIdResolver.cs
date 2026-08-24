using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using Microsoft.Data.SqlClient;
using KenshowLabo.Tools.Db;
using ImportRaceEntries.Netkeiba.Models;

namespace ImportRaceEntries.Netkeiba {
    /// <summary>
    /// netkeiba馬ID（nk）→ JV馬ID（jv）を解決します（バッチ解決）。
    /// 方針：
    /// 1) MP_HorseId から nk をまとめて検索し、jv を埋める
    /// 2) 未解決分は馬名で MT_HorsePedigree をまとめて検索（単一一致のみ採用）
    /// 3) 採用できたものは MP_HorseId に一括UPSERT（source=NAME, confidence=80）
    /// </summary>
    public sealed class HorseIdResolver {
        private readonly string _connectionString;

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public HorseIdResolver(string connectionString) {
            _connectionString = connectionString;
        }

        /// <summary>
        /// 指定された行リストについて、jv_horse_id を一括で解決し、rows の JvHorseId を埋めます。
        /// 未解決が残った場合は、その内容を警告メッセージとして返します（処理は止めません）。
        /// </summary>
        public List<string> ResolveForRows(List<NetkeibaRaceEntryRowRaw> rows) {
            if (rows == null) {
                throw new ArgumentNullException(nameof(rows));
            }

            List<string> warnings = new List<string>();

            // 対象が無ければ何もしない
            if (rows.Count == 0) {
                return warnings;
            }

            // 1レース分なので、トランザクションでまとめて処理
            DbUtil.ExecuteInTransaction(
                _connectionString,
                (SqlConnection conn, SqlTransaction tx) => {
                    // ============================================
                    // 1) MP_HorseId で nk → jv を一括取得
                    // ============================================
                    Dictionary<string, string> nkToJv = LoadMappingsByNk(conn, tx, rows);

                    // 取得できたものを埋める
                    ApplyMappingToRows(rows, nkToJv);

                    // ============================================
                    // 2) 未解決分を馬名で一括検索（単一一致のみ）
                    // ============================================
                    Dictionary<string, List<string>> nameToJvCandidates = LoadPedigreeByNames(conn, tx, rows);

                    // name単一一致のものを採用し、UPSERT対象を作る
                    List<HorseIdUpsertItem> upserts = ApplyNameMatchAndBuildUpserts(rows, nameToJvCandidates);

                    // ============================================
                    // 3) MP_HorseId に一括UPSERT
                    // ============================================
                    if (upserts.Count > 0) {
                        BulkUpsertMappings(conn, tx, upserts);
                    }
                }
            );

            // ============================================
            // 4) 未解決警告（トランザクション外でOK）
            // ============================================
            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                if (string.IsNullOrWhiteSpace(r.NkHorseId)) {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(r.JvHorseId)) {
                    continue;
                }

                string msg = "jv_horse_id unresolved: nk_horse_id=" + r.NkHorseId
                             + " horse_name=" + (r.HorseNameRaw ?? "null");
                warnings.Add(msg);
            }

            return warnings;
        }

        /// <summary>
        /// MP_HorseId から nk_horse_id をキーに一括取得します。
        /// </summary>
        private static Dictionary<string, string> LoadMappingsByNk(SqlConnection conn, SqlTransaction tx, List<NetkeibaRaceEntryRowRaw> rows) {
            HashSet<string> nkSet = new HashSet<string>(StringComparer.Ordinal);

            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                if (string.IsNullOrWhiteSpace(r.NkHorseId)) {
                    continue;
                }

                nkSet.Add(r.NkHorseId);
            }

            Dictionary<string, string> nkToJv = new Dictionary<string, string>(StringComparer.Ordinal);

            if (nkSet.Count == 0) {
                return nkToJv;
            }

            List<string> nkList = nkSet.ToList();

            // IN句をパラメータで組み立て
            string inClause = BuildInClause("@nk", nkList.Count);

            string sql = @"
SELECT m.nk_horse_id, m.jv_horse_id
FROM dbo.MP_HorseId AS m
WHERE m.nk_horse_id IN " + inClause + @";
";

            List<NkJvRow> list = DbUtil.QueryToList<NkJvRow>(
                conn,
                tx,
                sql,
                (SqlParameterCollection p) => {
                    AddInParameters(p, "@nk", nkList, SqlDbType.Char);
                },
                (SqlDataReader reader) => {
                    NkJvRow item = new NkJvRow();
                    item.NkHorseId = reader.GetString(0);
                    item.JvHorseId = reader.GetString(1);
                    return item;
                },
                30
            );

            foreach (NkJvRow item in list) {
                if (string.IsNullOrWhiteSpace(item.NkHorseId)) {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(item.JvHorseId)) {
                    continue;
                }

                if (!nkToJv.ContainsKey(item.NkHorseId)) {
                    nkToJv.Add(item.NkHorseId, item.JvHorseId);
                }
            }

            return nkToJv;
        }

        /// <summary>
        /// 取得済みマッピングを rows に適用します。
        /// </summary>
        private static void ApplyMappingToRows(List<NetkeibaRaceEntryRowRaw> rows, Dictionary<string, string> nkToJv) {
            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                if (string.IsNullOrWhiteSpace(r.NkHorseId)) {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(r.JvHorseId)) {
                    continue;
                }

                if (nkToJv.TryGetValue(r.NkHorseId, out string? jv)) {
                    r.JvHorseId = jv;
                }
            }
        }

        /// <summary>
        /// 未解決行の馬名をまとめて MT_HorsePedigree から検索します（候補は複数あり得る）。
        /// </summary>
        private static Dictionary<string, List<string>> LoadPedigreeByNames(SqlConnection conn, SqlTransaction tx, List<NetkeibaRaceEntryRowRaw> rows) {
            HashSet<string> nameSet = new HashSet<string>(StringComparer.Ordinal);

            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                if (!string.IsNullOrWhiteSpace(r.JvHorseId)) {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(r.HorseNameRaw)) {
                    continue;
                }

                // 馬名完全一致検索前提（必要なら後で正規化）
                nameSet.Add(r.HorseNameRaw);
            }

            Dictionary<string, List<string>> nameToCandidates = new Dictionary<string, List<string>>(StringComparer.Ordinal);

            if (nameSet.Count == 0) {
                return nameToCandidates;
            }

            List<string> nameList = nameSet.ToList();
            string inClause = BuildInClause("@nm", nameList.Count);

            string sql = @"
SELECT p.horse_name, p.horse_id
FROM dbo.MT_HorsePedigree AS p
WHERE p.horse_name IN " + inClause + @";
";

            List<NameJvRow> list = DbUtil.QueryToList<NameJvRow>(
                conn,
                tx,
                sql,
                (SqlParameterCollection p) => {
                    AddInParameters(p, "@nm", nameList, SqlDbType.NVarChar);
                },
                (SqlDataReader reader) => {
                    NameJvRow item = new NameJvRow();
                    item.HorseName = reader.GetString(0);
                    item.JvHorseId = reader.GetString(1);
                    return item;
                },
                30
            );

            foreach (NameJvRow item in list) {
                if (string.IsNullOrWhiteSpace(item.HorseName)) {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(item.JvHorseId)) {
                    continue;
                }

                if (!nameToCandidates.ContainsKey(item.HorseName)) {
                    nameToCandidates.Add(item.HorseName, new List<string>());
                }

                // 重複排除
                List<string> candidates = nameToCandidates[item.HorseName];
                if (!candidates.Contains(item.JvHorseId)) {
                    candidates.Add(item.JvHorseId);
                }
            }

            return nameToCandidates;
        }

        /// <summary>
        /// 馬名検索の単一一致のみ採用し、MP_HorseId へのUPSERT対象を作ります。
        /// </summary>
        private static List<HorseIdUpsertItem> ApplyNameMatchAndBuildUpserts(
            List<NetkeibaRaceEntryRowRaw> rows,
            Dictionary<string, List<string>> nameToCandidates) {
            Dictionary<string, HorseIdUpsertItem> nkKeyedUpserts = new Dictionary<string, HorseIdUpsertItem>(StringComparer.Ordinal);

            foreach (NetkeibaRaceEntryRowRaw r in rows) {
                if (string.IsNullOrWhiteSpace(r.NkHorseId)) {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(r.JvHorseId)) {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(r.HorseNameRaw)) {
                    continue;
                }

                if (!nameToCandidates.TryGetValue(r.HorseNameRaw, out List<string>? candidates)) {
                    continue;
                }

                if (candidates.Count != 1) {
                    // 0件 or 複数件は未解決（警告は呼び出し側で）
                    continue;
                }

                string resolvedJv = candidates[0];
                r.JvHorseId = resolvedJv;

                // 同一nkが複数行に出ることは原則ないが、防御的にDictionaryでまとめる
                if (!nkKeyedUpserts.ContainsKey(r.NkHorseId)) {
                    HorseIdUpsertItem item = new HorseIdUpsertItem();
                    item.NkHorseId = r.NkHorseId;
                    item.JvHorseId = resolvedJv;
                    item.Source = "NAME";
                    item.Confidence = 80;

                    nkKeyedUpserts.Add(r.NkHorseId, item);
                }
            }

            return nkKeyedUpserts.Values.ToList();
        }

        /// <summary>
        /// MP_HorseId を一括UPSERTします（temp table + MERGE）。
        /// </summary>
        private static void BulkUpsertMappings(SqlConnection conn, SqlTransaction tx, List<HorseIdUpsertItem> upserts) {
            // 一時テーブル作成
            const string createSql = @"
CREATE TABLE #TmpHorseIdMap
(
      nk_horse_id  CHAR(10)     NOT NULL
    , jv_horse_id  CHAR(10)     NOT NULL
    , source       NVARCHAR(20) NOT NULL
    , confidence   TINYINT      NOT NULL
);
";

            DbUtil.ExecuteNonQuery(
                conn,
                tx,
                createSql,
                (SqlParameterCollection p) => { },
                30
            );

            // DataTableに詰めて一括投入
            DataTable dt = new DataTable();
            dt.Columns.Add("nk_horse_id", typeof(string));
            dt.Columns.Add("jv_horse_id", typeof(string));
            dt.Columns.Add("source", typeof(string));
            dt.Columns.Add("confidence", typeof(byte));

            foreach (HorseIdUpsertItem u in upserts) {
                DataRow row = dt.NewRow();
                row["nk_horse_id"] = u.NkHorseId;
                row["jv_horse_id"] = u.JvHorseId;
                row["source"] = u.Source;
                row["confidence"] = (byte)u.Confidence;
                dt.Rows.Add(row);
            }

            DbUtil.BulkInsertDataTable(
                conn,
                tx,
                "#TmpHorseIdMap",
                dt,
                (SqlBulkCopyColumnMappingCollection m) => {
                    m.Add("nk_horse_id", "nk_horse_id");
                    m.Add("jv_horse_id", "jv_horse_id");
                    m.Add("source", "source");
                    m.Add("confidence", "confidence");
                },
                2000,
                0,
                SqlBulkCopyOptions.Default
            );

            // MERGEでUPSERT
            const string mergeSql = @"
MERGE dbo.MP_HorseId AS tgt
USING #TmpHorseIdMap AS src
    ON tgt.nk_horse_id = src.nk_horse_id
WHEN MATCHED THEN
    UPDATE SET
          tgt.jv_horse_id = src.jv_horse_id
        , tgt.source      = src.source
        , tgt.confidence  = src.confidence
        , tgt.updated_at  = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (nk_horse_id, jv_horse_id, source, confidence, created_at, updated_at)
    VALUES (src.nk_horse_id, src.jv_horse_id, src.source, src.confidence, SYSDATETIME(), SYSDATETIME());
";

            DbUtil.ExecuteNonQuery(
                conn,
                tx,
                mergeSql,
                (SqlParameterCollection p) => { },
                30
            );

            // 一時テーブル削除
            const string dropSql = @"DROP TABLE #TmpHorseIdMap;";

            DbUtil.ExecuteNonQuery(
                conn,
                tx,
                dropSql,
                (SqlParameterCollection p) => { },
                30
            );
        }

        /// <summary>
        /// IN句のパラメータ列（(@prefix0,@prefix1,...)）を生成します。
        /// </summary>
        private static string BuildInClause(string prefix, int count) {
            if (count <= 0) {
                return "(NULL)";
            }

            List<string> parts = new List<string>();

            for (int i = 0; i < count; i++) {
                parts.Add(prefix + i.ToString());
            }

            return "(" + string.Join(",", parts) + ")";
        }

        /// <summary>
        /// IN句パラメータを追加します。
        /// </summary>
        private static void AddInParameters(SqlParameterCollection parameters, string prefix, List<string> values, SqlDbType sqlType) {
            for (int i = 0; i < values.Count; i++) {
                string name = prefix + i.ToString();

                // Char/NVarChar の長さはSQL Server側で暗黙変換されるため、ここではDbUtil.CreateParameterに寄せる
                parameters.Add(DbUtil.CreateParameter(name, sqlType, values[i]));
            }
        }

        private sealed class NkJvRow {
            public string NkHorseId { get; set; } = string.Empty;
            public string JvHorseId { get; set; } = string.Empty;
        }

        private sealed class NameJvRow {
            public string HorseName { get; set; } = string.Empty;
            public string JvHorseId { get; set; } = string.Empty;
        }

        private sealed class HorseIdUpsertItem {
            public string NkHorseId { get; set; } = string.Empty;
            public string JvHorseId { get; set; } = string.Empty;
            public string Source { get; set; } = string.Empty;
            public int Confidence { get; set; }
        }
    }
}
