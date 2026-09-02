using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>Windows DPAPI CurrentUserで秘密情報を暗号化して保存します。</summary>
public sealed class DpapiSecretRepository(string path) : ISecretRepository
{
    private readonly string _path = path;

    /// <inheritdoc />
    public async Task<OperationResult<ServerSecrets>> LoadAsync(CancellationToken cancellationToken)
    {
        try
        {
            if (!File.Exists(_path)) { return OperationResult<ServerSecrets>.Success(new ServerSecrets()); }
            byte[] encrypted = await File.ReadAllBytesAsync(_path, cancellationToken);
            byte[] plain = ProtectedData.Unprotect(encrypted, null, DataProtectionScope.CurrentUser);
            ServerSecrets? secrets = JsonSerializer.Deserialize<ServerSecrets>(plain);
            if (secrets is null) { return OperationResult<ServerSecrets>.Failure("secrets.datの内容を復号できません。"); }
            return OperationResult<ServerSecrets>.Success(secrets);
        }
        catch (CryptographicException) { return OperationResult<ServerSecrets>.Failure("secrets.datを復号できません。別ユーザーのデータまたは破損データです。"); }
        catch (Exception exception) { return OperationResult<ServerSecrets>.Failure($"秘密情報の読込に失敗しました: {exception.Message}"); }
    }

    /// <inheritdoc />
    public async Task<OperationResult> SaveAsync(ServerSecrets secrets, CancellationToken cancellationToken)
    {
        try
        {
            string directory = Path.GetDirectoryName(_path) ?? throw new InvalidOperationException("秘密情報ファイルの親ディレクトリが不明です。");
            Directory.CreateDirectory(directory);
            byte[] plain = JsonSerializer.SerializeToUtf8Bytes(secrets);
            byte[] encrypted = ProtectedData.Protect(plain, null, DataProtectionScope.CurrentUser);
            await File.WriteAllBytesAsync(_path, encrypted, cancellationToken);
            CryptographicOperations.ZeroMemory(plain);
            return OperationResult.Success();
        }
        catch (Exception exception) { return OperationResult.Failure($"秘密情報の保存に失敗しました: {exception.Message}"); }
    }
}
