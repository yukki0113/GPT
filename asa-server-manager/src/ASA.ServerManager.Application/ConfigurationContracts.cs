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
