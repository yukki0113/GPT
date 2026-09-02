namespace ASA.ServerManager.WinForms;

/// <summary>V3の最上位画面です。各領域は個別UserControlとして分離します。</summary>
public sealed class MainForm : Form
{
    /// <summary>メイン画面を構築します。</summary>
    public MainForm(ServerOrchestrator? serverOrchestrator = null)
    {
        Text = "ASA Server Manager V3";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(1024, 680);
        Width = 1280;
        Height = 800;

        TabControl tabs = new TabControl();
        tabs.Dock = DockStyle.Fill;
        tabs.TabPages.Add(CreateTab("サーバー操作", new ServerControlView(serverOrchestrator)));
        tabs.TabPages.Add(CreateTab("基本設定", new BasicSettingsView()));
        tabs.TabPages.Add(CreateTab("MOD", new ModsView()));
        tabs.TabPages.Add(CreateTab("ゲーム設定", new GameSettingsView()));
        tabs.TabPages.Add(CreateTab("ログ・診断", new DiagnosticsView()));
        Controls.Add(tabs);
    }

    private static TabPage CreateTab(string title, Control content)
    {
        TabPage page = new TabPage(title);
        content.Dock = DockStyle.Fill;
        page.Controls.Add(content);
        return page;
    }
}
