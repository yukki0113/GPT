using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>更新、設定保存、起動、RCON待機、および安全停止を直列に実行します。</summary>
public sealed class ServerOrchestrator : IAsyncDisposable
{
    private readonly IServerSettingsRepository _settingsRepository;
    private readonly ISecretRepository _secretRepository;
    private readonly ISteamCmdService _steamCmdService;
    private readonly IAsaProcessService _processService;
    private readonly IRconClient _rconClient;
    private readonly IEnabledIniSettingsSaver _iniSettingsSaver;
    private readonly ServerArgumentBuilder _argumentBuilder;
    private readonly ServerStateResolver _stateResolver;
    private readonly IOperationDelay _delay;
    private readonly IAppLogger _logger;
    private readonly SemaphoreSlim _operationLock = new(1, 1);
    private ServerState? _operationState;

    /// <summary>実行時サービスを受け取り、状態操作の窓口を作成します。</summary>
    public ServerOrchestrator(
        IServerSettingsRepository settingsRepository,
        ISecretRepository secretRepository,
        ISteamCmdService steamCmdService,
        IAsaProcessService processService,
        IRconClient rconClient,
        IEnabledIniSettingsSaver iniSettingsSaver,
        ServerArgumentBuilder argumentBuilder,
        ServerStateResolver stateResolver,
        IOperationDelay delay,
        IAppLogger logger)
    {
        _settingsRepository = settingsRepository;
        _secretRepository = secretRepository;
        _steamCmdService = steamCmdService;
        _processService = processService;
        _rconClient = rconClient;
        _iniSettingsSaver = iniSettingsSaver;
        _argumentBuilder = argumentBuilder;
        _stateResolver = stateResolver;
        _delay = delay;
        _logger = logger;
    }

    /// <summary>実プロセスとRCONから最新スナップショットを取得します。</summary>
    public async Task<ServerSnapshot> GetSnapshotAsync(CancellationToken cancellationToken)
    {
        if (_operationState is not null)
        {
            return new ServerSnapshot { State = _operationState.Value, Detail = "サーバー操作を実行しています。" };
        }
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return new ServerSnapshot { State = ServerState.Error, Detail = settingsResult.ErrorMessage ?? "設定を読み込めません。" };
        }
        ServerSettings settings = settingsResult.Value;
        if (!ValidateSettings(settings, null).Succeeded)
        {
            return new ServerSnapshot { State = ServerState.Unconfigured, Detail = "必須設定が未完了です。" };
        }
        ProcessSnapshot process = await _processService.FindServerProcessAsync(settings.DedicatedServerPath, cancellationToken);
        RconConnectionResult? rcon = null;
        if (process.IsRunning)
        {
            OperationResult<ServerSecrets> secretsResult = await _secretRepository.LoadAsync(cancellationToken);
            if (secretsResult.Succeeded && secretsResult.Value is not null)
            {
                rcon = await _rconClient.TestConnectionAsync(CreateRconEndpoint(settings, secretsResult.Value), cancellationToken);
            }
        }
        return _stateResolver.Resolve(true, process, rcon);
    }

    /// <summary>停止中のASAを更新して起動します。</summary>
    public async Task<OperationResult> StartAsync(IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        await _operationLock.WaitAsync(cancellationToken);
        try
        {
            ServerSnapshot snapshot = await GetSnapshotIgnoringOperationStateAsync(cancellationToken);
            if (snapshot.State == ServerState.Running)
            {
                return OperationResult.Failure("サーバーは既に稼働中です。", errorCode: "SERVER_ALREADY_RUNNING");
            }
            if (snapshot.State == ServerState.WaitingForRcon || snapshot.State == ServerState.Starting)
            {
                return OperationResult.Failure("ASAプロセスは既に起動処理中です。", errorCode: "SERVER_ALREADY_RUNNING");
            }
            return await StartCoreAsync(progress, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("起動処理を取り消しました。", errorCode: "OPERATION_CANCELLED");
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Start operation failed.");
            SetState(ServerState.Error);
            return OperationResult.Failure("起動処理中に予期しないエラーが発生しました。", errorCode: "SERVER_START_FAILED", technicalMessage: exception.Message);
        }
        finally
        {
            _operationState = null;
            _operationLock.Release();
        }
    }

    /// <summary>稼働中のASAをSaveWorld後に再起動します。</summary>
    public async Task<OperationResult> RestartAsync(IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        await _operationLock.WaitAsync(cancellationToken);
        try
        {
            RuntimeContext? context = await LoadAndValidateContextAsync(cancellationToken);
            if (context is null)
            {
                return OperationResult.Failure("設定を確認できません。", errorCode: "CFG_REQUIRED_MISSING");
            }
            ServerSnapshot snapshot = await GetSnapshotIgnoringOperationStateAsync(cancellationToken);
            if (snapshot.State != ServerState.Running || snapshot.ProcessId is null)
            {
                return OperationResult.Failure("再起動にはRCON接続済みの稼働状態が必要です。", errorCode: "RCON_NOT_READY");
            }
            OperationResult stopResult = await StopRunningCoreAsync(context, snapshot.ProcessId.Value, progress, cancellationToken);
            if (!stopResult.Succeeded)
            {
                return stopResult;
            }
            return await StartCoreAsync(progress, cancellationToken, context);
        }
        catch (OperationCanceledException)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("再起動処理を取り消しました。", errorCode: "OPERATION_CANCELLED");
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Restart operation failed.");
            SetState(ServerState.Error);
            return OperationResult.Failure("再起動処理中に予期しないエラーが発生しました。", errorCode: "SERVER_START_FAILED", technicalMessage: exception.Message);
        }
        finally
        {
            _operationState = null;
            _operationLock.Release();
        }
    }

    /// <summary>稼働中のASAをSaveWorld後に安全停止します。</summary>
    public async Task<OperationResult> StopAsync(IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        await _operationLock.WaitAsync(cancellationToken);
        try
        {
            RuntimeContext? context = await LoadAndValidateContextAsync(cancellationToken);
            if (context is null)
            {
                return OperationResult.Failure("設定を確認できません。", errorCode: "CFG_REQUIRED_MISSING");
            }
            ServerSnapshot snapshot = await GetSnapshotIgnoringOperationStateAsync(cancellationToken);
            if (snapshot.State != ServerState.Running || snapshot.ProcessId is null)
            {
                return OperationResult.Failure("停止にはRCON接続済みの稼働状態が必要です。", errorCode: "RCON_NOT_READY");
            }
            return await StopRunningCoreAsync(context, snapshot.ProcessId.Value, progress, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("停止処理を取り消しました。", errorCode: "OPERATION_CANCELLED");
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Stop operation failed.");
            SetState(ServerState.Error);
            return OperationResult.Failure("停止処理中に予期しないエラーが発生しました。", errorCode: "STOP_TIMEOUT", technicalMessage: exception.Message);
        }
        finally
        {
            _operationState = null;
            _operationLock.Release();
        }
    }

    private async Task<OperationResult> StartCoreAsync(IProgress<OperationProgress>? progress, CancellationToken cancellationToken, RuntimeContext? existingContext = null)
    {
        RuntimeContext? context = existingContext ?? await LoadAndValidateContextAsync(cancellationToken);
        if (context is null)
        {
            SetState(ServerState.Unconfigured);
            return OperationResult.Failure("必須設定を確認してください。", errorCode: "CFG_REQUIRED_MISSING");
        }
        SetState(ServerState.Installing);
        Report(progress, "INSTALLING", "SteamCMDを確認しています", null);
        OperationResult ensureResult = await _steamCmdService.EnsureInstalledAsync(context.Settings.SteamCmdPath, progress, cancellationToken);
        if (!ensureResult.Succeeded)
        {
            return Fail(ensureResult, ServerState.Error, "STEAMCMD_INSTALL_FAILED");
        }
        SetState(ServerState.Updating);
        Report(progress, "UPDATING", "サーバーを更新しています", null);
        OperationResult updateResult = await _steamCmdService.UpdateAsaServerAsync(context.Settings.SteamCmdPath, context.Settings.DedicatedServerPath, progress, cancellationToken);
        if (!updateResult.Succeeded)
        {
            return Fail(updateResult, ServerState.Error, "STEAMCMD_UPDATE_FAILED");
        }
        OperationResult saveResult = await _iniSettingsSaver.SaveEnabledSettingsAsync(context.Settings, cancellationToken);
        if (!saveResult.Succeeded)
        {
            return Fail(saveResult, ServerState.Error, "INI_SAVE_FAILED");
        }
        OperationResult<ServerArgumentBuildResult> argumentsResult = _argumentBuilder.Build(context.Settings, context.Secrets);
        if (!argumentsResult.Succeeded || argumentsResult.Value is null)
        {
            SetState(ServerState.Error);
            return argumentsResult;
        }
        string executablePath = Path.Combine(context.Settings.DedicatedServerPath, "ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe");
        SetState(ServerState.Starting);
        Report(progress, "STARTING", "サーバーを起動しています", null);
        _logger.Info($"Starting ASA process: {argumentsResult.Value.MaskedArguments}");
        OperationResult<ProcessSnapshot> startResult = await _processService.StartAsync(new AsaStartRequest { ExecutablePath = executablePath, WorkingDirectory = Path.GetDirectoryName(executablePath) ?? context.Settings.DedicatedServerPath, Arguments = argumentsResult.Value.Arguments }, cancellationToken);
        if (!startResult.Succeeded || startResult.Value?.ProcessId is null)
        {
            return Fail(startResult, ServerState.Error, "SERVER_START_FAILED");
        }
        bool exitedEarly = await _processService.WaitForExitAsync(startResult.Value.ProcessId.Value, TimeSpan.FromSeconds(10), cancellationToken);
        if (exitedEarly)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("ASAプロセスが起動直後に終了しました。", errorCode: "SERVER_EXITED_EARLY");
        }
        SetState(ServerState.WaitingForRcon);
        Report(progress, "WAITING_RCON", "サーバーの準備完了を待っています", null);
        DateTimeOffset deadline = DateTimeOffset.UtcNow.AddMinutes(10);
        while (DateTimeOffset.UtcNow < deadline)
        {
            RconConnectionResult rcon = await _rconClient.TestConnectionAsync(CreateRconEndpoint(context.Settings, context.Secrets), cancellationToken);
            if (rcon.Succeeded)
            {
                SetState(ServerState.Running);
                Report(progress, "RUNNING", "サーバーは稼働中です", 100);
                return OperationResult.Success();
            }
            await _delay.DelayAsync(TimeSpan.FromSeconds(3), cancellationToken);
        }
        SetState(ServerState.Error);
        return OperationResult.Failure("RCONの準備完了を確認できませんでした。", errorCode: "RCON_NOT_READY");
    }

    private async Task<OperationResult> StopRunningCoreAsync(RuntimeContext context, int processId, IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        SetState(ServerState.Saving);
        Report(progress, "SAVING", "ワールドを保存しています", null);
        RconConnectionResult saveResult = await _rconClient.ExecuteAsync(CreateRconEndpoint(context.Settings, context.Secrets), "SaveWorld", cancellationToken);
        if (!saveResult.Succeeded)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("SaveWorldに失敗したため停止を中止しました。", errorCode: "SAVEWORLD_FAILED", technicalMessage: saveResult.ErrorMessage);
        }
        await _delay.DelayAsync(TimeSpan.FromSeconds(15), cancellationToken);
        SetState(ServerState.Stopping);
        Report(progress, "STOPPING", "サーバーを停止しています", null);
        RconConnectionResult exitResult = await _rconClient.ExecuteAsync(CreateRconEndpoint(context.Settings, context.Secrets), "DoExit", cancellationToken);
        if (!exitResult.Succeeded)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("DoExitに失敗しました。", errorCode: "DOEXIT_FAILED", technicalMessage: exitResult.ErrorMessage);
        }
        bool exited = await _processService.WaitForExitAsync(processId, TimeSpan.FromSeconds(60), cancellationToken);
        if (!exited)
        {
            SetState(ServerState.Error);
            return OperationResult.Failure("ASAプロセスの終了待機がタイムアウトしました。強制終了は実行していません。", errorCode: "STOP_TIMEOUT");
        }
        SetState(ServerState.Stopped);
        return OperationResult.Success();
    }

    private async Task<RuntimeContext?> LoadAndValidateContextAsync(CancellationToken cancellationToken)
    {
        OperationResult<ServerSettings> settingsResult = await _settingsRepository.LoadAsync(cancellationToken);
        if (!settingsResult.Succeeded || settingsResult.Value is null)
        {
            return null;
        }
        OperationResult<ServerSecrets> secretsResult = await _secretRepository.LoadAsync(cancellationToken);
        if (!secretsResult.Succeeded || secretsResult.Value is null)
        {
            return null;
        }
        OperationResult validation = ValidateSettings(settingsResult.Value, secretsResult.Value);
        if (!validation.Succeeded)
        {
            return null;
        }
        return new RuntimeContext(settingsResult.Value, secretsResult.Value);
    }

    private async Task<ServerSnapshot> GetSnapshotIgnoringOperationStateAsync(CancellationToken cancellationToken)
    {
        ServerState? state = _operationState;
        _operationState = null;
        try
        {
            return await GetSnapshotAsync(cancellationToken);
        }
        finally
        {
            _operationState = state;
        }
    }

    private static OperationResult ValidateSettings(ServerSettings settings, ServerSecrets? secrets)
    {
        if (string.IsNullOrWhiteSpace(settings.DedicatedServerPath) || string.IsNullOrWhiteSpace(settings.SteamCmdPath) || string.IsNullOrWhiteSpace(settings.ServerName) || string.IsNullOrWhiteSpace(settings.MapLevelName))
        {
            return OperationResult.Failure("サーバーの必須設定が不足しています。", errorCode: "CFG_REQUIRED_MISSING");
        }
        if (settings.MaxPlayers <= 0)
        {
            return OperationResult.Failure("最大人数は1以上で指定してください。", errorCode: "CFG_REQUIRED_MISSING");
        }
        int[] ports = [settings.Ports.GamePort, settings.Ports.PeerPort, settings.Ports.QueryPort, settings.Ports.RconPort];
        if (ports.Any(static port => port is < 1 or > 65535))
        {
            return OperationResult.Failure("ポート番号は1から65535で指定してください。", errorCode: "CFG_INVALID_PORT");
        }
        if (!settings.RconEnabled)
        {
            return OperationResult.Failure("通常運用ではRCONを有効にしてください。", errorCode: "CFG_REQUIRED_MISSING");
        }
        if (secrets is not null && string.IsNullOrWhiteSpace(secrets.AdminPassword))
        {
            return OperationResult.Failure("管理者パスワードが未設定です。", errorCode: "CFG_REQUIRED_MISSING");
        }
        return OperationResult.Success();
    }

    private static RconEndpoint CreateRconEndpoint(ServerSettings settings, ServerSecrets secrets)
    {
        string password = secrets.AdminPassword;
        if (!string.IsNullOrWhiteSpace(secrets.RconPassword))
        {
            password = secrets.RconPassword;
        }
        return new RconEndpoint("127.0.0.1", settings.Ports.RconPort, password);
    }

    private OperationResult Fail(OperationResult result, ServerState state, string fallbackCode)
    {
        SetState(state);
        return OperationResult.Failure(result.ErrorMessage ?? "サーバー操作に失敗しました。", result.Warnings, result.ErrorCode ?? fallbackCode, result.TechnicalMessage);
    }

    private void SetState(ServerState state)
    {
        _operationState = state;
    }

    private static void Report(IProgress<OperationProgress>? progress, string stepCode, string message, int? percent)
    {
        progress?.Report(new OperationProgress(stepCode, message, percent));
    }

    /// <inheritdoc />
    public ValueTask DisposeAsync()
    {
        _operationLock.Dispose();
        return ValueTask.CompletedTask;
    }

    private sealed record RuntimeContext(ServerSettings Settings, ServerSecrets Secrets);
}
