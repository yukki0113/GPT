using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>ASAのShooterGame/Saved全体を手動で安全に複製します。</summary>
public sealed class SavedBackupService : IBackupService
{
    private readonly string _backupRoot;
    private readonly TimeProvider _timeProvider;
    private readonly IAppLogger _logger;

    /// <summary>既定の時刻供給元でバックアップサービスを作成します。</summary>
    public SavedBackupService(string backupRoot, IAppLogger logger) : this(backupRoot, TimeProvider.System, logger)
    {
    }

    /// <summary>テスト可能な時刻供給元でバックアップサービスを作成します。</summary>
    public SavedBackupService(string backupRoot, TimeProvider timeProvider, IAppLogger logger)
    {
        _backupRoot = backupRoot;
        _timeProvider = timeProvider;
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task<OperationResult<BackupInfo>> CreateSavedBackupAsync(string serverRoot, CancellationToken cancellationToken)
    {
        string sourcePath = Path.Combine(serverRoot, "ShooterGame", "Saved");
        if (!Directory.Exists(sourcePath))
        {
            return OperationResult<BackupInfo>.Failure("Savedフォルダが見つかりません。", errorCode: "BACKUP_SOURCE_NOT_FOUND");
        }
        string destinationPath = CreateDestinationPath();
        if (IsPathInside(destinationPath, sourcePath))
        {
            return OperationResult<BackupInfo>.Failure("バックアップ先をSaved配下には作成できません。", errorCode: "BACKUP_CREATE_FAILED");
        }
        string markerPath = Path.Combine(destinationPath, ".incomplete");
        try
        {
            Directory.CreateDirectory(destinationPath);
            await File.WriteAllTextAsync(markerPath, "Backup is incomplete.", cancellationToken);
            _logger.Info("Saved backup started.");
            BackupCounters counters = new BackupCounters();
            await CopyDirectoryAsync(sourcePath, Path.Combine(destinationPath, "ShooterGame", "Saved"), counters, cancellationToken);
            File.Delete(markerPath);
            DateTimeOffset completedAt = _timeProvider.GetUtcNow();
            BackupInfo result = new BackupInfo { Path = destinationPath, CreatedAt = completedAt, FileCount = counters.FileCount, TotalBytes = counters.TotalBytes };
            _logger.Info($"Saved backup completed: files={result.FileCount}, bytes={result.TotalBytes}.");
            return OperationResult<BackupInfo>.Success(result);
        }
        catch (OperationCanceledException)
        {
            _logger.Warn("Saved backup was cancelled; incomplete marker was retained.");
            return OperationResult<BackupInfo>.Failure("Savedバックアップを取り消しました。", errorCode: "BACKUP_CANCELLED");
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Saved backup failed.");
            return OperationResult<BackupInfo>.Failure("Savedバックアップに失敗しました。", errorCode: "BACKUP_CREATE_FAILED", technicalMessage: exception.Message);
        }
    }

    private string CreateDestinationPath()
    {
        string timestamp = _timeProvider.GetLocalNow().ToString("yyyyMMdd_HHmmss");
        string candidate = Path.Combine(_backupRoot, "saved", timestamp);
        int suffix = 1;
        while (Directory.Exists(candidate))
        {
            candidate = Path.Combine(_backupRoot, "saved", $"{timestamp}_{suffix:D2}");
            suffix++;
        }
        return candidate;
    }

    private static async Task CopyDirectoryAsync(string sourceDirectory, string destinationDirectory, BackupCounters counters, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        DirectoryInfo sourceInfo = new DirectoryInfo(sourceDirectory);
        if (sourceInfo.Attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            return;
        }
        Directory.CreateDirectory(destinationDirectory);
        foreach (FileInfo file in sourceInfo.EnumerateFiles())
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (file.Attributes.HasFlag(FileAttributes.ReparsePoint))
            {
                continue;
            }
            string destinationFile = Path.Combine(destinationDirectory, file.Name);
            await using FileStream source = file.OpenRead();
            await using FileStream destination = File.Create(destinationFile);
            await source.CopyToAsync(destination, cancellationToken);
            counters.FileCount++;
            counters.TotalBytes += file.Length;
        }
        foreach (DirectoryInfo directory in sourceInfo.EnumerateDirectories())
        {
            await CopyDirectoryAsync(directory.FullName, Path.Combine(destinationDirectory, directory.Name), counters, cancellationToken);
        }
    }

    private static bool IsPathInside(string candidate, string parent)
    {
        string parentFullPath = Path.TrimEndingDirectorySeparator(Path.GetFullPath(parent)) + Path.DirectorySeparatorChar;
        string candidateFullPath = Path.GetFullPath(candidate);
        return candidateFullPath.StartsWith(parentFullPath, StringComparison.OrdinalIgnoreCase);
    }

    private sealed class BackupCounters
    {
        public int FileCount { get; set; }
        public long TotalBytes { get; set; }
    }
}
