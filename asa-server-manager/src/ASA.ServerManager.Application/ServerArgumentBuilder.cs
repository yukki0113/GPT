using System.Text;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>ASA起動引数と、秘密情報を伏せたログ用引数を構築します。</summary>
public sealed class ServerArgumentBuilder
{
    /// <summary>設定と秘密情報からASA起動引数を構築します。</summary>
    public OperationResult<ServerArgumentBuildResult> Build(ServerSettings settings, ServerSecrets secrets)
    {
        if (string.IsNullOrWhiteSpace(settings.MapLevelName))
        {
            return OperationResult<ServerArgumentBuildResult>.Failure("MAPのLevel Nameが未設定です。", errorCode: "CFG_REQUIRED_MISSING");
        }
        if (string.IsNullOrWhiteSpace(settings.ServerName))
        {
            return OperationResult<ServerArgumentBuildResult>.Failure("サーバー名が未設定です。", errorCode: "CFG_REQUIRED_MISSING");
        }
        if (ContainsModsArgument(settings.ExtraArguments))
        {
            return OperationResult<ServerArgumentBuildResult>.Failure("ExtraArgumentsに-mods指定は追加できません。", errorCode: "CFG_INVALID_ARGUMENT");
        }

        List<string> modIds = GetOrderedModIds(settings);
        StringBuilder actual = new StringBuilder();
        StringBuilder masked = new StringBuilder();
        actual.Append(settings.MapLevelName);
        masked.Append(settings.MapLevelName);
        AppendQuery(actual, masked, "SessionName", settings.ServerName, settings.ServerName);
        AppendQuery(actual, masked, "Port", settings.Ports.GamePort.ToString(), settings.Ports.GamePort.ToString());
        AppendQuery(actual, masked, "QueryPort", settings.Ports.QueryPort.ToString(), settings.Ports.QueryPort.ToString());
        AppendQuery(actual, masked, "MaxPlayers", settings.MaxPlayers.ToString(), settings.MaxPlayers.ToString());
        if (settings.RconEnabled)
        {
            AppendQuery(actual, masked, "RCONEnabled", "True", "True");
            AppendQuery(actual, masked, "RCONPort", settings.Ports.RconPort.ToString(), settings.Ports.RconPort.ToString());
        }
        AppendSwitch(actual, masked, "ServerPassword", secrets.ServerPassword, "***");
        AppendSwitch(actual, masked, "ServerAdminPassword", secrets.AdminPassword, "***");
        if (settings.RconEnabled && !string.IsNullOrWhiteSpace(secrets.RconPassword))
        {
            AppendSwitch(actual, masked, "RCONServerPassword", secrets.RconPassword, "***");
        }
        if (modIds.Count > 0)
        {
            string joined = string.Join(',', modIds);
            actual.Append(" -mods=").Append(joined);
            masked.Append(" -mods=").Append(joined);
        }
        if (!string.IsNullOrWhiteSpace(settings.ExtraArguments))
        {
            actual.Append(' ').Append(settings.ExtraArguments.Trim());
            masked.Append(' ').Append(settings.ExtraArguments.Trim());
        }
        return OperationResult<ServerArgumentBuildResult>.Success(new ServerArgumentBuildResult(actual.ToString(), masked.ToString()));
    }

    private static void AppendQuery(StringBuilder actual, StringBuilder masked, string key, string actualValue, string maskedValue)
    {
        actual.Append('?').Append(key).Append('=').Append(actualValue);
        masked.Append('?').Append(key).Append('=').Append(maskedValue);
    }

    private static void AppendSwitch(StringBuilder actual, StringBuilder masked, string key, string actualValue, string maskedValue)
    {
        if (string.IsNullOrWhiteSpace(actualValue))
        {
            return;
        }
        actual.Append(" -").Append(key).Append('=').Append(actualValue);
        masked.Append(" -").Append(key).Append('=').Append(maskedValue);
    }

    private static List<string> GetOrderedModIds(ServerSettings settings)
    {
        List<string> values = [];
        if (!string.IsNullOrWhiteSpace(settings.CustomMapModProjectId))
        {
            values.Add(settings.CustomMapModProjectId);
        }
        foreach (ModDefinition mod in settings.Mods.Where(static item => item.Enabled).OrderBy(static item => item.Order))
        {
            if (!values.Contains(mod.ProjectId, StringComparer.Ordinal))
            {
                values.Add(mod.ProjectId);
            }
        }
        return values;
    }

    private static bool ContainsModsArgument(string extraArguments)
    {
        return extraArguments.Contains("-mods=", StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>実行用とログ用の引数を対で保持します。</summary>
public sealed record ServerArgumentBuildResult(string Arguments, string MaskedArguments);
