using System;
using Microsoft.Extensions.Configuration;

namespace KenshowLabo.Tools.Config
{
    /// <summary>
    /// アプリ設定を読み込む共通ローダーです。
    /// </summary>
    public static class AppConfigLoader
    {
        /// <summary>
        /// appsettings.json / appsettings.local.json を読み込みます。
        /// 実行ファイルのあるフォルダ（AppContext.BaseDirectory）を基準に探索します。
        /// </summary>
        public static IConfigurationRoot Load()
        {
            // 実行ファイルの配置先を基準ディレクトリにする
            string baseDir = AppContext.BaseDirectory;

            // 設定ビルダーを構築する
            IConfigurationBuilder builder = new ConfigurationBuilder()
                .SetBasePath(baseDir)
                .AddJsonFile("appsettings.json", optional: true, reloadOnChange: false)
                .AddJsonFile("appsettings.local.json", optional: true, reloadOnChange: false)
                .AddEnvironmentVariables();

            // 設定をビルドして返す
            IConfigurationRoot config = builder.Build();
            return config;
        }

        /// <summary>
        /// 指定キーの文字列設定を取得します。未設定の場合は空文字を返します。
        /// </summary>
        public static string GetString(IConfiguration config, string key)
        {
            string? value = config[key];

            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            return value;
        }

        /// <summary>
        /// 指定キーの文字列設定を取得します。未設定の場合は例外を送出します。
        /// </summary>
        public static string GetRequiredString(IConfiguration config, string key)
        {
            string? value = config[key];

            if (string.IsNullOrWhiteSpace(value))
            {
                throw new InvalidOperationException("設定が未定義です。key=" + key);
            }

            return value;
        }

        /// <summary>
        /// SQL Server の接続文字列を取得します（必須）。
        /// </summary>
        public static string GetSqlServerConnectionString(IConfiguration config)
        {
            // 将来の拡張を見据えてキーは明示的にする
            return GetRequiredString(config, "Db:SqlServer:ConnectionString");
        }

        /// <summary>
        /// SQLite の接続文字列を取得します（任意）。
        /// </summary>
        public static string GetSqliteConnectionString(IConfiguration config)
        {
            return GetString(config, "Db:Sqlite:ConnectionString");
        }
    }
}
