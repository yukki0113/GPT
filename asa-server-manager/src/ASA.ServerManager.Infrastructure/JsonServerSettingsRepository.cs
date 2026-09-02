using System.Text;
using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>秘密情報を含めないサーバー設定をJSONで原子的に保存します。</summary>
public sealed class JsonServerSettingsRepository(string path) : IServerSettingsRepository
{
    private readonly string _path = path;
    private static readonly JsonSerializerOptions Options = new() { WriteIndented = true, PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    /// <inheritdoc />
    public async Task<OperationResult<ServerSettings>> LoadAsync(CancellationToken cancellationToken)
    {
        try
        {
            if (!File.Exists(_path)) { return OperationResult<ServerSettings>.Success(new ServerSettings()); }
            await using FileStream stream = File.OpenRead(_path);
            ServerSettings? settings = await JsonSerializer.DeserializeAsync<ServerSettings>(stream, Options, cancellationToken);
            if (settings is null) { return OperationResult<ServerSettings>.Failure("server-settings.jsonが空です。"); }
            return OperationResult<ServerSettings>.Success(settings);
        }
        catch (Exception exception) { return OperationResult<ServerSettings>.Failure($"設定の読込に失敗しました: {exception.Message}"); }
    }
    /// <inheritdoc />
    public async Task<OperationResult> SaveAsync(ServerSettings settings, CancellationToken cancellationToken)
    {
        try
        {
            string directory = Path.GetDirectoryName(_path) ?? throw new InvalidOperationException("設定ファイルの親ディレクトリが不明です。");
            Directory.CreateDirectory(directory);
            string tempPath = Path.Combine(directory, $".{Path.GetFileName(_path)}.{Guid.NewGuid():N}.tmp");
            try { await File.WriteAllTextAsync(tempPath, JsonSerializer.Serialize(settings, Options), new UTF8Encoding(false), cancellationToken); File.Move(tempPath, _path, true); return OperationResult.Success(); }
            finally { if (File.Exists(tempPath)) { File.Delete(tempPath); } }
        }
        catch (Exception exception) { return OperationResult.Failure($"設定の保存に失敗しました: {exception.Message}"); }
    }
}
