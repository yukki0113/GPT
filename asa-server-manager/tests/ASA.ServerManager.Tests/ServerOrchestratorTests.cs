using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Tests;

public sealed class ServerOrchestratorTests
{
    [Fact]
    public async Task StartAsync_UpdatesSavesStartsAndWaitsForRcon()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        fakes.Rcon.TestResult = RconConnectionResult.Success();
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StartAsync(null, CancellationToken.None);
        Assert.True(result.Succeeded);
        Assert.Equal(1, fakes.Steam.EnsureCalls);
        Assert.Equal(1, fakes.Steam.UpdateCalls);
        Assert.Equal(1, fakes.Saver.SaveCalls);
        Assert.Equal(1, fakes.Process.StartCalls);
    }

    [Fact]
    public async Task StartAsync_EarlyProcessExitReturnsError()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        fakes.Process.ExitResults.Enqueue(true);
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StartAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal("SERVER_EXITED_EARLY", result.ErrorCode);
    }

    [Fact]
    public async Task StartAsync_SteamUpdateFailureDoesNotStartProcess()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        fakes.Steam.UpdateResult = OperationResult.Failure("failed", errorCode: "STEAMCMD_UPDATE_FAILED");
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StartAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal(0, fakes.Process.StartCalls);
    }

    [Fact]
    public async Task StartAsync_FirewallNeedsUpdateRequestsElevationBeforeUpdate()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        fakes.Firewall.Snapshots.Enqueue(new FirewallSnapshot { Readiness = FirewallReadiness.NeedsUpdate });
        fakes.Firewall.Snapshots.Enqueue(new FirewallSnapshot { Readiness = FirewallReadiness.Ready });
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StartAsync(null, CancellationToken.None);
        Assert.True(result.Succeeded);
        Assert.Equal(1, fakes.Elevation.EnsureCalls);
        Assert.Equal(1, fakes.Steam.UpdateCalls);
    }

    [Fact]
    public async Task StartAsync_FirewallEnsureFailureDoesNotUpdateOrStart()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = false;
        fakes.Firewall.Snapshot = new FirewallSnapshot { Readiness = FirewallReadiness.NeedsUpdate };
        fakes.Elevation.EnsureResult = OperationResult.Failure("cancelled", errorCode: "FIREWALL_ELEVATION_CANCELLED");
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StartAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal("FIREWALL_ELEVATION_CANCELLED", result.ErrorCode);
        Assert.Equal(0, fakes.Steam.UpdateCalls);
        Assert.Equal(0, fakes.Process.StartCalls);
    }

    [Fact]
    public async Task StopAsync_SaveWorldFailureDoesNotIssueDoExit()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Failure("SAVEWORLD_FAILED", "failed"));
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StopAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal("SAVEWORLD_FAILED", result.ErrorCode);
        Assert.DoesNotContain("DoExit", fakes.Rcon.Commands);
    }

    [Fact]
    public async Task StopAsync_WaitsForExitWithoutForceKill()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Process.ExitResults.Enqueue(true);
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StopAsync(null, CancellationToken.None);
        Assert.True(result.Succeeded);
        Assert.Equal(new[] { "SaveWorld", "DoExit" }, fakes.Rcon.Commands);
        Assert.Equal(0, fakes.Process.ForceKillCalls);
        Assert.Equal(0, fakes.Elevation.EnsureCalls);
    }

    [Fact]
    public async Task StopAsync_ExitTimeoutReturnsErrorWithoutForceKill()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Process.ExitResults.Enqueue(false);
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.StopAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal("STOP_TIMEOUT", result.ErrorCode);
        Assert.Equal(0, fakes.Process.ForceKillCalls);
    }

    [Fact]
    public async Task RestartAsync_StopsThenUpdatesAndStarts()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Process.ExitResults.Enqueue(true);
        fakes.Process.ExitResults.Enqueue(false);
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.RestartAsync(null, CancellationToken.None);
        Assert.True(result.Succeeded);
        Assert.Equal(1, fakes.Steam.UpdateCalls);
        Assert.Equal(1, fakes.Process.StartCalls);
    }

    [Fact]
    public async Task RestartAsync_SaveWorldFailureDoesNotStartAgain()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Failure("SAVEWORLD_FAILED", "failed"));
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.RestartAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal(0, fakes.Process.StartCalls);
    }

    [Fact]
    public async Task RestartAsync_FirewallFailureAfterSafeStopDoesNotUpdateOrStart()
    {
        RuntimeFakes fakes = new RuntimeFakes();
        fakes.Process.IsRunning = true;
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Rcon.CommandResults.Enqueue(RconConnectionResult.Success());
        fakes.Process.ExitResults.Enqueue(true);
        fakes.Firewall.Snapshots.Enqueue(new FirewallSnapshot { Readiness = FirewallReadiness.Ready });
        fakes.Firewall.Snapshots.Enqueue(new FirewallSnapshot { Readiness = FirewallReadiness.NeedsUpdate });
        fakes.Elevation.EnsureResult = OperationResult.Failure("cancelled", errorCode: "FIREWALL_ELEVATION_CANCELLED");
        await using ServerOrchestrator orchestrator = fakes.CreateOrchestrator();
        OperationResult result = await orchestrator.RestartAsync(null, CancellationToken.None);
        Assert.False(result.Succeeded);
        Assert.Equal(new[] { "SaveWorld", "DoExit" }, fakes.Rcon.Commands);
        Assert.Equal(0, fakes.Steam.UpdateCalls);
        Assert.Equal(0, fakes.Process.StartCalls);
    }
}

internal sealed class RuntimeFakes
{
    internal FakeSettingsRepository Settings { get; } = new();
    internal FakeSecretRepository Secrets { get; } = new();
    internal FakeSteamService Steam { get; } = new();
    internal FakeProcessService Process { get; } = new();
    internal FakeRconClient Rcon { get; } = new();
    internal FakeIniSaver Saver { get; } = new();
    internal FakeFirewallService Firewall { get; } = new();
    internal FakeElevationLauncher Elevation { get; } = new();
    internal FakeNetworkInfoService Network { get; } = new();

    internal ServerOrchestrator CreateOrchestrator()
    {
        return new ServerOrchestrator(Settings, Secrets, Steam, Process, Rcon, Saver, new ServerArgumentBuilder(), new ServerStateResolver(), new FakeDelay(), new FakeLogger(), Firewall, Elevation, Network, new FirewallRequirementsBuilder());
    }
}

internal sealed class FakeSettingsRepository : IServerSettingsRepository
{
    private readonly ServerSettings _settings = new() { DedicatedServerPath = "C:\\ASA", SteamCmdPath = "C:\\SteamCMD", MapLevelName = "TheIsland_WP", ServerName = "ASA", MaxPlayers = 10, RconEnabled = true };
    public Task<OperationResult<ServerSettings>> LoadAsync(CancellationToken cancellationToken) => Task.FromResult(OperationResult<ServerSettings>.Success(_settings));
    public Task<OperationResult> SaveAsync(ServerSettings settings, CancellationToken cancellationToken) => Task.FromResult(OperationResult.Success());
}

internal sealed class FakeSecretRepository : ISecretRepository
{
    public Task<OperationResult<ServerSecrets>> LoadAsync(CancellationToken cancellationToken) => Task.FromResult(OperationResult<ServerSecrets>.Success(new ServerSecrets { AdminPassword = "admin", RconPassword = "rcon" }));
    public Task<OperationResult> SaveAsync(ServerSecrets secrets, CancellationToken cancellationToken) => Task.FromResult(OperationResult.Success());
}

internal sealed class FakeSteamService : ISteamCmdService
{
    internal int EnsureCalls { get; private set; }
    internal int UpdateCalls { get; private set; }
    internal OperationResult EnsureResult { get; set; } = OperationResult.Success();
    internal OperationResult UpdateResult { get; set; } = OperationResult.Success();
    public Task<OperationResult> EnsureInstalledAsync(string steamCmdPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken) { EnsureCalls++; return Task.FromResult(EnsureResult); }
    public Task<OperationResult> UpdateAsaServerAsync(string steamCmdPath, string dedicatedServerPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken) { UpdateCalls++; return Task.FromResult(UpdateResult); }
}

internal sealed class FakeProcessService : IAsaProcessService
{
    internal bool IsRunning { get; set; }
    internal int StartCalls { get; private set; }
    internal int ForceKillCalls { get; private set; }
    internal Queue<bool> ExitResults { get; } = new();
    public Task<ProcessSnapshot> FindServerProcessAsync(string dedicatedServerPath, CancellationToken cancellationToken)
    {
        int? processId = null;
        if (IsRunning)
        {
            processId = 50;
        }
        return Task.FromResult(new ProcessSnapshot { IsRunning = IsRunning, ProcessId = processId });
    }
    public Task<OperationResult<ProcessSnapshot>> StartAsync(AsaStartRequest request, CancellationToken cancellationToken) { StartCalls++; return Task.FromResult(OperationResult<ProcessSnapshot>.Success(new ProcessSnapshot { IsRunning = true, ProcessId = 60 })); }
    public Task<bool> WaitForExitAsync(int processId, TimeSpan timeout, CancellationToken cancellationToken) { bool value = ExitResults.Count > 0 && ExitResults.Dequeue(); return Task.FromResult(value); }
}

internal sealed class FakeRconClient : IRconClient
{
    internal RconConnectionResult TestResult { get; set; } = RconConnectionResult.Success();
    internal Queue<RconConnectionResult> CommandResults { get; } = new();
    internal List<string> Commands { get; } = [];
    public Task<RconConnectionResult> TestConnectionAsync(RconEndpoint endpoint, CancellationToken cancellationToken) => Task.FromResult(TestResult);
    public Task<RconConnectionResult> ExecuteAsync(RconEndpoint endpoint, string command, CancellationToken cancellationToken)
    {
        Commands.Add(command);
        RconConnectionResult value = RconConnectionResult.Success();
        if (CommandResults.Count > 0)
        {
            value = CommandResults.Dequeue();
        }
        return Task.FromResult(value);
    }
}

internal sealed class FakeIniSaver : IEnabledIniSettingsSaver
{
    internal int SaveCalls { get; private set; }
    public Task<OperationResult> SaveEnabledSettingsAsync(ServerSettings settings, CancellationToken cancellationToken) { SaveCalls++; return Task.FromResult(OperationResult.Success()); }
}

internal sealed class FakeFirewallService : IFirewallService
{
    internal int InspectCalls { get; private set; }
    internal FirewallSnapshot Snapshot { get; set; } = new FirewallSnapshot { Readiness = FirewallReadiness.Ready };
    internal Queue<FirewallSnapshot> Snapshots { get; } = new();
    public Task<FirewallSnapshot> InspectAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        InspectCalls++;
        if (Snapshots.Count > 0)
        {
            return Task.FromResult(Snapshots.Dequeue());
        }
        return Task.FromResult(Snapshot);
    }
    public Task<OperationResult> EnsureAsync(FirewallRequirements requirements, CancellationToken cancellationToken) => Task.FromResult(OperationResult.Success());
}

internal sealed class FakeElevationLauncher : IFirewallElevationLauncher
{
    internal int EnsureCalls { get; private set; }
    internal OperationResult EnsureResult { get; set; } = OperationResult.Success();
    public Task<OperationResult> EnsureAsync(FirewallRequirements requirements, CancellationToken cancellationToken) { EnsureCalls++; return Task.FromResult(EnsureResult); }
}

internal sealed class FakeNetworkInfoService : INetworkInfoService
{
    public Task<NetworkSnapshot> GetSnapshotAsync(int gamePort, CancellationToken cancellationToken) => Task.FromResult(new NetworkSnapshot());
}

internal sealed class FakeDelay : IOperationDelay
{
    public Task DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => Task.CompletedTask;
}

internal sealed class FakeLogger : IAppLogger
{
    public void Error(Exception exception, string message) { }
    public void Info(string message) { }
    public void Warn(string message) { }
}
