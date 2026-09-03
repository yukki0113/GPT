using System.Net;
using System.Net.NetworkInformation;
using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class FirewallRequirementsBuilderTests
{
    [Fact]
    public void Build_CreatesDistinctUdpPortsAndDoesNotExposeLocalRcon()
    {
        ServerSettings settings = CreateSettings();
        settings.Ports.PeerPort = settings.Ports.GamePort;
        OperationResult<FirewallRequirements> result = new FirewallRequirementsBuilder().Build(settings);
        Assert.True(result.Succeeded);
        Assert.Equal(new[] { 7777, 27015 }, result.Value?.UdpInboundPorts);
        Assert.False(result.Value?.ExposeRcon);
        Assert.Null(result.Value?.RconTcpPort);
    }

    [Fact]
    public void Build_ExposesRconOnlyWhenEnabledAndExplicitlyRequested()
    {
        ServerSettings settings = CreateSettings();
        settings.ExposeRcon = true;
        OperationResult<FirewallRequirements> result = new FirewallRequirementsBuilder().Build(settings);
        Assert.True(result.Succeeded);
        Assert.True(result.Value?.ExposeRcon);
        Assert.Equal(27020, result.Value?.RconTcpPort);
    }

    [Fact]
    public void Build_RejectsInvalidPort()
    {
        ServerSettings settings = CreateSettings();
        settings.Ports.QueryPort = 0;
        OperationResult<FirewallRequirements> result = new FirewallRequirementsBuilder().Build(settings);
        Assert.False(result.Succeeded);
        Assert.Equal("CFG_INVALID_PORT", result.ErrorCode);
    }

    private static ServerSettings CreateSettings()
    {
        return new ServerSettings { DedicatedServerPath = "C:\\ASA", RconEnabled = true, Ports = new PortSettings() };
    }
}

public sealed class FirewallComparisonTests
{
    [Fact]
    public void CreateSnapshot_ReturnsReadyForExactManagedRules()
    {
        FirewallRequirements requirements = CreateRequirements(exposeRcon: true);
        FirewallSnapshot snapshot = FirewallComparison.CreateSnapshot(requirements, [CreateUdpRule(), CreateRconRule()]);
        Assert.Equal(FirewallReadiness.Ready, snapshot.Readiness);
    }

    [Fact]
    public void CreateSnapshot_ReturnsNeedsUpdateForMissingOrStalePort()
    {
        FirewallRequirements requirements = CreateRequirements(exposeRcon: false);
        ManagedFirewallRule rule = CreateUdpRule([7777, 9999]);
        FirewallSnapshot snapshot = FirewallComparison.CreateSnapshot(requirements, [rule]);
        Assert.Equal(FirewallReadiness.NeedsUpdate, snapshot.Readiness);
    }

    [Fact]
    public void CreateSnapshot_ReturnsNeedsUpdateForDisabledRuleOrUnexpectedRcon()
    {
        FirewallRequirements requirements = CreateRequirements(exposeRcon: false);
        ManagedFirewallRule disabled = CreateUdpRule();
        disabled = new ManagedFirewallRule { Name = disabled.Name, Enabled = false, IsInbound = disabled.IsInbound, Protocol = disabled.Protocol, LocalPorts = disabled.LocalPorts, ApplicationPath = disabled.ApplicationPath };
        FirewallSnapshot snapshot = FirewallComparison.CreateSnapshot(requirements, [disabled, CreateRconRule()]);
        Assert.Equal(FirewallReadiness.NeedsUpdate, snapshot.Readiness);
    }

    private static FirewallRequirements CreateRequirements(bool exposeRcon)
    {
        int? rcon = null;
        if (exposeRcon)
        {
            rcon = 27020;
        }
        return new FirewallRequirements { ServerExecutablePath = "C:\\ASA\\ArkAscendedServer.exe", UdpInboundPorts = [7777, 7778, 27015], ExposeRcon = exposeRcon, RconTcpPort = rcon };
    }

    private static ManagedFirewallRule CreateUdpRule(IReadOnlyList<int>? ports = null)
    {
        return new ManagedFirewallRule { Name = WindowsFirewallService.GameUdpRuleName, Enabled = true, IsInbound = true, Protocol = FirewallProtocol.Udp, LocalPorts = ports ?? [7777, 7778, 27015], ApplicationPath = "C:\\ASA\\ArkAscendedServer.exe" };
    }

    private static ManagedFirewallRule CreateRconRule()
    {
        return new ManagedFirewallRule { Name = WindowsFirewallService.RconTcpRuleName, Enabled = true, IsInbound = true, Protocol = FirewallProtocol.Tcp, LocalPorts = [27020], ApplicationPath = "C:\\ASA\\ArkAscendedServer.exe" };
    }
}

public sealed class ElevatedFirewallRequestTests
{
    [Fact]
    public async Task ReadValidatedRequestAsync_AcceptsOnlyFirewallEnsureWithValidPorts()
    {
        string directory = CreateTemporaryDirectory();
        try
        {
            string path = Path.Combine(directory, "request.json");
            ElevatedFirewallRequest request = new ElevatedFirewallRequest { Operation = "firewall-ensure", Requirements = new FirewallRequirements { ServerExecutablePath = "C:\\ASA\\ArkAscendedServer.exe", UdpInboundPorts = [7777], ExposeRcon = false } };
            await File.WriteAllTextAsync(path, JsonSerializer.Serialize(request));
            OperationResult<ElevatedFirewallRequest> result = await WindowsFirewallService.ReadValidatedRequestAsync(path, CancellationToken.None);
            Assert.True(result.Succeeded);
        }
        finally
        {
            Directory.Delete(directory, true);
        }
    }

    [Fact]
    public async Task ReadValidatedRequestAsync_RejectsUnknownOperationAndInvalidPort()
    {
        string directory = CreateTemporaryDirectory();
        try
        {
            string path = Path.Combine(directory, "request.json");
            ElevatedFirewallRequest request = new ElevatedFirewallRequest { Operation = "arbitrary-command", Requirements = new FirewallRequirements { ServerExecutablePath = "C:\\ASA\\ArkAscendedServer.exe", UdpInboundPorts = [0], ExposeRcon = false } };
            await File.WriteAllTextAsync(path, JsonSerializer.Serialize(request));
            OperationResult<ElevatedFirewallRequest> result = await WindowsFirewallService.ReadValidatedRequestAsync(path, CancellationToken.None);
            Assert.False(result.Succeeded);
            Assert.Equal("FIREWALL_ENSURE_FAILED", result.ErrorCode);
        }
        finally
        {
            Directory.Delete(directory, true);
        }
    }

    private static string CreateTemporaryDirectory()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"asa-tests-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        return directory;
    }
}

public sealed class NetworkInfoServiceTests
{
    [Fact]
    public async Task GetSnapshotAsync_ExcludesLoopbackAndLinkLocalAndBuildsLanCommand()
    {
        FakeNetworkInterfaceProvider provider = new FakeNetworkInterfaceProvider([new NetworkInterfaceRecord
        {
            Name = "Ethernet",
            Description = "Ethernet adapter",
            InterfaceType = NetworkInterfaceType.Ethernet,
            UnicastAddresses = [IPAddress.Loopback, IPAddress.Parse("169.254.1.2"), IPAddress.Parse("192.168.1.20")]
        }]);
        NetworkSnapshot snapshot = await new NetworkInfoService(provider, new FakeLogger()).GetSnapshotAsync(7777, CancellationToken.None);
        Assert.Equal("192.168.1.20", snapshot.LanIpv4);
        Assert.Equal("open 192.168.1.20:7777", snapshot.LanConnectCommand);
        Assert.Single(snapshot.Addresses);
    }

    [Fact]
    public async Task GetSnapshotAsync_DetectsHamachiByNameOrDescription()
    {
        FakeNetworkInterfaceProvider provider = new FakeNetworkInterfaceProvider([new NetworkInterfaceRecord
        {
            Name = "Hamachi",
            Description = "Virtual network adapter",
            InterfaceType = NetworkInterfaceType.Ethernet,
            UnicastAddresses = [IPAddress.Parse("25.1.2.3")]
        }]);
        NetworkSnapshot snapshot = await new NetworkInfoService(provider, new FakeLogger()).GetSnapshotAsync(7777, CancellationToken.None);
        Assert.Equal("25.1.2.3", snapshot.HamachiIpv4);
        Assert.Equal("open 25.1.2.3:7777", snapshot.HamachiConnectCommand);
    }
}

public sealed class SavedBackupServiceTests
{
    [Fact]
    public async Task CreateSavedBackupAsync_CopiesTreeAndReturnsCounts()
    {
        string root = CreateTemporaryDirectory();
        string destinationRoot = CreateTemporaryDirectory();
        try
        {
            string source = Path.Combine(root, "ShooterGame", "Saved", "Config");
            Directory.CreateDirectory(source);
            await File.WriteAllTextAsync(Path.Combine(source, "server.txt"), "saved-data");
            SavedBackupService service = new SavedBackupService(destinationRoot, new FakeLogger());
            OperationResult<BackupInfo> result = await service.CreateSavedBackupAsync(root, CancellationToken.None);
            Assert.True(result.Succeeded);
            Assert.Equal(1, result.Value?.FileCount);
            Assert.Equal(10, result.Value?.TotalBytes);
            Assert.True(File.Exists(Path.Combine(result.Value?.Path ?? string.Empty, "ShooterGame", "Saved", "Config", "server.txt")));
            Assert.False(File.Exists(Path.Combine(result.Value?.Path ?? string.Empty, ".incomplete")));
        }
        finally
        {
            Directory.Delete(root, true);
            Directory.Delete(destinationRoot, true);
        }
    }

    [Fact]
    public async Task CreateSavedBackupAsync_ReturnsSourceNotFound()
    {
        string root = CreateTemporaryDirectory();
        string destinationRoot = CreateTemporaryDirectory();
        try
        {
            OperationResult<BackupInfo> result = await new SavedBackupService(destinationRoot, new FakeLogger()).CreateSavedBackupAsync(root, CancellationToken.None);
            Assert.False(result.Succeeded);
            Assert.Equal("BACKUP_SOURCE_NOT_FOUND", result.ErrorCode);
        }
        finally
        {
            Directory.Delete(root, true);
            Directory.Delete(destinationRoot, true);
        }
    }

    private static string CreateTemporaryDirectory()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"asa-tests-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        return directory;
    }
}

internal sealed class FakeNetworkInterfaceProvider : INetworkInterfaceProvider
{
    private readonly IReadOnlyList<NetworkInterfaceRecord> _records;

    /// <summary>固定のネットワークアダプター記録を使用してテスト用providerを作成します。</summary>
    internal FakeNetworkInterfaceProvider(IReadOnlyList<NetworkInterfaceRecord> records) { _records = records; }

    /// <inheritdoc />
    public IReadOnlyList<NetworkInterfaceRecord> GetActiveInterfaces() => _records;
}
