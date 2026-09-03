using System.Globalization;

namespace ASA.ServerManager.Domain;

public enum ServerState { Unconfigured, Stopped, Firewall, Installing, Updating, Starting, WaitingForRcon, Running, Saving, Stopping, Error }
public enum SupportStatus { AsaSupported, AsaSupportedConditional, AsaMapSpecific, Deprecated, AseOnly, Unverified, Unknown }
public enum GameSettingValueType { Boolean, Integer, Decimal, String, Enum, List, Complex }
public enum IniFileKind { GameUserSettings, Game }
public enum ValidationState { Valid, Warning, Invalid }

/// <summary>INI内の設定を一意に識別します。</summary>
public sealed record SettingIdentity(IniFileKind FileKind, string Section, string Key)
{
    /// <summary>大文字小文字を区別しない比較用のキーを返します。</summary>
    public string ToLookupKey()
    {
        return string.Create(CultureInfo.InvariantCulture, $"{FileKind}|{Section}|{Key}").ToUpperInvariant();
    }
}

/// <summary>外部JSONから読み込むゲーム設定の定義です。</summary>
public sealed class GameSettingDefinition
{
    public required string Id { get; init; }
    public required string DisplayNameJa { get; init; }
    public required string DisplayNameEn { get; init; }
    public required string Category { get; init; }
    public required IniFileKind FileKind { get; init; }
    public required string Section { get; init; }
    public required string Key { get; init; }
    public required GameSettingValueType ValueType { get; init; }
    public string? DefaultValue { get; init; }
    public required SupportStatus SupportStatus { get; init; }
    public required bool Deprecated { get; init; }
    public required bool RestartRequired { get; init; }
    public required IReadOnlyList<string> Sources { get; init; }
    public required string Notes { get; init; }

    /// <summary>定義のINI照合用IDを返します。</summary>
    public SettingIdentity GetIdentity()
    {
        return new SettingIdentity(FileKind, Section, Key);
    }
}

/// <summary>利用者編集値とINI現在値を分離して保持する状態です。</summary>
public sealed class GameSettingState
{
    public required string DefinitionId { get; init; }
    public bool Enabled { get; set; }
    public string? EditedValue { get; set; }
    public string? CurrentIniValue { get; set; }
    public bool ExistsInIni { get; set; }
    public ValidationState ValidationState { get; set; } = ValidationState.Valid;
}

public sealed class ServerSettings
{
    public string DedicatedServerPath { get; set; } = string.Empty;
    public string SteamCmdPath { get; set; } = string.Empty;
    public string MapId { get; set; } = string.Empty;
    public string MapLevelName { get; set; } = string.Empty;
    public string ServerName { get; set; } = string.Empty;
    public int MaxPlayers { get; set; } = 20;
    public ServerGameMode GameMode { get; set; } = ServerGameMode.Pve;
    public bool RconEnabled { get; set; } = true;
    public bool ExposeRcon { get; set; }
    public string ExtraArguments { get; set; } = string.Empty;
    public string? CustomMapModProjectId { get; set; }
    public PortSettings Ports { get; set; } = new();
    public List<GameSettingState> GameSettings { get; set; } = [];
    public List<ModDefinition> Mods { get; set; } = [];
}

public enum ServerGameMode { Pve, Pvp }
public sealed class PortSettings { public int GamePort { get; set; } = 7777; public int PeerPort { get; set; } = 7778; public int QueryPort { get; set; } = 27015; public int RconPort { get; set; } = 27020; }
public sealed class ServerSecrets { public string ServerPassword { get; set; } = string.Empty; public string AdminPassword { get; set; } = string.Empty; public string RconPassword { get; set; } = string.Empty; public string SpectatorPassword { get; set; } = string.Empty; }
public sealed class ModDefinition { public required string ProjectId { get; init; } public string Name { get; init; } = string.Empty; public bool Enabled { get; init; } = true; public int Order { get; init; } }
public sealed class MapDefinition { public required string Id { get; init; } public required string LevelName { get; init; } public required string DisplayNameJa { get; init; } }
public sealed record OperationProgress(string StepCode, string UserMessage, int? Percent);

/// <summary>ASA Server Managerが必要とする受信Firewall設定です。</summary>
public sealed class FirewallRequirements
{
    public required string ServerExecutablePath { get; init; }
    public required IReadOnlyList<int> UdpInboundPorts { get; init; }
    public required bool ExposeRcon { get; init; }
    public int? RconTcpPort { get; init; }
}

/// <summary>現在のFirewall設定が起動に利用できる状態かを表します。</summary>
public enum FirewallReadiness { Unknown, Ready, NeedsUpdate, Unavailable, Error }

/// <summary>管理対象Firewall Ruleの比較用表現です。</summary>
public sealed class ManagedFirewallRule
{
    public required string Name { get; init; }
    public required bool Enabled { get; init; }
    public required bool IsInbound { get; init; }
    public required FirewallProtocol Protocol { get; init; }
    public required IReadOnlyList<int> LocalPorts { get; init; }
    public string? ApplicationPath { get; init; }
}

/// <summary>Firewall Ruleの対象プロトコルです。</summary>
public enum FirewallProtocol { Tcp, Udp }

/// <summary>Firewall状態を画面と起動処理へ返します。</summary>
public sealed class FirewallSnapshot
{
    public FirewallReadiness Readiness { get; init; }
    public IReadOnlyList<int> ExpectedUdpPorts { get; init; } = [];
    public IReadOnlyList<int> ActualUdpPorts { get; init; } = [];
    public bool ExpectedRconExposed { get; init; }
    public bool ActualRconExposed { get; init; }
    public int? ExpectedRconTcpPort { get; init; }
    public int? ActualRconTcpPort { get; init; }
    public string? Detail { get; init; }
}

/// <summary>昇格helperへ渡す固定用途の要求です。</summary>
public sealed class ElevatedFirewallRequest
{
    public required string Operation { get; init; }
    public required FirewallRequirements Requirements { get; init; }
}

/// <summary>ネットワークアダプター上で検出したIPv4候補です。</summary>
public sealed class NetworkAddressInfo
{
    public required string AdapterName { get; init; }
    public required string AdapterDescription { get; init; }
    public required string Ipv4Address { get; init; }
    public bool IsHamachi { get; init; }
    public bool IsPrivateLan { get; init; }
}

/// <summary>接続候補として画面に出すネットワーク情報です。</summary>
public sealed class NetworkSnapshot
{
    public string? LanIpv4 { get; init; }
    public string? HamachiIpv4 { get; init; }
    public IReadOnlyList<NetworkAddressInfo> Addresses { get; init; } = [];
    public string? LanConnectCommand { get; init; }
    public string? HamachiConnectCommand { get; init; }
}

/// <summary>Saved手動バックアップの完了情報です。</summary>
public sealed class BackupInfo
{
    public required string Path { get; init; }
    public required DateTimeOffset CreatedAt { get; init; }
    public required int FileCount { get; init; }
    public required long TotalBytes { get; init; }
}

/// <summary>失敗理由を例外に依存せず呼出元へ返す結果です。</summary>
public class OperationResult
{
    public bool Succeeded { get; init; }
    public string? ErrorMessage { get; init; }
    public string? ErrorCode { get; init; }
    public string? UserMessage { get; init; }
    public string? TechnicalMessage { get; init; }
    public string? LogPath { get; init; }
    public IReadOnlyList<string> Warnings { get; init; } = [];
    public static OperationResult Success(IReadOnlyList<string>? warnings = null) => new() { Succeeded = true, Warnings = warnings ?? [] };
    public static OperationResult Failure(string message, IReadOnlyList<string>? warnings = null, string? errorCode = null, string? technicalMessage = null) => new() { Succeeded = false, ErrorMessage = message, UserMessage = message, ErrorCode = errorCode, TechnicalMessage = technicalMessage, Warnings = warnings ?? [] };
}

/// <summary>値を返す操作結果です。</summary>
public sealed class OperationResult<T> : OperationResult
{
    public T? Value { get; init; }
    public static OperationResult<T> Success(T value, IReadOnlyList<string>? warnings = null) => new() { Succeeded = true, Value = value, Warnings = warnings ?? [] };
    public static OperationResult<T> Failure(string message, IReadOnlyList<string>? warnings = null, string? errorCode = null, string? technicalMessage = null) => new() { Succeeded = false, ErrorMessage = message, UserMessage = message, ErrorCode = errorCode, TechnicalMessage = technicalMessage, Warnings = warnings ?? [] };
}
