using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>Windows Firewall COM APIを管理Ruleだけに限定して利用します。</summary>
public sealed class WindowsFirewallService : IFirewallService
{
    public const string RulePrefix = "ASA Server Manager - ";
    public const string GameUdpRuleName = RulePrefix + "Game UDP";
    public const string RconTcpRuleName = RulePrefix + "RCON TCP";
    private readonly IWindowsFirewallPolicyAdapter _policyAdapter;
    private readonly IAppLogger _logger;
    private readonly string? _elevatedRequestDirectory;

    /// <summary>実Windows Firewall adapterでサービスを作成します。</summary>
    public WindowsFirewallService(IAppLogger logger, string? elevatedRequestDirectory = null) : this(new WindowsFirewallPolicyAdapter(), logger, elevatedRequestDirectory)
    {
    }

    /// <summary>テスト可能なpolicy adapterでサービスを作成します。</summary>
    public WindowsFirewallService(IWindowsFirewallPolicyAdapter policyAdapter, IAppLogger logger, string? elevatedRequestDirectory = null)
    {
        _policyAdapter = policyAdapter;
        _logger = logger;
        _elevatedRequestDirectory = elevatedRequestDirectory;
    }

    /// <inheritdoc />
    public async Task<FirewallSnapshot> InspectAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        try
        {
            IReadOnlyList<ManagedFirewallRule> rules = await _policyAdapter.ReadManagedRulesAsync(RulePrefix, cancellationToken);
            FirewallSnapshot snapshot = FirewallComparison.CreateSnapshot(requirements, rules);
            _logger.Info($"Firewall inspect: {snapshot.Readiness}.");
            return snapshot;
        }
        catch (PlatformNotSupportedException exception)
        {
            _logger.Error(exception, "Windows Firewall API is unavailable.");
            return new FirewallSnapshot { Readiness = FirewallReadiness.Unavailable, Detail = "Windows Firewall APIを利用できません。" };
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Firewall inspect failed.");
            return new FirewallSnapshot { Readiness = FirewallReadiness.Error, Detail = "Firewall状態の取得に失敗しました。" };
        }
    }

    /// <inheritdoc />
    public async Task<OperationResult> EnsureAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        try
        {
            await _policyAdapter.ReplaceManagedRulesAsync(RulePrefix, CreateRequiredRules(requirements), cancellationToken);
            _logger.Info("Firewall ensure completed.");
            return OperationResult.Success();
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Firewall ensure failed.");
            return OperationResult.Failure("Firewall設定の更新に失敗しました。", errorCode: "FIREWALL_ENSURE_FAILED", technicalMessage: exception.Message);
        }
    }

    /// <summary>helper requestを検証し、固定されたFirewall補正だけを実行します。</summary>
    public async Task<OperationResult> EnsureFromElevatedRequestAsync(string requestPath, CancellationToken cancellationToken)
    {
        if (!IsAllowedRequestPath(requestPath))
        {
            return OperationResult.Failure("昇格要求ファイルの場所が不正です。", errorCode: "FIREWALL_ENSURE_FAILED");
        }
        OperationResult<ElevatedFirewallRequest> requestResult = await ReadValidatedRequestAsync(requestPath, cancellationToken);
        if (!requestResult.Succeeded || requestResult.Value is null)
        {
            return OperationResult.Failure(requestResult.ErrorMessage ?? "昇格要求を検証できません。", errorCode: requestResult.ErrorCode ?? "FIREWALL_ENSURE_FAILED");
        }
        return await EnsureAsync(requestResult.Value.Requirements, cancellationToken);
    }

    /// <summary>昇格helperの入力を、許可された一種類の操作に限定して検証します。</summary>
    public static async Task<OperationResult<ElevatedFirewallRequest>> ReadValidatedRequestAsync(string requestPath, CancellationToken cancellationToken)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(requestPath) || !Path.IsPathFullyQualified(requestPath) || !File.Exists(requestPath))
            {
                return OperationResult<ElevatedFirewallRequest>.Failure("昇格要求ファイルが見つかりません。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            await using FileStream stream = File.OpenRead(requestPath);
            ElevatedFirewallRequest? request = await JsonSerializer.DeserializeAsync<ElevatedFirewallRequest>(stream, cancellationToken: cancellationToken);
            if (request is null || !string.Equals(request.Operation, "firewall-ensure", StringComparison.Ordinal) || request.Requirements is null)
            {
                return OperationResult<ElevatedFirewallRequest>.Failure("許可されていない昇格操作です。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            FirewallRequirements requirements = request.Requirements;
            if (string.IsNullOrWhiteSpace(requirements.ServerExecutablePath) || !Path.IsPathFullyQualified(requirements.ServerExecutablePath) || !string.Equals(Path.GetFileName(requirements.ServerExecutablePath), "ArkAscendedServer.exe", StringComparison.OrdinalIgnoreCase) || requirements.UdpInboundPorts.Count == 0 || requirements.UdpInboundPorts.Any(static port => port is < 1 or > 65535))
            {
                return OperationResult<ElevatedFirewallRequest>.Failure("昇格要求のFirewall設定が不正です。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            if (requirements.ExposeRcon && (requirements.RconTcpPort is null || requirements.RconTcpPort is < 1 or > 65535))
            {
                return OperationResult<ElevatedFirewallRequest>.Failure("昇格要求のRCON設定が不正です。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            return OperationResult<ElevatedFirewallRequest>.Success(request);
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException)
        {
            return OperationResult<ElevatedFirewallRequest>.Failure("昇格要求を読み込めません。", errorCode: "FIREWALL_ENSURE_FAILED");
        }
    }

    private bool IsAllowedRequestPath(string requestPath)
    {
        if (string.IsNullOrWhiteSpace(requestPath) || !Path.IsPathFullyQualified(requestPath))
        {
            return false;
        }
        if (string.IsNullOrWhiteSpace(_elevatedRequestDirectory))
        {
            return true;
        }
        string allowedDirectory = Path.TrimEndingDirectorySeparator(Path.GetFullPath(_elevatedRequestDirectory)) + Path.DirectorySeparatorChar;
        string fullRequestPath = Path.GetFullPath(requestPath);
        return fullRequestPath.StartsWith(allowedDirectory, StringComparison.OrdinalIgnoreCase);
    }

    private static IReadOnlyList<ManagedFirewallRule> CreateRequiredRules(FirewallRequirements requirements)
    {
        List<ManagedFirewallRule> rules = [new ManagedFirewallRule
        {
            Name = GameUdpRuleName,
            Enabled = true,
            IsInbound = true,
            Protocol = FirewallProtocol.Udp,
            LocalPorts = requirements.UdpInboundPorts.Distinct().OrderBy(static port => port).ToList(),
            ApplicationPath = requirements.ServerExecutablePath
        }];
        if (requirements.ExposeRcon && requirements.RconTcpPort is not null)
        {
            rules.Add(new ManagedFirewallRule
            {
                Name = RconTcpRuleName,
                Enabled = true,
                IsInbound = true,
                Protocol = FirewallProtocol.Tcp,
                LocalPorts = [requirements.RconTcpPort.Value],
                ApplicationPath = requirements.ServerExecutablePath
            });
        }
        return rules;
    }
}

/// <summary>Windows FirewallのCOM詳細をInfrastructure内に閉じ込めます。</summary>
public interface IWindowsFirewallPolicyAdapter
{
    /// <summary>prefixを持つ管理Ruleを読み取ります。</summary>
    Task<IReadOnlyList<ManagedFirewallRule>> ReadManagedRulesAsync(string rulePrefix, CancellationToken cancellationToken);

    /// <summary>prefixを持つ管理Ruleだけを置き換えます。</summary>
    Task ReplaceManagedRulesAsync(string rulePrefix, IReadOnlyList<ManagedFirewallRule> rules, CancellationToken cancellationToken);
}

/// <summary>HNetCfg.FwPolicy2 COM APIの実adapterです。</summary>
public sealed class WindowsFirewallPolicyAdapter : IWindowsFirewallPolicyAdapter
{
    private const int NetFwRuleDirectionIn = 1;
    private const int NetFwIpProtocolTcp = 6;
    private const int NetFwIpProtocolUdp = 17;

    /// <inheritdoc />
    public Task<IReadOnlyList<ManagedFirewallRule>> ReadManagedRulesAsync(string rulePrefix, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        dynamic policy = CreatePolicy();
        List<ManagedFirewallRule> result = [];
        foreach (dynamic rule in policy.Rules)
        {
            string name = rule.Name as string ?? string.Empty;
            if (!name.StartsWith(rulePrefix, StringComparison.Ordinal))
            {
                continue;
            }
            int protocolValue = (int)rule.Protocol;
            FirewallProtocol protocol = FirewallProtocol.Tcp;
            if (protocolValue == NetFwIpProtocolUdp)
            {
                protocol = FirewallProtocol.Udp;
            }
            result.Add(new ManagedFirewallRule
            {
                Name = name,
                Enabled = (bool)rule.Enabled,
                IsInbound = (int)rule.Direction == NetFwRuleDirectionIn,
                Protocol = protocol,
                LocalPorts = ParsePorts(rule.LocalPorts as string),
                ApplicationPath = rule.ApplicationName as string
            });
        }
        return Task.FromResult<IReadOnlyList<ManagedFirewallRule>>(result);
    }

    /// <inheritdoc />
    public Task ReplaceManagedRulesAsync(string rulePrefix, IReadOnlyList<ManagedFirewallRule> rules, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        dynamic policy = CreatePolicy();
        List<string> existingNames = [];
        foreach (dynamic rule in policy.Rules)
        {
            string name = rule.Name as string ?? string.Empty;
            if (name.StartsWith(rulePrefix, StringComparison.Ordinal))
            {
                existingNames.Add(name);
            }
        }
        foreach (string name in existingNames)
        {
            policy.Rules.Remove(name);
        }
        foreach (ManagedFirewallRule rule in rules)
        {
            dynamic firewallRule = Activator.CreateInstance(Type.GetTypeFromProgID("HNetCfg.FWRule") ?? throw new PlatformNotSupportedException("Windows Firewall COM is unavailable.")) ?? throw new InvalidOperationException("Firewall rule could not be created.");
            firewallRule.Name = rule.Name;
            firewallRule.Description = "Managed by ASA Server Manager.";
            firewallRule.ApplicationName = rule.ApplicationPath;
            int protocol = NetFwIpProtocolTcp;
            if (rule.Protocol == FirewallProtocol.Udp)
            {
                protocol = NetFwIpProtocolUdp;
            }
            firewallRule.Protocol = protocol;
            firewallRule.LocalPorts = string.Join(',', rule.LocalPorts);
            firewallRule.Direction = NetFwRuleDirectionIn;
            firewallRule.Enabled = true;
            firewallRule.Action = 1;
            firewallRule.Profiles = int.MaxValue;
            policy.Rules.Add(firewallRule);
        }
        return Task.CompletedTask;
    }

    private static dynamic CreatePolicy()
    {
        Type policyType = Type.GetTypeFromProgID("HNetCfg.FwPolicy2") ?? throw new PlatformNotSupportedException("Windows Firewall COM is unavailable.");
        return Activator.CreateInstance(policyType) ?? throw new PlatformNotSupportedException("Windows Firewall COM is unavailable.");
    }

    private static IReadOnlyList<int> ParsePorts(string? ports)
    {
        if (string.IsNullOrWhiteSpace(ports))
        {
            return [];
        }
        List<int> parsed = [];
        foreach (string token in ports.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries))
        {
            if (int.TryParse(token, out int port) && port is >= 1 and <= 65535)
            {
                parsed.Add(port);
            }
        }
        return parsed;
    }
}
