using System.ComponentModel;
using System.Diagnostics;
using System.Text.Json;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>Firewall補正だけを同一実行ファイルの昇格helperへ委譲します。</summary>
public sealed class FirewallElevationLauncher : IFirewallElevationLauncher
{
    private readonly string _applicationPath;
    private readonly string _requestDirectory;
    private readonly IAppLogger _logger;

    /// <summary>helper起動に必要なアプリ実行パスと作業フォルダを設定します。</summary>
    public FirewallElevationLauncher(string applicationPath, string requestDirectory, IAppLogger logger)
    {
        _applicationPath = applicationPath;
        _requestDirectory = requestDirectory;
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task<OperationResult> EnsureAsync(FirewallRequirements requirements, CancellationToken cancellationToken)
    {
        string requestPath = Path.Combine(_requestDirectory, $"firewall-{Guid.NewGuid():N}.json");
        try
        {
            Directory.CreateDirectory(_requestDirectory);
            ElevatedFirewallRequest request = new ElevatedFirewallRequest { Operation = "firewall-ensure", Requirements = requirements };
            await using (FileStream stream = File.Create(requestPath))
            {
                await JsonSerializer.SerializeAsync(stream, request, cancellationToken: cancellationToken);
            }
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = _applicationPath,
                UseShellExecute = true,
                Verb = "runas",
                Arguments = $"--elevated firewall-ensure \"{requestPath}\""
            };
            _logger.Info("Firewall elevation requested.");
            using Process? process = Process.Start(startInfo);
            if (process is null)
            {
                return OperationResult.Failure("Firewall昇格helperを起動できません。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            await process.WaitForExitAsync(cancellationToken);
            if (process.ExitCode != 0)
            {
                return OperationResult.Failure("Firewall設定の更新に失敗しました。", errorCode: "FIREWALL_ENSURE_FAILED");
            }
            return OperationResult.Success();
        }
        catch (Win32Exception exception) when (exception.NativeErrorCode == 1223)
        {
            _logger.Warn("Firewall elevation was cancelled.");
            return OperationResult.Failure("Firewall設定の管理者承認が取り消されました。", errorCode: "FIREWALL_ELEVATION_CANCELLED");
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "Firewall elevation failed.");
            return OperationResult.Failure("Firewall設定の更新に失敗しました。", errorCode: "FIREWALL_ENSURE_FAILED", technicalMessage: exception.Message);
        }
        finally
        {
            try
            {
                if (File.Exists(requestPath))
                {
                    File.Delete(requestPath);
                }
            }
            catch (IOException)
            {
                _logger.Warn("Firewall elevation request cleanup was deferred.");
            }
        }
    }
}
