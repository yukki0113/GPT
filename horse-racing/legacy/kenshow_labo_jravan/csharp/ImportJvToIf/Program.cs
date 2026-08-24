using KenshowLabo.Tools.Config;
using KenshowLabo.Tools.Db;
using KenshowLabo.Tools.Domain;
using KenshowLabo.Tools.Domain.JvIf;
using Microsoft.Extensions.Configuration;
using System;

namespace ImportJvToIf
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            IConfigurationRoot config = AppConfigLoader.Load();

            string sqlServerCs = AppConfigLoader.GetSqlServerConnectionString(config);
            string sqliteCs = AppConfigLoader.GetSqliteConnectionString(config);

            int fromYear = ReadIntOrDefault(config, "Import:FromYear", 2016);
            int toYear = ReadIntOrDefault(config, "Import:ToYear", DateTime.Now.Year);

            // 1) SQLite → IF
            JvRaceToIfImportService service = new JvRaceToIfImportService(sqlServerCs, sqliteCs);
            service.ImportByYearRange(fromYear, toYear);

            JvRaceUmaToIfImportService umaService = new JvRaceUmaToIfImportService(sqlServerCs, sqliteCs);
            umaService.ImportByYearRange(fromYear, toYear);

            JvPayToIfImportService payService = new JvPayToIfImportService(sqlServerCs, sqliteCs);
            payService.ImportByYearRange(fromYear, toYear);

            JvWin5TargetToIfImportService win5Service = new JvWin5TargetToIfImportService(sqlServerCs, sqliteCs);
            win5Service.ImportByYearRange(fromYear, toYear);

            JvHorsePedigreeToIfImportService pedService = new JvHorsePedigreeToIfImportService(sqlServerCs, sqliteCs);
            pedService.ImportMissing(batchSize: 1000);


            // 2) IF → TR/MT 展開（追加）
            Console.WriteLine("[EXPAND] start dbo.usp_JV_Expand_All");

            // タイムアウトは無制限(0)推奨。必要なら 600 などでもOKです。
            DbUtil.ExecuteStoredProcedure(
                sqlServerCs,
                "dbo.usp_JV_Expand_All",
                null,
                commandTimeoutSeconds: 0);

            Console.WriteLine("[EXPAND] end dbo.usp_JV_Expand_All");

            return 0;
        }

        private static int ReadIntOrDefault(IConfiguration config, string key, int defaultValue)
        {
            string? value = config[key];
            if (string.IsNullOrWhiteSpace(value))
            {
                return defaultValue;
            }

            int parsed;
            if (!int.TryParse(value, out parsed))
            {
                return defaultValue;
            }

            return parsed;
        }
    }
}
