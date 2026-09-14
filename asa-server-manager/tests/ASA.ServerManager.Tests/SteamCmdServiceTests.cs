using System.Diagnostics;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class SteamCmdServiceTests
{
    private const string SuccessMarker = "Success! App '2430930' fully installed.";

    [Fact]
    public async Task ExitZeroAndServerExecutableExists_Succeeds()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stdout", "up to date")]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.True(result.Succeeded);
    }

    [Fact]
    public async Task ExitZeroAndServerExecutableMissing_Fails()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: false);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stdout", SuccessMarker)]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal("STEAMCMD_UPDATE_FAILED", result.ErrorCode);
    }

    [Fact]
    public async Task NonZeroWithSuccessMarkerAndServerExecutable_SucceedsWithWarning()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(7, [new FakeSteamCmdLine("stdout", SuccessMarker)]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.True(result.Succeeded);
        Assert.NotEmpty(result.Warnings);
        Assert.Equal(1, fixture.Runner.RunCount);
    }

    [Theory]
    [InlineData("ERROR! failed")]
    [InlineData("Failed to install app '2430930'")]
    [InlineData("Disk write failure")]
    [InlineData("No subscription")]
    [InlineData("Timeout")]
    [InlineData("Access is denied")]
    public async Task FailureMarker_OverridesExitCodeAndExecutable(string marker)
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stderr", marker)]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.False(result.Succeeded);
    }

    [Fact]
    public async Task SuccessAndFailureMarkersTogether_FailureWins()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stdout", SuccessMarker), new FakeSteamCmdLine("stderr", "ERROR! disk") ]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.False(result.Succeeded);
    }

    [Fact]
    public async Task BootstrapFailure_RetriesOnlyOnceAndSecondSuccessWins()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(1, [new FakeSteamCmdLine("stdout", "Checking for available update") ]));
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stdout", SuccessMarker)]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.True(result.Succeeded);
        Assert.Equal(2, fixture.Runner.RunCount);
        Assert.Contains(fixture.Logger.Warnings, message => message.Contains("retrying once", StringComparison.Ordinal));
    }

    [Fact]
    public async Task BootstrapRetryFailure_DoesNotRunThirdAttempt()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: false);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(1, [new FakeSteamCmdLine("stdout", "Updating Steam") ]));
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(1, [new FakeSteamCmdLine("stdout", "Updating Steam") ]));

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Equal(2, fixture.Runner.RunCount);
    }

    [Fact]
    public async Task NormalUpdateOmitsValidateAndRepairIncludesValidate()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, []));
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, []));

        await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);
        await fixture.Service.RepairAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        Assert.DoesNotContain("validate", fixture.Runner.Arguments[0]);
        Assert.Contains("validate", fixture.Runner.Arguments[1]);
        Assert.Equal(new[] { "+force_install_dir", fixture.ServerRoot, "+login", "anonymous", "+app_update", "2430930", "+quit" }, fixture.Runner.Arguments[0]);
    }

    [Fact]
    public void ProgressParser_ParsesDecimalAndIgnoresMalformedInput()
    {
        Assert.Equal(59.33d, SteamCmdService.TryParseProgress(" Update state (0x61) downloading, progress: 59.33"));
        Assert.Null(SteamCmdService.TryParseProgress("progress: unknown"));
        Assert.Null(SteamCmdService.TryParseProgress(string.Empty));
    }

    [Fact]
    public async Task StdoutStderrProgressHeartbeatAndBoundedTail_AreCaptured()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: false);
        List<FakeSteamCmdLine> lines = Enumerable.Range(1, 125).Select(index => new FakeSteamCmdLine("stdout", "line-" + index)).ToList();
        lines.Add(new FakeSteamCmdLine("stdout", "progress: 59.33"));
        lines.Add(new FakeSteamCmdLine("stderr", "ERROR! final failure"));
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(1, lines, SendHeartbeat: true));
        RecordingProgress progress = new RecordingProgress();

        OperationResult result = await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, progress, CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.Contains("[stderr] ERROR! final failure", result.TechnicalMessage);
        Assert.DoesNotContain("line-1" + Environment.NewLine, result.TechnicalMessage);
        Assert.True((result.TechnicalMessage ?? string.Empty).Split(Environment.NewLine).Length <= 100);
        Assert.Contains(progress.Values, value => value.Percent == 59);
        Assert.Contains(progress.Values, value => value.UserMessage.Contains("最終応答", StringComparison.Ordinal));
    }

    [Fact]
    public async Task Completion_RecordsDiagnosticsAndStructuredLogFields()
    {
        using SteamCmdFixture fixture = new SteamCmdFixture(serverExecutableExists: true);
        fixture.Runner.Results.Enqueue(new FakeSteamCmdResult(0, [new FakeSteamCmdLine("stdout", SuccessMarker)]));

        await fixture.Service.UpdateAsaServerAsync(fixture.SteamRoot, fixture.ServerRoot, null, CancellationToken.None);

        SteamCmdDiagnostics diagnostics = Assert.IsType<SteamCmdDiagnostics>(fixture.StatusStore.GetSteamCmdDiagnostics());
        Assert.Equal(0, diagnostics.ExitCode);
        Assert.Contains("SuccessMarker=True", diagnostics.Summary);
        Assert.Contains(fixture.Logger.Information, message => message == "AppId=2430930");
        Assert.Contains(fixture.Logger.Information, message => message == "Validate=false");
        Assert.Contains(fixture.Logger.Information, message => message.Contains("ServerExecutableExists=True", StringComparison.Ordinal));
    }
}

public sealed class ApplicationStatusStoreTests
{
    [Fact]
    public void ClearLastError_RemovesOldFailureAndSuccessDoesNotRestoreIt()
    {
        ApplicationStatusStore store = new ApplicationStatusStore();
        store.Record(OperationResult.Failure("old", errorCode: "OLD_ERROR"));

        store.ClearLastError();
        store.Record(OperationResult.Success());

        Assert.Null(store.GetLastErrorCode());
    }

    [Fact]
    public void FailureAfterClear_RecordsNewError()
    {
        ApplicationStatusStore store = new ApplicationStatusStore();
        store.Record(OperationResult.Failure("old", errorCode: "OLD_ERROR"));
        store.ClearLastError();

        store.Record(OperationResult.Failure("new", errorCode: "NEW_ERROR"));

        Assert.Equal("NEW_ERROR", store.GetLastErrorCode());
    }
}

internal sealed class SteamCmdFixture : IDisposable
{
    private readonly TestDirectory _directory = new TestDirectory();

    internal SteamCmdFixture(bool serverExecutableExists)
    {
        SteamRoot = Path.Combine(_directory.Path, "steamcmd");
        ServerRoot = Path.Combine(_directory.Path, "server");
        Directory.CreateDirectory(SteamRoot);
        File.WriteAllText(Path.Combine(SteamRoot, "steamcmd.exe"), "test");
        if (serverExecutableExists)
        {
            string serverExecutable = Path.Combine(ServerRoot, "ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(serverExecutable) ?? ServerRoot);
            File.WriteAllText(serverExecutable, "test");
        }
        Service = new SteamCmdService(new HttpClient(), Logger, Runner, StatusStore);
    }

    internal string SteamRoot { get; }
    internal string ServerRoot { get; }
    internal FakeSteamCmdRunner Runner { get; } = new FakeSteamCmdRunner();
    internal RecordingLogger Logger { get; } = new RecordingLogger();
    internal ApplicationStatusStore StatusStore { get; } = new ApplicationStatusStore();
    internal SteamCmdService Service { get; }

    public void Dispose()
    {
        _directory.Dispose();
    }
}

internal sealed class FakeSteamCmdRunner : ISteamCmdProcessRunner
{
    internal Queue<FakeSteamCmdResult> Results { get; } = new Queue<FakeSteamCmdResult>();
    internal List<IReadOnlyList<string>> Arguments { get; } = [];
    internal int RunCount { get; private set; }

    public Task<SteamCmdProcessRunResult> RunAsync(ProcessStartInfo startInfo, Action<string, string> captureLine, Action heartbeat, CancellationToken cancellationToken)
    {
        RunCount++;
        Arguments.Add(startInfo.ArgumentList.ToArray());
        FakeSteamCmdResult result = Results.Dequeue();
        foreach (FakeSteamCmdLine line in result.Lines)
        {
            captureLine(line.Source, line.Text);
        }
        if (result.SendHeartbeat)
        {
            heartbeat();
        }
        return Task.FromResult(new SteamCmdProcessRunResult(result.ExitCode, TimeSpan.FromSeconds(2)));
    }
}

internal sealed record FakeSteamCmdResult(int ExitCode, IReadOnlyList<FakeSteamCmdLine> Lines, bool SendHeartbeat = false);
internal sealed record FakeSteamCmdLine(string Source, string Text);

internal sealed class RecordingProgress : IProgress<OperationProgress>
{
    internal List<OperationProgress> Values { get; } = [];
    public void Report(OperationProgress value) { Values.Add(value); }
}

internal sealed class RecordingLogger : IAppLogger
{
    internal List<string> Information { get; } = [];
    internal List<string> Warnings { get; } = [];
    public void Info(string message) { Information.Add(message); }
    public void Warn(string message) { Warnings.Add(message); }
    public void Error(Exception exception, string message) { Warnings.Add(message + ": " + exception.Message); }
}
