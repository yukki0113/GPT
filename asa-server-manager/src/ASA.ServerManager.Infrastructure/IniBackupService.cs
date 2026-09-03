using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>INI保存前のファイルを時刻別フォルダに複製します。</summary>
public sealed class IniBackupService(string backupRoot) : IIniBackupService
{
    private readonly string _backupRoot = backupRoot;

    /// <inheritdoc />
    public async Task<OperationResult<string>> BackupIniAsync(IEnumerable<string> sourcePaths, CancellationToken cancellationToken)
    {
        try
        {
            string directory = Path.Combine(_backupRoot, "ini", DateTime.Now.ToString("yyyyMMdd_HHmmss"));
            Directory.CreateDirectory(directory);
            foreach (string sourcePath in sourcePaths)
            {
                if (!File.Exists(sourcePath))
                {
                    return OperationResult<string>.Failure($"バックアップ対象INIが見つかりません: {sourcePath}");
                }
                string destinationPath = Path.Combine(directory, Path.GetFileName(sourcePath));
                await using FileStream source = File.OpenRead(sourcePath);
                await using FileStream destination = File.Create(destinationPath);
                await source.CopyToAsync(destination, cancellationToken);
            }
            return OperationResult<string>.Success(directory);
        }
        catch (Exception exception)
        {
            return OperationResult<string>.Failure($"INIバックアップに失敗しました: {exception.Message}");
        }
    }
}
