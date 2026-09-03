using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>サーバー設定からFirewall要求を一箇所で構築します。</summary>
public sealed class FirewallRequirementsBuilder
{
    /// <summary>ゲーム、Peer、Queryおよび必要時のRCON公開要求を返します。</summary>
    public OperationResult<FirewallRequirements> Build(ServerSettings settings)
    {
        int[] configuredPorts = [settings.Ports.GamePort, settings.Ports.PeerPort, settings.Ports.QueryPort];
        if (configuredPorts.Any(static port => port is < 1 or > 65535))
        {
            return OperationResult<FirewallRequirements>.Failure("Firewall対象のポート番号が不正です。", errorCode: "CFG_INVALID_PORT");
        }
        if (settings.RconEnabled && settings.ExposeRcon && (settings.Ports.RconPort is < 1 or > 65535))
        {
            return OperationResult<FirewallRequirements>.Failure("RCONポート番号が不正です。", errorCode: "CFG_INVALID_PORT");
        }
        string executablePath = Path.Combine(settings.DedicatedServerPath, "ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe");
        List<int> udpPorts = configuredPorts.Distinct().OrderBy(static port => port).ToList();
        bool exposeRcon = settings.RconEnabled && settings.ExposeRcon;
        int? rconPort = null;
        if (exposeRcon)
        {
            rconPort = settings.Ports.RconPort;
        }
        return OperationResult<FirewallRequirements>.Success(new FirewallRequirements
        {
            ServerExecutablePath = executablePath,
            UdpInboundPorts = udpPorts,
            ExposeRcon = exposeRcon,
            RconTcpPort = rconPort
        });
    }
}

/// <summary>管理対象Ruleと要求との差分をWindows APIから独立して評価します。</summary>
public static class FirewallComparison
{
    /// <summary>管理Ruleだけを比較し、実際の受信Portを含むスナップショットを返します。</summary>
    public static FirewallSnapshot CreateSnapshot(FirewallRequirements requirements, IReadOnlyList<ManagedFirewallRule> managedRules, string? detail = null)
    {
        List<ManagedFirewallRule> udpRules = managedRules.Where(static rule => rule.Protocol == FirewallProtocol.Udp && rule.IsInbound && rule.Enabled).ToList();
        List<ManagedFirewallRule> tcpRules = managedRules.Where(static rule => rule.Protocol == FirewallProtocol.Tcp && rule.IsInbound && rule.Enabled).ToList();
        List<int> actualUdpPorts = udpRules.SelectMany(static rule => rule.LocalPorts).Distinct().OrderBy(static port => port).ToList();
        List<int> expectedUdpPorts = requirements.UdpInboundPorts.Distinct().OrderBy(static port => port).ToList();
        int? actualRconPort = null;
        if (tcpRules.Count == 1 && tcpRules[0].LocalPorts.Count == 1)
        {
            actualRconPort = tcpRules[0].LocalPorts[0];
        }
        bool pathMatches = managedRules.All(rule => string.IsNullOrWhiteSpace(rule.ApplicationPath) || PathsEqual(rule.ApplicationPath, requirements.ServerExecutablePath));
        bool udpMatches = expectedUdpPorts.SequenceEqual(actualUdpPorts) && udpRules.All(static rule => rule.Enabled && rule.IsInbound);
        bool rconMatches = !requirements.ExposeRcon || (tcpRules.Count == 1 && actualRconPort == requirements.RconTcpPort);
        bool noUnexpectedRcon = requirements.ExposeRcon || tcpRules.Count == 0;
        bool readiness = udpMatches && rconMatches && noUnexpectedRcon && pathMatches;
        FirewallReadiness state = FirewallReadiness.NeedsUpdate;
        if (readiness)
        {
            state = FirewallReadiness.Ready;
        }
        return new FirewallSnapshot
        {
            Readiness = state,
            ExpectedUdpPorts = expectedUdpPorts,
            ActualUdpPorts = actualUdpPorts,
            ExpectedRconExposed = requirements.ExposeRcon,
            ActualRconExposed = tcpRules.Count > 0,
            ExpectedRconTcpPort = requirements.RconTcpPort,
            ActualRconTcpPort = actualRconPort,
            Detail = detail
        };
    }

    private static bool PathsEqual(string left, string right)
    {
        return string.Equals(Path.GetFullPath(left), Path.GetFullPath(right), StringComparison.OrdinalIgnoreCase);
    }
}

/// <summary>起動を妨げず、設定済みとみなすテスト・開発用Firewallサービスです。</summary>
public sealed class ReadyFirewallService : IFirewallService
{
    /// <inheritdoc />
    public Task<FirewallSnapshot> InspectAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        List<ManagedFirewallRule> rules = [new ManagedFirewallRule
        {
            Name = "Ready test rule",
            Enabled = true,
            IsInbound = true,
            Protocol = FirewallProtocol.Udp,
            LocalPorts = requirements.UdpInboundPorts,
            ApplicationPath = requirements.ServerExecutablePath
        }];
        if (requirements.ExposeRcon && requirements.RconTcpPort is not null)
        {
            rules.Add(new ManagedFirewallRule
            {
                Name = "Ready test RCON rule",
                Enabled = true,
                IsInbound = true,
                Protocol = FirewallProtocol.Tcp,
                LocalPorts = [requirements.RconTcpPort.Value],
                ApplicationPath = requirements.ServerExecutablePath
            });
        }
        FirewallSnapshot snapshot = FirewallComparison.CreateSnapshot(requirements, rules);
        return Task.FromResult(snapshot);
    }

    /// <inheritdoc />
    public Task<OperationResult> EnsureAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        return Task.FromResult(OperationResult.Success());
    }
}
