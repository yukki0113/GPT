namespace ASA.ServerManager.Domain;

/// <summary>サーバープロセスとRCON確認から復元した現在状態です。</summary>
public sealed class ServerSnapshot
{
    public required ServerState State { get; init; }
    public string Detail { get; init; } = string.Empty;
    public int? ProcessId { get; init; }
    public bool IsRconReady { get; init; }
    public FirewallSnapshot? Firewall { get; init; }
    public NetworkSnapshot? Network { get; init; }
    public DateTimeOffset ObservedAt { get; init; } = DateTimeOffset.UtcNow;
}

/// <summary>ASAプロセスの確認結果です。</summary>
public sealed class ProcessSnapshot
{
    public bool IsRunning { get; init; }
    public int? ProcessId { get; init; }
    public DateTimeOffset? StartedAt { get; init; }
    public string? ExecutablePath { get; init; }
}

/// <summary>RCON接続先です。</summary>
public sealed record RconEndpoint(string Host, int Port, string Password);

/// <summary>ASA起動に必要な、秘密情報を含む一回限りの要求です。</summary>
public sealed class AsaStartRequest
{
    public required string ExecutablePath { get; init; }
    public required string WorkingDirectory { get; init; }
    public required string Arguments { get; init; }
}

/// <summary>RCONの接続またはコマンド実行結果です。</summary>
public sealed class RconConnectionResult
{
    public bool Succeeded { get; init; }
    public bool IsAuthenticated { get; init; }
    public string? Response { get; init; }
    public string? ErrorCode { get; init; }
    public string? ErrorMessage { get; init; }
    public static RconConnectionResult Success(string? response = null) => new() { Succeeded = true, IsAuthenticated = true, Response = response };
    public static RconConnectionResult Failure(string code, string message, bool authenticated = false) => new() { Succeeded = false, IsAuthenticated = authenticated, ErrorCode = code, ErrorMessage = message };
}
