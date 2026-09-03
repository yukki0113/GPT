using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using ASA.ServerManager.Application;
using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Infrastructure;

/// <summary>OSのネットワークアダプターを読み取る境界です。</summary>
public interface INetworkInterfaceProvider
{
    /// <summary>稼働中アダプターのIPv4候補を返します。</summary>
    IReadOnlyList<NetworkInterfaceRecord> GetActiveInterfaces();
}

/// <summary>ネットワークアダプターから取得した比較用データです。</summary>
public sealed class NetworkInterfaceRecord
{
    public required string Name { get; init; }
    public required string Description { get; init; }
    public required NetworkInterfaceType InterfaceType { get; init; }
    public required IReadOnlyList<IPAddress> UnicastAddresses { get; init; }
}

/// <summary>System.Net.NetworkInformationを使用する実adapterです。</summary>
public sealed class SystemNetworkInterfaceProvider : INetworkInterfaceProvider
{
    /// <inheritdoc />
    public IReadOnlyList<NetworkInterfaceRecord> GetActiveInterfaces()
    {
        List<NetworkInterfaceRecord> records = [];
        foreach (NetworkInterface networkInterface in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (networkInterface.OperationalStatus != OperationalStatus.Up || networkInterface.NetworkInterfaceType == NetworkInterfaceType.Loopback)
            {
                continue;
            }
            List<IPAddress> addresses = networkInterface.GetIPProperties().UnicastAddresses
                .Select(static address => address.Address)
                .Where(static address => address.AddressFamily == AddressFamily.InterNetwork)
                .ToList();
            records.Add(new NetworkInterfaceRecord
            {
                Name = networkInterface.Name,
                Description = networkInterface.Description,
                InterfaceType = networkInterface.NetworkInterfaceType,
                UnicastAddresses = addresses
            });
        }
        return records;
    }
}

/// <summary>LANおよびHamachiのIPv4接続候補を表示用モデルへ変換します。</summary>
public sealed class NetworkInfoService : INetworkInfoService
{
    private readonly INetworkInterfaceProvider _provider;
    private readonly IAppLogger _logger;

    /// <summary>実OS adapterでネットワークサービスを作成します。</summary>
    public NetworkInfoService(IAppLogger logger) : this(new SystemNetworkInterfaceProvider(), logger)
    {
    }

    /// <summary>テスト可能なadapterでネットワークサービスを作成します。</summary>
    public NetworkInfoService(INetworkInterfaceProvider provider, IAppLogger logger)
    {
        _provider = provider;
        _logger = logger;
    }

    /// <inheritdoc />
    public Task<NetworkSnapshot> GetSnapshotAsync(int gamePort, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        List<NetworkAddressInfo> candidates = [];
        foreach (NetworkInterfaceRecord networkInterface in _provider.GetActiveInterfaces())
        {
            bool isHamachi = ContainsHamachi(networkInterface.Name) || ContainsHamachi(networkInterface.Description);
            foreach (IPAddress address in networkInterface.UnicastAddresses)
            {
                if (IsExcluded(address))
                {
                    continue;
                }
                bool privateLan = IsPrivateIpv4(address);
                candidates.Add(new NetworkAddressInfo
                {
                    AdapterName = networkInterface.Name,
                    AdapterDescription = networkInterface.Description,
                    Ipv4Address = address.ToString(),
                    IsHamachi = isHamachi,
                    IsPrivateLan = privateLan
                });
            }
        }
        NetworkAddressInfo? lan = candidates.FirstOrDefault(static candidate => candidate.IsPrivateLan && !candidate.IsHamachi);
        NetworkAddressInfo? hamachi = candidates.FirstOrDefault(static candidate => candidate.IsHamachi);
        _logger.Info($"Network address candidates: {candidates.Count}; Hamachi candidate: {hamachi is not null}.");
        return Task.FromResult(new NetworkSnapshot
        {
            Addresses = candidates,
            LanIpv4 = lan?.Ipv4Address,
            HamachiIpv4 = hamachi?.Ipv4Address,
            LanConnectCommand = CreateConnectCommand(lan, gamePort),
            HamachiConnectCommand = CreateConnectCommand(hamachi, gamePort)
        });
    }

    private static string? CreateConnectCommand(NetworkAddressInfo? candidate, int gamePort)
    {
        if (candidate is null || gamePort is < 1 or > 65535)
        {
            return null;
        }
        return $"open {candidate.Ipv4Address}:{gamePort}";
    }

    private static bool ContainsHamachi(string value)
    {
        return value.Contains("Hamachi", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsExcluded(IPAddress address)
    {
        byte[] bytes = address.GetAddressBytes();
        return IPAddress.IsLoopback(address) || (bytes[0] == 169 && bytes[1] == 254) || address.Equals(IPAddress.Any);
    }

    private static bool IsPrivateIpv4(IPAddress address)
    {
        byte[] bytes = address.GetAddressBytes();
        if (bytes[0] == 10 || (bytes[0] == 192 && bytes[1] == 168))
        {
            return true;
        }
        return bytes[0] == 172 && bytes[1] is >= 16 and <= 31;
    }
}
