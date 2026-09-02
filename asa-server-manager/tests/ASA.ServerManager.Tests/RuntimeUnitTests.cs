using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Tests;

public sealed class ServerArgumentBuilderTests
{
    [Fact]
    public void Build_IncludesMapAndSessionName()
    {
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(CreateSettings(), CreateSecrets());
        Assert.True(result.Succeeded);
        Assert.Contains("TheIsland_WP?SessionName=ASA-Test", result.Value?.Arguments);
    }

    [Fact]
    public void Build_IncludesConfiguredPortsAndMaxPlayers()
    {
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(CreateSettings(), CreateSecrets());
        Assert.Contains("?Port=7777", result.Value?.Arguments);
        Assert.Contains("?RCONPort=27020", result.Value?.Arguments);
        Assert.Contains("?MaxPlayers=20", result.Value?.Arguments);
    }

    [Fact]
    public void Build_IncludesEnabledModsInOrder()
    {
        ServerSettings settings = CreateSettings();
        settings.Mods.Add(new ModDefinition { ProjectId = "200", Order = 2 });
        settings.Mods.Add(new ModDefinition { ProjectId = "100", Order = 1 });
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(settings, CreateSecrets());
        Assert.Contains("-mods=100,200", result.Value?.Arguments);
    }

    [Fact]
    public void Build_PutsCustomMapModFirstAndDeduplicates()
    {
        ServerSettings settings = CreateSettings();
        settings.CustomMapModProjectId = "300";
        settings.Mods.Add(new ModDefinition { ProjectId = "300", Order = 1 });
        settings.Mods.Add(new ModDefinition { ProjectId = "200", Order = 2 });
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(settings, CreateSecrets());
        Assert.Contains("-mods=300,200", result.Value?.Arguments);
    }

    [Fact]
    public void Build_ExcludesDisabledMods()
    {
        ServerSettings settings = CreateSettings();
        settings.Mods.Add(new ModDefinition { ProjectId = "100", Enabled = false, Order = 1 });
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(settings, CreateSecrets());
        Assert.DoesNotContain("-mods=100", result.Value?.Arguments);
    }

    [Fact]
    public void Build_RejectsExternalModsArgument()
    {
        ServerSettings settings = CreateSettings();
        settings.ExtraArguments = "-mods=999";
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(settings, CreateSecrets());
        Assert.False(result.Succeeded);
        Assert.Equal("CFG_INVALID_ARGUMENT", result.ErrorCode);
    }

    [Fact]
    public void Build_MasksEverySecretInLogArguments()
    {
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(CreateSettings(), CreateSecrets());
        Assert.DoesNotContain("join-secret", result.Value?.MaskedArguments);
        Assert.DoesNotContain("admin-secret", result.Value?.MaskedArguments);
        Assert.DoesNotContain("rcon-secret", result.Value?.MaskedArguments);
    }

    [Fact]
    public void Build_UsesActualSecretsOnlyInRuntimeArguments()
    {
        ServerArgumentBuilder builder = new ServerArgumentBuilder();
        OperationResult<ServerArgumentBuildResult> result = builder.Build(CreateSettings(), CreateSecrets());
        Assert.Contains("admin-secret", result.Value?.Arguments);
        Assert.Contains("rcon-secret", result.Value?.Arguments);
    }

    [Fact]
    public void Build_RejectsMissingMapLevel()
    {
        ServerSettings settings = CreateSettings();
        settings.MapLevelName = string.Empty;
        OperationResult<ServerArgumentBuildResult> result = new ServerArgumentBuilder().Build(settings, CreateSecrets());
        Assert.False(result.Succeeded);
        Assert.Equal("CFG_REQUIRED_MISSING", result.ErrorCode);
    }

    private static ServerSettings CreateSettings()
    {
        return new ServerSettings { DedicatedServerPath = "C:\\ASA", SteamCmdPath = "C:\\SteamCMD", MapLevelName = "TheIsland_WP", ServerName = "ASA-Test", MaxPlayers = 20, RconEnabled = true };
    }

    private static ServerSecrets CreateSecrets()
    {
        return new ServerSecrets { ServerPassword = "join-secret", AdminPassword = "admin-secret", RconPassword = "rcon-secret" };
    }
}

public sealed class ServerStateResolverTests
{
    [Fact]
    public void Resolve_ReturnsUnconfiguredWhenRequiredConfigurationIsMissing()
    {
        ServerSnapshot snapshot = new ServerStateResolver().Resolve(false, new ProcessSnapshot(), null);
        Assert.Equal(ServerState.Unconfigured, snapshot.State);
    }

    [Fact]
    public void Resolve_ReturnsStoppedWhenProcessIsMissing()
    {
        ServerSnapshot snapshot = new ServerStateResolver().Resolve(true, new ProcessSnapshot(), null);
        Assert.Equal(ServerState.Stopped, snapshot.State);
    }

    [Fact]
    public void Resolve_ReturnsWaitingWhenProcessExistsWithoutRcon()
    {
        ServerSnapshot snapshot = new ServerStateResolver().Resolve(true, new ProcessSnapshot { IsRunning = true, ProcessId = 10 }, RconConnectionResult.Failure("RCON_NOT_READY", "not ready"));
        Assert.Equal(ServerState.WaitingForRcon, snapshot.State);
    }

    [Fact]
    public void Resolve_ReturnsRunningOnlyWhenProcessAndRconAreReady()
    {
        ServerSnapshot snapshot = new ServerStateResolver().Resolve(true, new ProcessSnapshot { IsRunning = true, ProcessId = 10 }, RconConnectionResult.Success());
        Assert.Equal(ServerState.Running, snapshot.State);
    }
}
