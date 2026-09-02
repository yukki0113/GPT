using ASA.ServerManager.Domain;
using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class RepositoryTests
{
    [Fact]
    public async Task ServerSettings_SaveLoadRoundTripIsAtomicAndDoesNotPersistPasswords()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "server-settings.json");
        JsonServerSettingsRepository repository = new JsonServerSettingsRepository(path);
        ServerSettings settings = new ServerSettings { DedicatedServerPath = "C:\\ASA", MapId = "TheIsland_WP", GameSettings = [new GameSettingState { DefinitionId = "id", Enabled = true, EditedValue = "value" }] };

        OperationResult save = await repository.SaveAsync(settings, CancellationToken.None);
        OperationResult<ServerSettings> load = await repository.LoadAsync(CancellationToken.None);

        Assert.True(save.Succeeded, save.ErrorMessage);
        Assert.True(load.Succeeded, load.ErrorMessage);
        Assert.Equal("TheIsland_WP", load.Value?.MapId);
        string json = await File.ReadAllTextAsync(path);
        Assert.DoesNotContain("Password", json, StringComparison.OrdinalIgnoreCase);
        Assert.Empty(Directory.GetFiles(directory.Path, "*.tmp"));
    }

    [Fact]
    public async Task ServerSettings_LoadAsyncReportsCorruptJson()
    {
        using TestDirectory directory = new TestDirectory();
        string path = Path.Combine(directory.Path, "server-settings.json");
        await File.WriteAllTextAsync(path, "{ bad json");

        OperationResult<ServerSettings> result = await new JsonServerSettingsRepository(path).LoadAsync(CancellationToken.None);

        Assert.False(result.Succeeded);
        Assert.NotNull(result.ErrorMessage);
    }
}

internal sealed class TestDirectory : IDisposable
{
    public TestDirectory()
    {
        Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "asa-server-manager-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path);
    }
    public string Path { get; }
    public void Dispose() { if (Directory.Exists(Path)) { Directory.Delete(Path, true); } }
}
