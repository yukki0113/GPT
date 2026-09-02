using System.Diagnostics;
using System.IO.Compression;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>SteamCMDの取得とASA Dedicated Serverの更新を実装します。</summary>
public sealed class SteamCmdService : ISteamCmdService
{
    private const string SteamCmdArchiveUrl = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip";
    private const int AsaAppId = 2430930;
    private readonly HttpClient _httpClient;
    private readonly IAppLogger _logger;

    /// <summary>既定のHTTPクライアントでSteamCMDサービスを作成します。</summary>
    public SteamCmdService(HttpClient httpClient, IAppLogger logger)
    {
        _httpClient = httpClient;
        _logger = logger;
    }

    /// <inheritdoc />
    public async Task<OperationResult> EnsureInstalledAsync(string steamCmdPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        string root = GetSteamCmdRoot(steamCmdPath);
        string executable = Path.Combine(root, "steamcmd.exe");
        if (File.Exists(executable))
        {
            return OperationResult.Success();
        }
        try
        {
            progress?.Report(new OperationProgress("INSTALLING", "SteamCMDをダウンロードしています", null));
            byte[] archive = await _httpClient.GetByteArrayAsync(SteamCmdArchiveUrl, cancellationToken);
            await using MemoryStream source = new MemoryStream(archive, writable: false);
            using ZipArchive zip = new ZipArchive(source, ZipArchiveMode.Read, leaveOpen: false);
            if (zip.Entries.All(static entry => !string.Equals(entry.Name, "steamcmd.exe", StringComparison.OrdinalIgnoreCase)))
            {
                return OperationResult.Failure("SteamCMD配布物を検証できません。", errorCode: "STEAMCMD_INSTALL_FAILED");
            }
            Directory.CreateDirectory(root);
            zip.ExtractToDirectory(root, overwriteFiles: true);
            if (!File.Exists(executable))
            {
                return OperationResult.Failure("SteamCMD展開後にsteamcmd.exeが見つかりません。", errorCode: "STEAMCMD_INSTALL_FAILED");
            }
            _logger.Info("SteamCMD installation completed.");
            return OperationResult.Success();
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "SteamCMD installation failed.");
            return OperationResult.Failure("SteamCMDの導入に失敗しました。", errorCode: "STEAMCMD_INSTALL_FAILED", technicalMessage: exception.Message);
        }
    }

    /// <inheritdoc />
    public async Task<OperationResult> UpdateAsaServerAsync(string steamCmdPath, string dedicatedServerPath, IProgress<OperationProgress>? progress, CancellationToken cancellationToken)
    {
        try
        {
            string executable = Path.Combine(GetSteamCmdRoot(steamCmdPath), "steamcmd.exe");
            if (!File.Exists(executable))
            {
                return OperationResult.Failure("steamcmd.exeが見つかりません。", errorCode: "STEAMCMD_INSTALL_FAILED");
            }
            progress?.Report(new OperationProgress("UPDATING", "ASA Dedicated Serverを更新しています", null));
            SteamCmdRunResult first = await RunUpdateAsync(executable, dedicatedServerPath, cancellationToken);
            if (IsSuccessfulUpdate(first, dedicatedServerPath))
            {
                return OperationResult.Success();
            }
            if (IsBootstrapRetryCandidate(first, executable))
            {
                _logger.Warn("SteamCMD bootstrap completion detected; retrying once.");
                SteamCmdRunResult retry = await RunUpdateAsync(executable, dedicatedServerPath, cancellationToken);
                if (IsSuccessfulUpdate(retry, dedicatedServerPath))
                {
                    return OperationResult.Success();
                }
                return OperationResult.Failure("ASA Dedicated Serverの更新に失敗しました。", errorCode: "STEAMCMD_UPDATE_FAILED", technicalMessage: retry.CombinedOutput);
            }
            return OperationResult.Failure("ASA Dedicated Serverの更新に失敗しました。", errorCode: "STEAMCMD_UPDATE_FAILED", technicalMessage: first.CombinedOutput);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "SteamCMD update failed.");
            return OperationResult.Failure("ASA Dedicated Serverの更新に失敗しました。", errorCode: "STEAMCMD_UPDATE_FAILED", technicalMessage: exception.Message);
        }
    }

    private static string GetSteamCmdRoot(string configuredPath)
    {
        if (configuredPath.EndsWith("steamcmd.exe", StringComparison.OrdinalIgnoreCase))
        {
            return Path.GetDirectoryName(configuredPath) ?? configuredPath;
        }
        return configuredPath;
    }

    private static bool IsSuccessfulUpdate(SteamCmdRunResult result, string dedicatedServerPath)
    {
        return result.ExitCode == 0 && File.Exists(GetServerExecutablePath(dedicatedServerPath));
    }

    private static bool IsBootstrapRetryCandidate(SteamCmdRunResult result, string executable)
    {
        return File.Exists(executable) && (result.CombinedOutput.Contains("Updating Steam", StringComparison.OrdinalIgnoreCase) || result.CombinedOutput.Contains("Steam>", StringComparison.OrdinalIgnoreCase));
    }

    private static string GetServerExecutablePath(string dedicatedServerPath)
    {
        return Path.Combine(dedicatedServerPath, "ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe");
    }

    private static async Task<SteamCmdRunResult> RunUpdateAsync(string executable, string dedicatedServerPath, CancellationToken cancellationToken)
    {
        ProcessStartInfo startInfo = new ProcessStartInfo
        {
            FileName = executable,
            WorkingDirectory = Path.GetDirectoryName(executable) ?? Environment.CurrentDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("+force_install_dir");
        startInfo.ArgumentList.Add(dedicatedServerPath);
        startInfo.ArgumentList.Add("+login");
        startInfo.ArgumentList.Add("anonymous");
        startInfo.ArgumentList.Add("+app_update");
        startInfo.ArgumentList.Add(AsaAppId.ToString());
        startInfo.ArgumentList.Add("validate");
        startInfo.ArgumentList.Add("+quit");
        using Process process = new Process { StartInfo = startInfo };
        if (!process.Start())
        {
            return new SteamCmdRunResult(-1, "SteamCMD process did not start.");
        }
        Task<string> stdout = process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> stderr = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        string output = await stdout;
        string errors = await stderr;
        return new SteamCmdRunResult(process.ExitCode, output + Environment.NewLine + errors);
    }

    private sealed record SteamCmdRunResult(int ExitCode, string CombinedOutput);
}

/// <summary>ArkAscendedServer.exeを安全なProcess APIで起動・監視します。</summary>
public sealed class AsaProcessService : IAsaProcessService
{
    private const string AsaExecutableName = "ArkAscendedServer";
    private readonly IAppLogger _logger;

    /// <summary>プロセスサービスを作成します。</summary>
    public AsaProcessService(IAppLogger logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public Task<ProcessSnapshot> FindServerProcessAsync(string dedicatedServerPath, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        foreach (Process process in Process.GetProcessesByName(AsaExecutableName))
        {
            using (process)
            {
                try
                {
                    string processPath = process.MainModule?.FileName ?? string.Empty;
                    if (processPath.StartsWith(dedicatedServerPath, StringComparison.OrdinalIgnoreCase))
                    {
                        return Task.FromResult(new ProcessSnapshot { IsRunning = true, ProcessId = process.Id, StartedAt = new DateTimeOffset(process.StartTime.ToUniversalTime()), ExecutablePath = processPath });
                    }
                }
                catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
                {
                    _logger.Warn("Unable to inspect an ASA process.");
                }
            }
        }
        return Task.FromResult(new ProcessSnapshot { IsRunning = false });
    }

    /// <inheritdoc />
    public Task<OperationResult<ProcessSnapshot>> StartAsync(AsaStartRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!File.Exists(request.ExecutablePath))
        {
            return Task.FromResult(OperationResult<ProcessSnapshot>.Failure("ArkAscendedServer.exeが見つかりません。", errorCode: "SERVER_START_FAILED"));
        }
        try
        {
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = request.ExecutablePath,
                WorkingDirectory = request.WorkingDirectory,
                Arguments = request.Arguments,
                UseShellExecute = false,
                CreateNoWindow = false
            };
            Process? process = Process.Start(startInfo);
            if (process is null)
            {
                return Task.FromResult(OperationResult<ProcessSnapshot>.Failure("ASAプロセスを起動できません。", errorCode: "SERVER_START_FAILED"));
            }
            ProcessSnapshot snapshot = new ProcessSnapshot { IsRunning = true, ProcessId = process.Id, StartedAt = new DateTimeOffset(process.StartTime.ToUniversalTime()), ExecutablePath = request.ExecutablePath };
            process.Dispose();
            return Task.FromResult(OperationResult<ProcessSnapshot>.Success(snapshot));
        }
        catch (Exception exception)
        {
            _logger.Error(exception, "ASA process start failed.");
            return Task.FromResult(OperationResult<ProcessSnapshot>.Failure("ASAプロセスの起動に失敗しました。", errorCode: "SERVER_START_FAILED", technicalMessage: exception.Message));
        }
    }

    /// <inheritdoc />
    public async Task<bool> WaitForExitAsync(int processId, TimeSpan timeout, CancellationToken cancellationToken)
    {
        try
        {
            using Process process = Process.GetProcessById(processId);
            Task exited = process.WaitForExitAsync(cancellationToken);
            Task completed = await Task.WhenAny(exited, Task.Delay(timeout, cancellationToken));
            return completed == exited;
        }
        catch (ArgumentException)
        {
            return true;
        }
    }
}

/// <summary>Source RCONのパケットを送受信します。</summary>
public sealed class RconClient : IRconClient
{
    private const int AuthType = 3;
    private const int CommandType = 2;
    private readonly TimeSpan _timeout;

    /// <summary>指定タイムアウトでRCONクライアントを作成します。</summary>
    public RconClient(TimeSpan? timeout = null)
    {
        _timeout = timeout ?? TimeSpan.FromSeconds(5);
    }

    /// <inheritdoc />
    public async Task<RconConnectionResult> TestConnectionAsync(RconEndpoint endpoint, CancellationToken cancellationToken)
    {
        try
        {
            using CancellationTokenSource timeout = CreateTimeoutToken(cancellationToken);
            using TcpClient client = await ConnectAsync(endpoint, timeout.Token);
            NetworkStream stream = client.GetStream();
            await RconPacketCodec.WriteAsync(stream, new RconPacket(1, AuthType, endpoint.Password), timeout.Token);
            RconPacket response = await RconPacketCodec.ReadAsync(stream, timeout.Token);
            if (response.Id == -1)
            {
                return RconConnectionResult.Failure("RCON_AUTH_FAILED", "RCON認証に失敗しました。");
            }
            if (response.Id != 1)
            {
                return RconConnectionResult.Failure("RCON_PROTOCOL_ERROR", "RCON応答IDが一致しません。");
            }
            return RconConnectionResult.Success();
        }
        catch (TimeoutException)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCON接続がタイムアウトしました。");
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCON接続がタイムアウトしました。");
        }
        catch (SocketException)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCONへ接続できません。");
        }
        catch (IOException)
        {
            return RconConnectionResult.Failure("RCON_PROTOCOL_ERROR", "RCON応答を読み取れません。");
        }
    }

    /// <inheritdoc />
    public async Task<RconConnectionResult> ExecuteAsync(RconEndpoint endpoint, string command, CancellationToken cancellationToken)
    {
        RconConnectionResult connection = await TestConnectionAsync(endpoint, cancellationToken);
        if (!connection.Succeeded)
        {
            return connection;
        }
        try
        {
            using CancellationTokenSource timeout = CreateTimeoutToken(cancellationToken);
            using TcpClient client = await ConnectAsync(endpoint, timeout.Token);
            NetworkStream stream = client.GetStream();
            await RconPacketCodec.WriteAsync(stream, new RconPacket(1, AuthType, endpoint.Password), timeout.Token);
            RconPacket authentication = await RconPacketCodec.ReadAsync(stream, timeout.Token);
            if (authentication.Id == -1)
            {
                return RconConnectionResult.Failure("RCON_AUTH_FAILED", "RCON認証に失敗しました。");
            }
            await RconPacketCodec.WriteAsync(stream, new RconPacket(2, CommandType, command), timeout.Token);
            RconPacket response = await RconPacketCodec.ReadAsync(stream, timeout.Token);
            return RconConnectionResult.Success(response.Body);
        }
        catch (TimeoutException)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCON応答がタイムアウトしました。", authenticated: true);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCON応答がタイムアウトしました。", authenticated: true);
        }
        catch (SocketException)
        {
            return RconConnectionResult.Failure("RCON_NOT_READY", "RCONへ接続できません。", authenticated: true);
        }
        catch (IOException)
        {
            return RconConnectionResult.Failure("RCON_PROTOCOL_ERROR", "RCON応答を読み取れません。", authenticated: true);
        }
    }

    private async Task<TcpClient> ConnectAsync(RconEndpoint endpoint, CancellationToken cancellationToken)
    {
        TcpClient client = new TcpClient();
        using CancellationTokenSource timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_timeout);
        try
        {
            await client.ConnectAsync(endpoint.Host, endpoint.Port, timeout.Token);
            return client;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            client.Dispose();
            throw new TimeoutException();
        }
        catch
        {
            client.Dispose();
            throw;
        }
    }

    private CancellationTokenSource CreateTimeoutToken(CancellationToken cancellationToken)
    {
        CancellationTokenSource timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(_timeout);
        return timeout;
    }
}

/// <summary>Source RCONのバイナリパケットをエンコード・デコードします。</summary>
public static class RconPacketCodec
{
    /// <summary>RCONパケットを書き込みます。</summary>
    public static async Task WriteAsync(Stream stream, RconPacket packet, CancellationToken cancellationToken)
    {
        byte[] body = Encoding.UTF8.GetBytes(packet.Body);
        int size = 10 + body.Length;
        byte[] bytes = new byte[size + 4];
        BitConverter.GetBytes(size).CopyTo(bytes, 0);
        BitConverter.GetBytes(packet.Id).CopyTo(bytes, 4);
        BitConverter.GetBytes(packet.Type).CopyTo(bytes, 8);
        body.CopyTo(bytes, 12);
        await stream.WriteAsync(bytes, cancellationToken);
        await stream.FlushAsync(cancellationToken);
    }

    /// <summary>RCONパケットを一つ読み込みます。</summary>
    public static async Task<RconPacket> ReadAsync(Stream stream, CancellationToken cancellationToken)
    {
        byte[] sizeBytes = await ReadExactlyAsync(stream, 4, cancellationToken);
        int size = BitConverter.ToInt32(sizeBytes, 0);
        if (size < 10 || size > 4 * 1024 * 1024)
        {
            throw new IOException("Invalid RCON packet size.");
        }
        byte[] payload = await ReadExactlyAsync(stream, size, cancellationToken);
        int id = BitConverter.ToInt32(payload, 0);
        int type = BitConverter.ToInt32(payload, 4);
        string body = Encoding.UTF8.GetString(payload, 8, size - 10);
        return new RconPacket(id, type, body);
    }

    private static async Task<byte[]> ReadExactlyAsync(Stream stream, int length, CancellationToken cancellationToken)
    {
        byte[] bytes = new byte[length];
        int offset = 0;
        while (offset < length)
        {
            int read = await stream.ReadAsync(bytes.AsMemory(offset, length - offset), cancellationToken);
            if (read == 0)
            {
                throw new IOException("RCON stream closed unexpectedly.");
            }
            offset += read;
        }
        return bytes;
    }
}

/// <summary>Source RCONパケットの値です。</summary>
public sealed record RconPacket(int Id, int Type, string Body);

/// <summary>通常運用で使用する待機実装です。</summary>
public sealed class SystemOperationDelay : IOperationDelay
{
    /// <inheritdoc />
    public Task DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
    {
        return Task.Delay(delay, cancellationToken);
    }
}

/// <summary>日次ファイルへ秘密情報を含まないログを記録します。</summary>
public sealed class FileAppLogger : IAppLogger
{
    private readonly string _directory;
    private readonly object _syncRoot = new();

    /// <summary>ログ保存先を指定して作成します。</summary>
    public FileAppLogger(string directory)
    {
        _directory = directory;
    }

    /// <inheritdoc />
    public void Info(string message) => Write("INFO", message);

    /// <inheritdoc />
    public void Warn(string message) => Write("WARN", message);

    /// <inheritdoc />
    public void Error(Exception exception, string message) => Write("ERROR", $"{message} {exception.GetType().Name}: {exception.Message}");

    private void Write(string level, string message)
    {
        Directory.CreateDirectory(_directory);
        string path = Path.Combine(_directory, $"{DateTime.UtcNow:yyyyMMdd}.log");
        lock (_syncRoot)
        {
            string safeMessage = MaskSecretArgumentValues(message);
            File.AppendAllText(path, $"{DateTime.UtcNow:O} [{level}] {safeMessage}{Environment.NewLine}", new UTF8Encoding(false));
        }
    }

    private static string MaskSecretArgumentValues(string message)
    {
        string value = Regex.Replace(message, "(?i)(-ServerPassword=)([^\\s]+)", "$1***");
        value = Regex.Replace(value, "(?i)(-ServerAdminPassword=)([^\\s]+)", "$1***");
        return Regex.Replace(value, "(?i)(-RCONServerPassword=)([^\\s]+)", "$1***");
    }
}
