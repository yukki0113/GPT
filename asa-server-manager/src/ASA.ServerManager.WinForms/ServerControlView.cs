namespace ASA.ServerManager.WinForms;

/// <summary>将来のサーバー操作を表示する最小シェルです。</summary>
public sealed class ServerControlView : UserControl
{
    /// <summary>操作画面を構築します。</summary>
    public ServerControlView()
    {
        Label status = new Label();
        status.AutoSize = true;
        status.Location = new Point(24, 24);
        status.Text = "状態: 未構成";

        Button start = new Button();
        start.Location = new Point(24, 60);
        start.Size = new Size(140, 32);
        start.Text = "起動／再起動";
        start.Enabled = false;

        Button stop = new Button();
        stop.Location = new Point(176, 60);
        stop.Size = new Size(100, 32);
        stop.Text = "停止";
        stop.Enabled = false;

        Controls.Add(status);
        Controls.Add(start);
        Controls.Add(stop);
    }
}
