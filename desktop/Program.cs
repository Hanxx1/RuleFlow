using System.Diagnostics;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Zhishi.RuleFlow.Desktop;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

internal sealed class MainForm : Form
{
    private const string AppHost = "app.zhishi.local";
    private readonly WebView2 webView = new() { Dock = DockStyle.Fill };

    public MainForm()
    {
        Text = "知事 RuleFlow";
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(430, 860);
        MinimumSize = new Size(390, 700);
        Controls.Add(webView);
        Shown += InitializeWebViewAsync;
    }

    private async void InitializeWebViewAsync(object? sender, EventArgs e)
    {
        try
        {
            var webRoot = Path.Combine(AppContext.BaseDirectory, "wwwroot");
            var indexPath = Path.Combine(webRoot, "index.html");
            if (!File.Exists(indexPath))
            {
                throw new FileNotFoundException("应用资源不完整，未找到 index.html。", indexPath);
            }

            var userDataFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "ZhishiRuleFlow",
                "WebView2");
            Directory.CreateDirectory(userDataFolder);

            var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: userDataFolder);
            await webView.EnsureCoreWebView2Async(environment);
            webView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                AppHost,
                webRoot,
                CoreWebView2HostResourceAccessKind.Allow);
            webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
            webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
            webView.CoreWebView2.NavigationStarting += HandleNavigationStarting;
            webView.CoreWebView2.NewWindowRequested += HandleNewWindowRequested;
            await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync("""
                (() => {
                  if (location.hostname !== 'app.zhishi.local' || location.pathname !== '/index.html') return;
                  const params = new URLSearchParams(location.search);
                  const route = params.get('__route') || '/';
                  history.replaceState(null, '', route);
                })();
                """);
            webView.Source = new Uri($"https://{AppHost}/index.html");
        }
        catch (Exception error)
        {
            MessageBox.Show(
                $"知事 RuleFlow 无法启动。\n\n{error.Message}\n\n请确认系统已安装 Microsoft Edge WebView2 Runtime。",
                "启动失败",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            Close();
        }
    }

    private void HandleNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs e)
    {
        if (!Uri.TryCreate(e.Uri, UriKind.Absolute, out var uri) ||
            !uri.Host.Equals(AppHost, StringComparison.OrdinalIgnoreCase) ||
            Path.HasExtension(uri.AbsolutePath) ||
            uri.AbsolutePath == "/")
        {
            return;
        }

        e.Cancel = true;
        var route = Uri.EscapeDataString(uri.PathAndQuery + uri.Fragment);
        webView.CoreWebView2.Navigate($"https://{AppHost}/index.html?__route={route}");
    }

    private static void HandleNewWindowRequested(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        if (!Uri.TryCreate(e.Uri, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
        {
            return;
        }

        e.Handled = true;
        Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true });
    }
}
