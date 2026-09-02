using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>ゲーム設定カタログを取得します。</summary>
public interface IGameSettingCatalogRepository
{
    /// <summary>カタログを検証して読み込みます。</summary>
    Task<OperationResult<IReadOnlyList<GameSettingDefinition>>> LoadAsync(CancellationToken cancellationToken);
}

/// <summary>秘密情報を除くサーバー設定を保存します。</summary>
public interface IServerSettingsRepository
{
    /// <summary>設定を読み込みます。</summary>
    Task<OperationResult<ServerSettings>> LoadAsync(CancellationToken cancellationToken);
    /// <summary>設定を保存します。</summary>
    Task<OperationResult> SaveAsync(ServerSettings settings, CancellationToken cancellationToken);
}

/// <summary>暗号化された秘密情報を保存します。</summary>
public interface ISecretRepository
{
    /// <summary>秘密情報を読み込みます。</summary>
    Task<OperationResult<ServerSecrets>> LoadAsync(CancellationToken cancellationToken);
    /// <summary>秘密情報を保存します。</summary>
    Task<OperationResult> SaveAsync(ServerSecrets secrets, CancellationToken cancellationToken);
}

/// <summary>INIファイルのバックアップを作成します。</summary>
public interface IBackupService
{
    /// <summary>指定INIを同じ時刻フォルダへ退避します。</summary>
    Task<OperationResult<string>> BackupIniAsync(IEnumerable<string> sourcePaths, CancellationToken cancellationToken);
}

/// <summary>順序保持INIドキュメントを読み書きします。</summary>
public interface IIniDocumentService
{
    /// <summary>INIファイルを読み込みます。</summary>
    Task<OperationResult<IniDocument>> LoadAsync(string path, IniFileKind fileKind, CancellationToken cancellationToken);
    /// <summary>INIファイルを原子的に保存します。</summary>
    Task<OperationResult> SaveAsync(string path, IniDocument document, CancellationToken cancellationToken);
}

/// <summary>SteamCMDの導入確認とASA更新を実行します。</summary>
public interface ISteamCmdService
{
    /// <summary>SteamCMD本体を導入済みにします。</summary>
    Task<OperationResult> EnsureInstalledAsync(string steamCmdPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken);

    /// <summary>ASA Dedicated Serverを更新します。</summary>
    Task<OperationResult> UpdateAsaServerAsync(string steamCmdPath, string dedicatedServerPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken);
}

/// <summary>ASAプロセスの起動と状態照会を行います。</summary>
public interface IAsaProcessService
{
    /// <summary>管理対象のASAプロセスを検出します。</summary>
    Task<ProcessSnapshot> FindServerProcessAsync(string dedicatedServerPath, CancellationToken cancellationToken);

    /// <summary>ASAプロセスを起動します。</summary>
    Task<OperationResult<ProcessSnapshot>> StartAsync(AsaStartRequest request, CancellationToken cancellationToken);

    /// <summary>指定プロセスの終了を待機します。</summary>
    Task<bool> WaitForExitAsync(int processId, TimeSpan timeout, CancellationToken cancellationToken);
}

/// <summary>ASAのSource RCONを操作します。</summary>
public interface IRconClient
{
    /// <summary>認証まで含めてRCON接続を確認します。</summary>
    Task<RconConnectionResult> TestConnectionAsync(RconEndpoint endpoint, CancellationToken cancellationToken);

    /// <summary>認証済みRCONへコマンドを送信します。</summary>
    Task<RconConnectionResult> ExecuteAsync(RconEndpoint endpoint, string command, CancellationToken cancellationToken);
}

/// <summary>実行済みのゲーム設定をINIへ安全に保存します。</summary>
public interface IEnabledIniSettingsSaver
{
    /// <summary>有効設定のみを既存INIへ反映します。</summary>
    Task<OperationResult> SaveEnabledSettingsAsync(ServerSettings settings, CancellationToken cancellationToken);
}

/// <summary>秘密情報を除外して運用ログを記録します。</summary>
public interface IAppLogger
{
    /// <summary>情報ログを記録します。</summary>
    void Info(string message);

    /// <summary>警告ログを記録します。</summary>
    void Warn(string message);

    /// <summary>例外を伴うエラーログを記録します。</summary>
    void Error(Exception exception, string message);
}

/// <summary>テスト可能な待機処理を提供します。</summary>
public interface IOperationDelay
{
    /// <summary>指定時間待機します。</summary>
    Task DelayAsync(TimeSpan delay, CancellationToken cancellationToken);
}
