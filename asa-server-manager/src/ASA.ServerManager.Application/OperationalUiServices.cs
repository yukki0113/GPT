using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>画面間で最後の操作エラーコードを共有するスレッドセーフな状態です。</summary>
public sealed class ApplicationStatusStore : IApplicationStatusStore
{
    private readonly object _syncRoot = new object();
    private string? _lastErrorCode;

    /// <inheritdoc />
    public void Record(OperationResult result)
    {
        lock (_syncRoot)
        {
            if (result.Succeeded)
            {
                return;
            }
            _lastErrorCode = result.ErrorCode;
        }
    }

    /// <inheritdoc />
    public string? GetLastErrorCode()
    {
        lock (_syncRoot)
        {
            return _lastErrorCode;
        }
    }
}

/// <summary>稼働状態に応じたSaveWorldとSavedバックアップを安全な順序で実行します。</summary>
public sealed class ManualBackupCoordinator : IAsyncDisposable
{
    private readonly ServerOrchestrator _serverOrchestrator;
    private readonly IServerSettingsRepository _settingsRepository;
    private readonly ISecretRepository _secretRepository;
    private readonly IRconClient _rconClient;
    private readonly IBackupService _backupService;
    private readonly IOperationDelay _delay;
    private readonly SemaphoreSlim _operationLock = new SemaphoreSlim(1, 1);

    /// <summary>Snapshot、RCON、バックアップに必要な既存サービスを指定します。</summary>
    public ManualBackupCoordinator(ServerOrchestrator serverOrchestrator, IServerSettingsRepository settingsRepository, ISecretRepository secretRepository, IRconClient rconClient, IBackupService backupService, IOperationDelay delay)
    {
        _serverOrchestrator = serverOrchestrator;
        _settingsRepository = settingsRepository;
        _secretRepository = secretRepository;
        _rconClient = rconClient;
        _backupService = backupService;
        _delay = delay;
    }

    /// <summary>停止中は直接、稼働中はSaveWorld後15秒待ってSavedをバックアップします。</summary>
    public async Task<OperationResult<ManualBackupResult>> CreateAsync(IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        if (!await _operationLock.WaitAsync(0, cancellationToken))
        {
            return OperationResult<ManualBackupResult>.Failure("別のバックアップ操作を実行中です。", errorCode: "OPERATION_IN_PROGRESS");
        }
        try
        {
            ServerSnapshot snapshot = await _serverOrchestrator.GetSnapshotAsync(cancellationToken);
            if (IsTransitional(snapshot.State))
            {
                return OperationResult<ManualBackupResult>.Failure("サーバー操作中はバックアップできません。", errorCode: "BACKUP_STATE_INVALID");
            }
            if (snapshot.State != ServerState.Running && snapshot.State != ServerState.Stopped)
            {
                return OperationResult<ManualBackupResult>.Failure("停止中または稼働中にバックアップしてください。", errorCode: "BACKUP_STATE_INVALID");
            }
            OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
            if (!settingsResult.Succeeded || settingsResult.Value is null)
            {
                return OperationResult<ManualBackupResult>.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
            }
            bool isLiveBackup = snapshot.State == ServerState.Running;
            if (isLiveBackup)
            {
                OperationResult saveWorldResult = await SaveWorldAsync(settingsResult.Value, progress, cancellationToken);
                if (!saveWorldResult.Succeeded)
                {
                    return OperationResult<ManualBackupResult>.Failure(saveWorldResult.ErrorMessage ?? "SaveWorldに失敗したためバックアップを中止しました。", errorCode: saveWorldResult.ErrorCode ?? "SAVEWORLD_FAILED", technicalMessage: saveWorldResult.TechnicalMessage);
                }
                await _delay.DelayAsync(TimeSpan.FromSeconds(15), cancellationToken);
            }
            progress?.Report(new OperationProgress("BACKUP", "Savedバックアップを作成しています", null));
            OperationResult<BackupInfo> backupResult = await _backupService.CreateSavedBackupAsync(settingsResult.Value.DedicatedServerPath, cancellationToken);
            if (!backupResult.Succeeded || backupResult.Value is null)
            {
                return OperationResult<ManualBackupResult>.Failure(backupResult.ErrorMessage ?? "Savedバックアップに失敗しました。", backupResult.Warnings, backupResult.ErrorCode, backupResult.TechnicalMessage);
            }
            string? warning = null;
            List<string> warnings = [];
            if (isLiveBackup)
            {
                warning = "SaveWorld後のライブバックアップです。コピー中の完全なfilesystem freezeではありません。";
                warnings.Add(warning);
            }
            return OperationResult<ManualBackupResult>.Success(new ManualBackupResult { Backup = backupResult.Value, IsLiveBackup = isLiveBackup, Warning = warning }, warnings);
        }
        catch (OperationCanceledException)
        {
            return OperationResult<ManualBackupResult>.Failure("Savedバックアップを取り消しました。", errorCode: "BACKUP_CANCELLED");
        }
        finally
        {
            _operationLock.Release();
        }
    }

    /// <inheritdoc />
    public ValueTask DisposeAsync()
    {
        _operationLock.Dispose();
        return ValueTask.CompletedTask;
    }

    private async Task<OperationResult> SaveWorldAsync(ServerSettings settings, IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        OperationResult<ServerSecrets> secretsResult = await _secretRepository.LoadAsync(cancellationToken);
        if (!secretsResult.Succeeded || secretsResult.Value is null)
        {
            return OperationResult.Failure(secretsResult.ErrorMessage ?? "RCON秘密情報を読み込めません。", errorCode: "SECRETS_LOAD_FAILED");
        }
        progress?.Report(new OperationProgress("SAVING", "ワールドを保存しています", null));
        RconEndpoint endpoint = new RconEndpoint("127.0.0.1", settings.Ports.RconPort, secretsResult.Value.RconPassword);
        RconConnectionResult result = await _rconClient.ExecuteAsync(endpoint, "SaveWorld", cancellationToken);
        if (!result.Succeeded)
        {
            return OperationResult.Failure("SaveWorldに失敗したためバックアップを中止しました。", errorCode: "SAVEWORLD_FAILED", technicalMessage: result.ErrorMessage);
        }
        return OperationResult.Success();
    }

    private static bool IsTransitional(ServerState state)
    {
        return state == ServerState.Firewall || state == ServerState.Installing || state == ServerState.Updating || state == ServerState.Starting || state == ServerState.WaitingForRcon || state == ServerState.Saving || state == ServerState.Stopping;
    }
}

/// <summary>秘密情報を含めず、現在状態と件数制限済みログを診断表示へ集約します。</summary>
public sealed class DiagnosticsService
{
    private readonly ServerOrchestrator _serverOrchestrator;
    private readonly IServerSettingsRepository _settingsRepository;
    private readonly ILogFileService _logFileService;
    private readonly IApplicationStatusStore _statusStore;
    private readonly string _appVersion;

    /// <summary>診断表示に必要なサービスを指定します。</summary>
    public DiagnosticsService(ServerOrchestrator serverOrchestrator, IServerSettingsRepository settingsRepository, ILogFileService logFileService, IApplicationStatusStore statusStore, string appVersion)
    {
        _serverOrchestrator = serverOrchestrator;
        _settingsRepository = settingsRepository;
        _logFileService = logFileService;
        _statusStore = statusStore;
        _appVersion = appVersion;
    }

    /// <summary>現在の診断Summaryと最新ログ末尾を返します。</summary>
    public async Task<OperationResult<DiagnosticsSnapshot>> LoadAsync(int maximumLogLines, CancellationToken cancellationToken)
    {
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return OperationResult<DiagnosticsSnapshot>.Failure(settingsResult.ErrorMessage ?? "基本設定を読み込めません。", errorCode: "SETTINGS_LOAD_FAILED");
        }
        ServerSnapshot server = await _serverOrchestrator.GetSnapshotAsync(cancellationToken);
        OperationResult<LogTailSnapshot> logResult = await _logFileService.ReadTailAsync(maximumLogLines, cancellationToken);
        if (!logResult.Succeeded || logResult.Value is null)
        {
            return OperationResult<DiagnosticsSnapshot>.Failure(logResult.ErrorMessage ?? "ログを読み込めません。", errorCode: logResult.ErrorCode ?? "LOG_READ_FAILED");
        }
        DiagnosticsSnapshot snapshot = new DiagnosticsSnapshot
        {
            AppVersion = _appVersion,
            ServerState = server.State,
            ServerPath = settingsResult.Value.DedicatedServerPath,
            SteamCmdPath = settingsResult.Value.SteamCmdPath,
            Firewall = server.Firewall?.Readiness,
            LanIpv4 = server.Network?.LanIpv4,
            HamachiIpv4 = server.Network?.HamachiIpv4,
            CurrentLogPath = logResult.Value.Path,
            LastErrorCode = _statusStore.GetLastErrorCode(),
            LogLines = logResult.Value.Lines
        };
        return OperationResult<DiagnosticsSnapshot>.Success(snapshot);
    }

    /// <summary>ログ保存フォルダーのパスを返します。</summary>
    public string GetLogDirectory()
    {
        return _logFileService.GetLogDirectory();
    }
}
