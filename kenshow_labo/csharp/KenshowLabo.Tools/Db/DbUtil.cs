using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.Data.SqlClient;

namespace KenshowLabo.Tools.Db
{
    /// <summary>
    /// SQL Server 実行の共通ユーティリティです。
    /// ※責務は「SQL実行」「トランザクション」に限定します。
    /// </summary>
    public static class DbUtil
    {
        /// <summary>
        /// SQL Serverに接続し、クエリを実行して結果を List&lt;T&gt; に詰めて返します。
        /// </summary>
        public static List<T> QueryToList<T>(
            string connectionString,
            string sql,
            Action<SqlParameterCollection> addParameters,
            Func<SqlDataReader, T> mapRow,
            int commandTimeoutSeconds = 30)
        {
            // 結果格納
            List<T> list = new List<T>();

            // 接続を開く
            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                conn.Open();

                // コマンドを準備する
                using (SqlCommand cmd = new SqlCommand(sql, conn))
                {
                    cmd.CommandType = CommandType.Text;

                    // タイムアウト設定（重い集計・取込で必要になる）
                    cmd.CommandTimeout = commandTimeoutSeconds;

                    // パラメータを追加する
                    if (addParameters != null)
                    {
                        addParameters(cmd.Parameters);
                    }

                    // 実行して読み取る
                    using (SqlDataReader reader = cmd.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            // 1行 → 1要素に変換して追加する
                            T item = mapRow(reader);
                            list.Add(item);
                        }
                    }
                }
            }

            return list;
        }

        /// <summary>
        /// SQL Serverに接続し、非クエリ（INSERT/UPDATE/DELETE）を実行します。
        /// </summary>
        public static int ExecuteNonQuery(
            string connectionString,
            string sql,
            Action<SqlParameterCollection> addParameters,
            int commandTimeoutSeconds = 30)
        {
            int affectedRows = 0;

            // 接続を開く
            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                conn.Open();

                // コマンドを準備する
                using (SqlCommand cmd = new SqlCommand(sql, conn))
                {
                    cmd.CommandType = CommandType.Text;

                    // タイムアウト設定
                    cmd.CommandTimeout = commandTimeoutSeconds;

                    // パラメータを追加する
                    if (addParameters != null)
                    {
                        addParameters(cmd.Parameters);
                    }

                    // 実行
                    affectedRows = cmd.ExecuteNonQuery();
                }
            }

            return affectedRows;
        }

        /// <summary>
        /// SQL Serverに接続し、スカラー値を取得します（DBNull/NULL の場合は default を返します）。
        /// </summary>
        public static T? ExecuteScalar<T>(
            string connectionString,
            string sql,
            Action<SqlParameterCollection> addParameters,
            int commandTimeoutSeconds = 30)
        {
            object result;

            // 接続を開く
            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                conn.Open();

                // コマンドを準備する
                using (SqlCommand cmd = new SqlCommand(sql, conn))
                {
                    cmd.CommandType = CommandType.Text;

                    // タイムアウト設定
                    cmd.CommandTimeout = commandTimeoutSeconds;

                    // パラメータを追加する
                    if (addParameters != null)
                    {
                        addParameters(cmd.Parameters);
                    }

                    // 実行
                    result = cmd.ExecuteScalar();
                }
            }

            // NULL/DBNull の場合
            if (result == null || result == DBNull.Value)
            {
                return default(T);
            }

            // 既に型が一致している場合はそのまま返す
            if (result is T)
            {
                return (T)result;
            }

            // Nullable<T> を考慮して変換する
            Type targetType = typeof(T);
            Type? underlyingType = Nullable.GetUnderlyingType(targetType);
            if (underlyingType != null)
            {
                targetType = underlyingType;
            }

            object converted = Convert.ChangeType(result, targetType);
            return (T)converted;
        }

        /// <summary>
        /// トランザクション内で処理を実行します（例：取込の一括INSERT/UPDATE）。
        /// </summary>
        public static void ExecuteInTransaction(
            string connectionString,
            Action<SqlConnection, SqlTransaction> action)
        {
            // 接続を開く
            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                conn.Open();

                // トランザクション開始
                using (SqlTransaction tx = conn.BeginTransaction())
                {
                    try
                    {
                        // 呼び出し側処理を実行
                        action(conn, tx);

                        // コミット
                        tx.Commit();
                    }
                    catch
                    {
                        // ロールバック（失敗しても原例外を優先）
                        try
                        {
                            tx.Rollback();
                        }
                        catch
                        {
                            // rollback失敗は握りつぶし
                        }

                        throw;
                    }
                }
            }
        }

        /// <summary>
        /// 既存の接続・トランザクション内で非クエリ（INSERT/UPDATE/DELETE）を実行します。
        /// </summary>
        public static int ExecuteNonQuery(
            SqlConnection conn,
            SqlTransaction tx,
            string sql,
            Action<SqlParameterCollection> addParameters,
            int commandTimeoutSeconds = 30) {
            int affectedRows = 0;

            // 入力チェック
            if (conn == null) {
                throw new ArgumentNullException(nameof(conn));
            }

            if (tx == null) {
                throw new ArgumentNullException(nameof(tx));
            }

            if (string.IsNullOrWhiteSpace(sql)) {
                throw new ArgumentException("sql is null or empty.", nameof(sql));
            }

            // コマンドを準備する（トランザクションに紐づける）
            using (SqlCommand cmd = new SqlCommand(sql, conn, tx)) {
                cmd.CommandType = CommandType.Text;

                // タイムアウト設定
                cmd.CommandTimeout = commandTimeoutSeconds;

                // パラメータを追加する
                if (addParameters != null) {
                    addParameters(cmd.Parameters);
                }

                // 実行
                affectedRows = cmd.ExecuteNonQuery();
            }

            return affectedRows;
        }

        /// <summary>
        /// 既存の接続・トランザクション内でスカラー値を取得します（DBNull/NULL の場合は default を返します）。
        /// </summary>
        public static T? ExecuteScalar<T>(
            SqlConnection conn,
            SqlTransaction tx,
            string sql,
            Action<SqlParameterCollection> addParameters,
            int commandTimeoutSeconds = 30) 
        {
            object result;

            // 入力チェック
            if (conn == null) {
                throw new ArgumentNullException(nameof(conn));
            }

            if (tx == null) {
                throw new ArgumentNullException(nameof(tx));
            }

            if (string.IsNullOrWhiteSpace(sql)) {
                throw new ArgumentException("sql is null or empty.", nameof(sql));
            }

            // コマンドを準備する（トランザクションに紐づける）
            using (SqlCommand cmd = new SqlCommand(sql, conn, tx)) {
                cmd.CommandType = CommandType.Text;

                // タイムアウト設定
                cmd.CommandTimeout = commandTimeoutSeconds;

                // パラメータを追加する
                if (addParameters != null) {
                    addParameters(cmd.Parameters);
                }

                // 実行
                result = cmd.ExecuteScalar();
            }

            // NULL/DBNull の場合
            if (result == null || result == DBNull.Value) {
                return default(T);
            }

            // 既に型が一致している場合はそのまま返す
            if (result is T) {
                return (T)result;
            }

            // Nullable<T> を考慮して変換する
            Type targetType = typeof(T);
            Type? underlyingType = Nullable.GetUnderlyingType(targetType);
            if (underlyingType != null) {
                targetType = underlyingType;
            }

            object converted = Convert.ChangeType(result, targetType);
            return (T)converted;
        }

        /// <summary>
        /// 既存の接続・トランザクション内でクエリを実行し、結果を List&lt;T&gt; に詰めて返します。
        /// </summary>
        public static List<T> QueryToList<T>(
            SqlConnection conn,
            SqlTransaction tx,
            string sql,
            Action<SqlParameterCollection> addParameters,
            Func<SqlDataReader, T> mapRow,
            int commandTimeoutSeconds = 30) {
            List<T> list = new List<T>();

            // 入力チェック
            if (conn == null) {
                throw new ArgumentNullException(nameof(conn));
            }

            if (tx == null) {
                throw new ArgumentNullException(nameof(tx));
            }

            if (string.IsNullOrWhiteSpace(sql)) {
                throw new ArgumentException("sql is null or empty.", nameof(sql));
            }

            if (mapRow == null) {
                throw new ArgumentNullException(nameof(mapRow));
            }

            // コマンドを準備する（トランザクションに紐づける）
            using (SqlCommand cmd = new SqlCommand(sql, conn, tx)) {
                cmd.CommandType = CommandType.Text;

                // タイムアウト設定
                cmd.CommandTimeout = commandTimeoutSeconds;

                // パラメータを追加する
                if (addParameters != null) {
                    addParameters(cmd.Parameters);
                }

                // 実行して読み取る
                using (SqlDataReader reader = cmd.ExecuteReader()) {
                    while (reader.Read()) {
                        T item = mapRow(reader);
                        list.Add(item);
                    }
                }
            }

            return list;
        }

        /// <summary>
        /// SqlParameter を作成します（NULL は DBNull.Value に置換します）。
        /// </summary>
        public static SqlParameter CreateParameter(string name, SqlDbType type, object? value)
        {
            SqlParameter p = new SqlParameter(name, type);

            // NULL をそのまま渡すと例外や意図しない挙動になりやすいため変換する
            if (value == null)
            {
                p.Value = DBNull.Value;
            }
            else
            {
                p.Value = value;
            }

            return p;
        }

        /// <summary>
        /// SQL Serverのストアドプロシージャを実行します（戻り値は影響行数）。
        /// </summary>
        public static int ExecuteStoredProcedure(
            string connectionString,
            string storedProcedureName,
            Action<SqlParameterCollection>? addParameters,
            int commandTimeoutSeconds = 0) // 0 = 無制限（重い展開向け）
        {
            int affectedRows = 0;

            using (SqlConnection conn = new SqlConnection(connectionString))
            {
                conn.Open();

                using (SqlCommand cmd = new SqlCommand(storedProcedureName, conn))
                {
                    // ストアド実行
                    cmd.CommandType = CommandType.StoredProcedure;

                    // タイムアウト（展開は長い可能性があるので無制限推奨）
                    cmd.CommandTimeout = commandTimeoutSeconds;

                    // パラメータがあれば追加（今回はNULLでOK）
                    if (addParameters != null)
                    {
                        addParameters(cmd.Parameters);
                    }

                    affectedRows = cmd.ExecuteNonQuery();
                }
            }

            return affectedRows;
        }

        /// <summary>
        /// DataTable を SqlBulkCopy で一括投入します（トランザクション無し）。
        /// </summary>
        /// <param name="connectionString">接続文字列</param>
        /// <param name="destinationTableName">投入先テーブル名（例：dbo.IF_Nk_RaceEntryRow）</param>
        /// <param name="dataTable">投入するDataTable</param>
        /// <param name="addColumnMappings">列マッピング追加（任意）</param>
        /// <param name="batchSize">バッチサイズ</param>
        /// <param name="commandTimeoutSeconds">タイムアウト（0=無制限）</param>
        /// <param name="options">SqlBulkCopyOptions</param>
        public static void BulkInsertDataTable(
            string connectionString,
            string destinationTableName,
            DataTable dataTable,
            Action<SqlBulkCopyColumnMappingCollection>? addColumnMappings,
            int batchSize = 5000,
            int commandTimeoutSeconds = 0,
            SqlBulkCopyOptions options = SqlBulkCopyOptions.Default) {
            // 入力チェック
            if (string.IsNullOrWhiteSpace(connectionString)) {
                throw new ArgumentException("connectionString is null or empty.", nameof(connectionString));
            }

            if (string.IsNullOrWhiteSpace(destinationTableName)) {
                throw new ArgumentException("destinationTableName is null or empty.", nameof(destinationTableName));
            }

            if (dataTable == null) {
                throw new ArgumentNullException(nameof(dataTable));
            }

            // 0件は何もしない（INSERT相当の挙動として自然）
            if (dataTable.Rows.Count == 0) {
                return;
            }

            // 接続を開く
            using (SqlConnection conn = new SqlConnection(connectionString)) {
                conn.Open();

                // BulkCopy実行
                using (SqlBulkCopy bulk = new SqlBulkCopy(conn, options, null)) {
                    // 投入先
                    bulk.DestinationTableName = destinationTableName;

                    // パフォーマンス系
                    bulk.BatchSize = batchSize;
                    bulk.BulkCopyTimeout = commandTimeoutSeconds;

                    // 列マッピング（呼び出し側で明示したい場合）
                    if (addColumnMappings != null) {
                        addColumnMappings(bulk.ColumnMappings);
                    }

                    // 実行
                    bulk.WriteToServer(dataTable);
                }
            }
        }

        /// <summary>
        /// DataTable を SqlBulkCopy で一括投入します（既存トランザクション内）。
        /// </summary>
        /// <param name="conn">接続（Open済み想定）</param>
        /// <param name="tx">トランザクション</param>
        /// <param name="destinationTableName">投入先テーブル名</param>
        /// <param name="dataTable">投入するDataTable</param>
        /// <param name="addColumnMappings">列マッピング追加（任意）</param>
        /// <param name="batchSize">バッチサイズ</param>
        /// <param name="commandTimeoutSeconds">タイムアウト（0=無制限）</param>
        /// <param name="options">SqlBulkCopyOptions</param>
        public static void BulkInsertDataTable(
            SqlConnection conn,
            SqlTransaction tx,
            string destinationTableName,
            DataTable dataTable,
            Action<SqlBulkCopyColumnMappingCollection>? addColumnMappings,
            int batchSize = 5000,
            int commandTimeoutSeconds = 0,
            SqlBulkCopyOptions options = SqlBulkCopyOptions.Default) {
            // 入力チェック
            if (conn == null) {
                throw new ArgumentNullException(nameof(conn));
            }

            if (tx == null) {
                throw new ArgumentNullException(nameof(tx));
            }

            if (string.IsNullOrWhiteSpace(destinationTableName)) {
                throw new ArgumentException("destinationTableName is null or empty.", nameof(destinationTableName));
            }

            if (dataTable == null) {
                throw new ArgumentNullException(nameof(dataTable));
            }

            // 0件は何もしない
            if (dataTable.Rows.Count == 0) {
                return;
            }

            // BulkCopy実行（トランザクションに紐づける）
            using (SqlBulkCopy bulk = new SqlBulkCopy(conn, options, tx)) {
                // 投入先
                bulk.DestinationTableName = destinationTableName;

                // パフォーマンス系
                bulk.BatchSize = batchSize;
                bulk.BulkCopyTimeout = commandTimeoutSeconds;

                // 列マッピング
                if (addColumnMappings != null) {
                    addColumnMappings(bulk.ColumnMappings);
                }

                // 実行
                bulk.WriteToServer(dataTable);
            }
        }

    }
}
