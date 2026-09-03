using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>外部JSONから選択可能なASA MAP定義を読み込みます。</summary>
public sealed class JsonMapDefinitionRepository : IMapDefinitionRepository
{
    private readonly string _path;
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };

    /// <summary>MAP定義ファイルのパスを指定します。</summary>
    public JsonMapDefinitionRepository(string path)
    {
        _path = path;
    }

    /// <inheritdoc />
    public async Task<OperationResult<IReadOnlyList<MapDefinition>>> LoadAsync(CancellationToken cancellationToken)
    {
        try
        {
            if (!File.Exists(_path))
            {
                return OperationResult<IReadOnlyList<MapDefinition>>.Failure("MAP定義が見つかりません。", errorCode: "MAP_CATALOG_MISSING");
            }
            await using FileStream stream = File.OpenRead(_path);
            List<MapDefinition>? maps = await JsonSerializer.DeserializeAsync<List<MapDefinition>>(stream, Options, cancellationToken);
            if (maps is null || maps.Count == 0)
            {
                return OperationResult<IReadOnlyList<MapDefinition>>.Failure("MAP定義が空です。", errorCode: "MAP_CATALOG_INVALID");
            }
            if (maps.Any(map => string.IsNullOrWhiteSpace(map.Id) || string.IsNullOrWhiteSpace(map.LevelName) || string.IsNullOrWhiteSpace(map.DisplayNameJa)))
            {
                return OperationResult<IReadOnlyList<MapDefinition>>.Failure("MAP定義に必須項目が不足しています。", errorCode: "MAP_CATALOG_INVALID");
            }
            if (maps.Select(map => map.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != maps.Count || maps.Select(map => map.LevelName).Distinct(StringComparer.OrdinalIgnoreCase).Count() != maps.Count)
            {
                return OperationResult<IReadOnlyList<MapDefinition>>.Failure("MAP定義に重複があります。", errorCode: "MAP_CATALOG_INVALID");
            }
            return OperationResult<IReadOnlyList<MapDefinition>>.Success(maps);
        }
        catch (Exception exception)
        {
            return OperationResult<IReadOnlyList<MapDefinition>>.Failure("MAP定義の読み込みに失敗しました。", errorCode: "MAP_CATALOG_INVALID", technicalMessage: exception.Message);
        }
    }
}

/// <summary>最新の日次ログを件数制限して読み込みます。</summary>
public sealed class FileLogService : ILogFileService
{
    private readonly string _directory;

    /// <summary>ログ保存フォルダーを指定します。</summary>
    public FileLogService(string directory)
    {
        _directory = directory;
    }

    /// <inheritdoc />
    public string GetLogDirectory()
    {
        return _directory;
    }

    /// <inheritdoc />
    public async Task<OperationResult<LogTailSnapshot>> ReadTailAsync(int maximumLines, CancellationToken cancellationToken)
    {
        if (maximumLines < 1 || maximumLines > 10000)
        {
            return OperationResult<LogTailSnapshot>.Failure("ログ表示行数が不正です。", errorCode: "LOG_TAIL_INVALID");
        }
        try
        {
            string? path = FindLatestLogPath();
            if (path is null)
            {
                return OperationResult<LogTailSnapshot>.Success(new LogTailSnapshot());
            }
            Queue<string> lines = new Queue<string>(maximumLines);
            using FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using StreamReader reader = new StreamReader(stream);
            while (!reader.EndOfStream)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string? line = await reader.ReadLineAsync(cancellationToken);
                if (line is null)
                {
                    continue;
                }
                if (lines.Count == maximumLines)
                {
                    lines.Dequeue();
                }
                lines.Enqueue(line);
            }
            return OperationResult<LogTailSnapshot>.Success(new LogTailSnapshot { Path = path, Lines = lines.ToArray() });
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception exception)
        {
            return OperationResult<LogTailSnapshot>.Failure("ログの読み込みに失敗しました。", errorCode: "LOG_READ_FAILED", technicalMessage: exception.Message);
        }
    }

    private string? FindLatestLogPath()
    {
        if (!Directory.Exists(_directory))
        {
            return null;
        }
        return Directory.EnumerateFiles(_directory, "*.log", SearchOption.TopDirectoryOnly)
            .OrderByDescending(File.GetLastWriteTimeUtc)
            .FirstOrDefault();
    }
}
