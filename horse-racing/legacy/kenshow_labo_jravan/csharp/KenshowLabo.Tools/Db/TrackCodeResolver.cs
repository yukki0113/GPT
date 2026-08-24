using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;

namespace KenshowLabo.Tools.Db
{
    /// <summary>
    /// 競馬場名からJV準拠の場CD（2桁）を解決します。
    /// </summary>
    public sealed class TrackCodeResolver
    {
        private readonly string _connectionString;
        private readonly Dictionary<string, string> _cache;

        /// <summary>
        /// コンストラクタです。
        /// </summary>
        public TrackCodeResolver(string connectionString)
        {
            if (string.IsNullOrWhiteSpace(connectionString))
            {
                throw new ArgumentException("connectionString is empty.");
            }

            this._connectionString = connectionString;
            this._cache = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }

        /// <summary>
        /// 競馬場名から場CD（2桁）を取得します（見つからない場合は例外）。
        /// </summary>
        public string ResolveTrackCode(string trackName)
        {
            if (string.IsNullOrWhiteSpace(trackName))
            {
                throw new ArgumentException("trackName is empty.");
            }

            // 念のためトリムして正規化
            string normalized = trackName.Trim();

            // キャッシュヒット
            if (this._cache.TryGetValue(normalized, out string? cached) && cached != null)
            {
                return cached;
            }

            // DB問い合わせ
            string sql =
                "SELECT track_cd " +
                "FROM dbo.MT_Track " +
                "WHERE track_name = @track_name;";

            string trackCd = QuerySingleTrackCd(sql, normalized);

            // DBに無ければ例外（後でAlias導入するならここを拡張）
            if (string.IsNullOrWhiteSpace(trackCd))
            {
                throw new InvalidOperationException("MT_Track に競馬場名が見つかりません: " + normalized);
            }

            // キャッシュ
            this._cache[normalized] = trackCd;

            return trackCd;
        }

        /// <summary>
        /// track_cd を1件取得します（無ければ空文字）。
        /// </summary>
        private string QuerySingleTrackCd(string sql, string trackName)
        {
            // DbUtil の QueryToList / ExecuteScalar の実装差異を避けるため、ここは素直にADOで書きます
            using (SqlConnection conn = new SqlConnection(this._connectionString))
            {
                conn.Open();

                using (SqlCommand cmd = new SqlCommand(sql, conn))
                {
                    cmd.CommandType = CommandType.Text;

                    // CreateParameter は (name, type, value) 版に合わせる
                    SqlParameter p = DbUtil.CreateParameter("@track_name", SqlDbType.NVarChar, trackName);
                    p.Size = 10; // MT_Track.track_name に合わせる（3でも良いが将来拡張を見て10）
                    cmd.Parameters.Add(p);

                    object result = cmd.ExecuteScalar();
                    if (result == null || result == DBNull.Value)
                    {
                        return string.Empty;
                    }

                    return Convert.ToString(result) ?? string.Empty;
                }
            }
        }
    }
}
