using ASA.ServerManager.Application;

namespace ASA.ServerManager.WinForms;

/// <summary>V3の5つの運用領域を統合する最上位画面です。</summary>
public sealed class MainForm : Form
{
    /// <summary>Composition Rootで構築済みの各Application serviceを画面へ配布します。</summary>
    public MainForm(
        ServerOrchestrator serverOrchestrator,
        BasicSettingsService basicSettingsService,
        ModSettingsService modSettingsService,
        GameSettingsService gameSettingsService,
        DiagnosticsService diagnosticsService,
        ManualBackupCoordinator backupCoordinator,
        IApplicationStatusStore statusStore)
    {
        Text = "ASA Server Manager V3";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(1100, 700);
        ClientSize = new Size(1280, 800);
        AutoScaleMode = AutoScaleMode.Dpi;

        TabControl tabs = new TabControl { Dock = DockStyle.Fill };
        tabs.TabPages.Add(CreateTab("サーバー操作", new ServerControlView(serverOrchestrator, statusStore)));
        tabs.TabPages.Add(CreateTab("基本設定", new BasicSettingsView(basicSettingsService, serverOrchestrator, statusStore)));
        tabs.TabPages.Add(CreateTab("MOD", new ModsView(modSettingsService, statusStore)));
        tabs.TabPages.Add(CreateTab("ゲーム設定", new GameSettingsView(gameSettingsService, statusStore)));
        tabs.TabPages.Add(CreateTab("ログ・診断", new DiagnosticsView(diagnosticsService, backupCoordinator, statusStore)));
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
