using ASA.ServerManager.Domain;

namespace ASA.ServerManager.Application;

/// <summary>設定、プロセス、RCONを優先順に評価してサーバー状態を決定します。</summary>
public sealed class ServerStateResolver
{
    /// <summary>観測値から状態を解決します。</summary>
    public ServerSnapshot Resolve(bool isConfigured, ProcessSnapshot process, RconConnectionResult? rcon)
    {
        if (!isConfigured)
        {
            return new ServerSnapshot { State = ServerState.Unconfigured, Detail = "必須設定が未完了です。" };
        }
        if (!process.IsRunning)
        {
            return new ServerSnapshot { State = ServerState.Stopped, Detail = "ASAプロセスは停止しています。" };
        }
        if (rcon is not null && rcon.Succeeded)
        {
            return new ServerSnapshot { State = ServerState.Running, Detail = "RCON接続を確認しました。", ProcessId = process.ProcessId, IsRconReady = true };
        }
        return new ServerSnapshot { State = ServerState.WaitingForRcon, Detail = "ASAプロセスは起動していますがRCON準備中です。", ProcessId = process.ProcessId };
    }
}
