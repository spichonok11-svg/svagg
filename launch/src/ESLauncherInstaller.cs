using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed class InstallerForm : Form
{
    private TextBox pathBox;
    private Label statusLabel;
    private Button installButton;
    private Button browseButton;
    private CheckBox installVersionsBox;
    private ProgressBar progressBar;
    private Label percentLabel;

    public InstallerForm()
    {
        Text = "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 ES Launcher";
        ClientSize = new Size(580, 310);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 10f);
        BackColor = Color.FromArgb(18, 24, 24);

        var title = new Label
        {
            Text = "ES Launcher Setup",
            Bounds = new Rectangle(24, 22, 500, 36),
            ForeColor = Color.White,
            BackColor = Color.Transparent,
            Font = new Font("Segoe UI", 20f, FontStyle.Bold)
        };
        Controls.Add(title);

        var hint = new Label
        {
            Text = "\u041f\u0430\u043f\u043a\u0430 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438",
            Bounds = new Rectangle(26, 76, 170, 22),
            ForeColor = Color.FromArgb(210, 230, 210),
            BackColor = Color.Transparent
        };
        Controls.Add(hint);

        pathBox = new TextBox
        {
            Bounds = new Rectangle(24, 102, 400, 30),
            Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ES Launcher")
        };
        Controls.Add(pathBox);

        browseButton = new Button
        {
            Text = "\u0412\u044b\u0431\u0440\u0430\u0442\u044c",
            Bounds = new Rectangle(436, 101, 96, 32)
        };
        browseButton.Click += Browse;
        Controls.Add(browseButton);

        installVersionsBox = new CheckBox
        {
            Text = "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c Forge \u0438 Fabric \u043f\u043e\u0441\u043b\u0435 \u0440\u0430\u0441\u043f\u0430\u043a\u043e\u0432\u043a\u0438",
            Bounds = new Rectangle(24, 146, 500, 24),
            Checked = true,
            ForeColor = Color.White,
            BackColor = BackColor
        };
        Controls.Add(installVersionsBox);

        statusLabel = new Label
        {
            Text = "",
            Bounds = new Rectangle(24, 178, 508, 24),
            ForeColor = Color.FromArgb(180, 255, 120),
            BackColor = Color.Transparent
        };
        Controls.Add(statusLabel);

        progressBar = new ProgressBar
        {
            Bounds = new Rectangle(24, 208, 430, 24),
            Minimum = 0,
            Maximum = 100,
            Value = 0
        };
        Controls.Add(progressBar);

        percentLabel = new Label
        {
            Text = "0%",
            Bounds = new Rectangle(468, 206, 80, 28),
            ForeColor = Color.White,
            BackColor = Color.Transparent,
            TextAlign = ContentAlignment.MiddleRight,
            Font = new Font("Segoe UI", 11f, FontStyle.Bold)
        };
        Controls.Add(percentLabel);

        installButton = new Button
        {
            Text = "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c",
            Bounds = new Rectangle(24, 250, 532, 36),
            BackColor = Color.FromArgb(113, 229, 28),
            ForeColor = Color.FromArgb(17, 17, 17),
            Font = new Font("Segoe UI", 11f, FontStyle.Bold)
        };
        installButton.Click += async (s, e) => await Install();
        Controls.Add(installButton);
    }

    private void Browse(object sender, EventArgs e)
    {
        using (var dialog = new FolderBrowserDialog())
        {
            dialog.Description = "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438 ES Launcher";
            dialog.SelectedPath = pathBox.Text;
            if (dialog.ShowDialog(this) == DialogResult.OK)
            {
                pathBox.Text = dialog.SelectedPath;
            }
        }
    }

    private async Task Install()
    {
        installButton.Enabled = false;
        browseButton.Enabled = false;

        string target = pathBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(target))
        {
            MessageBox.Show(this, "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u043f\u043a\u0443 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438.", "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 ES Launcher", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            installButton.Enabled = true;
            browseButton.Enabled = true;
            return;
        }

        try
        {
            SetProgress(5, "\u0420\u0430\u0441\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u043b\u0430\u0443\u043d\u0447\u0435\u0440\u0430...");
            await Task.Run(() => ExtractPackage(target, value => BeginInvoke((Action)(() => SetProgress(value, "\u0420\u0430\u0441\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u043b\u0430\u0443\u043d\u0447\u0435\u0440\u0430...")))));

            if (installVersionsBox.Checked)
            {
                SetProgress(45, "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 Forge 1.21.11...");
                await Task.Run(() => RunInstall(target, "Forge 1.21.11"));
                SetProgress(70, "Forge 1.21.11 \u0433\u043e\u0442\u043e\u0432.");

                SetProgress(72, "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 Fabric 1.21.11...");
                await Task.Run(() => RunInstall(target, "Fabric 1.21.11"));
                SetProgress(95, "Fabric 1.21.11 \u0433\u043e\u0442\u043e\u0432.");
            }

            SetProgress(100, "\u0413\u043e\u0442\u043e\u0432\u043e.");
            string exe = Path.Combine(target, "ES Launcher.exe");
            if (MessageBox.Show(this, "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c ES Launcher?", "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 ES Launcher", MessageBoxButtons.YesNo, MessageBoxIcon.Information) == DialogResult.Yes)
            {
                Process.Start(exe);
            }
            Close();
        }
        catch (Exception ex)
        {
            File.AppendAllText(Path.Combine(target, "installer-error.log"), ex + Environment.NewLine);
            MessageBox.Show(this, "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 \u043d\u0435 \u0443\u0434\u0430\u043b\u0430\u0441\u044c. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 installer-error.log.", "\u0423\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 ES Launcher", MessageBoxButtons.OK, MessageBoxIcon.Error);
            installButton.Enabled = true;
            browseButton.Enabled = true;
        }
    }

    private void SetProgress(int value, string text)
    {
        if (value < 0) value = 0;
        if (value > 100) value = 100;
        progressBar.Value = value;
        percentLabel.Text = value + "%";
        statusLabel.Text = text;
        statusLabel.Refresh();
        progressBar.Refresh();
        percentLabel.Refresh();
    }

    private static void ExtractPackage(string target, Action<int> reportProgress)
    {
        Directory.CreateDirectory(target);

        var assembly = Assembly.GetExecutingAssembly();
        string resourceName = null;
        foreach (string name in assembly.GetManifestResourceNames())
        {
            if (name.EndsWith("package.zip", StringComparison.OrdinalIgnoreCase))
            {
                resourceName = name;
                break;
            }
        }

        using (Stream stream = resourceName == null ? null : assembly.GetManifestResourceStream(resourceName))
        {
            if (stream == null) throw new InvalidOperationException("Embedded package.zip not found.");
            using (var archive = new ZipArchive(stream, ZipArchiveMode.Read))
            {
                int total = Math.Max(archive.Entries.Count, 1);
                int done = 0;
                foreach (var entry in archive.Entries)
                {
                    string path = Path.Combine(target, entry.FullName);
                    string fullTarget = Path.GetFullPath(path);
                    string fullRoot = Path.GetFullPath(target);
                    if (!fullTarget.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("Bad zip entry: " + entry.FullName);
                    }

                    if (string.IsNullOrEmpty(entry.Name))
                    {
                        Directory.CreateDirectory(fullTarget);
                        continue;
                    }

                    Directory.CreateDirectory(Path.GetDirectoryName(fullTarget));
                    entry.ExtractToFile(fullTarget, true);
                    done++;
                    int progress = 5 + (int)Math.Round(done * 35.0 / total);
                    reportProgress(progress);
                }
            }
        }
    }

    private static void RunInstall(string target, string version)
    {
        string script = Path.Combine(target, "scripts", "minecraft.ps1");
        if (!File.Exists(script)) throw new FileNotFoundException(script);

        string log = Path.Combine(target, "installer-install.log");
        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\" install -Version \"" + version + "\"",
            WorkingDirectory = target,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };

        using (var process = Process.Start(psi))
        {
            string output = process.StandardOutput.ReadToEnd();
            string error = process.StandardError.ReadToEnd();
            process.WaitForExit();
            File.AppendAllText(log, "==== " + version + " ====" + Environment.NewLine + output + Environment.NewLine + error + Environment.NewLine);
            if (process.ExitCode != 0) throw new InvalidOperationException("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c " + version + ".");
        }
    }
}

internal static class ESLauncherInstaller
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new InstallerForm());
    }
}
