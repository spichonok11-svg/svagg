using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
using System.Windows.Forms;

internal sealed class LauncherForm : Form
{
    private readonly string root;
    private readonly string gameRoot;
    private readonly string scriptPath;
    private readonly string settingsPath;
    private readonly string logPath;
    private readonly Image background;

    private string selectedVersion = "Forge 1.21.11";
    private Panel forgeCard;
    private Panel fabricCard;
    private TextBox nickBox;
    private Label warningLabel;
    private Label statusLabel;
    private Button playButton;
    private Panel settingsPanel;
    private TrackBar ramSlider;
    private Label ramValueLabel;

    public LauncherForm()
    {
        root = AppDomain.CurrentDomain.BaseDirectory;
        gameRoot = Path.Combine(root, "game", ".minecraft");
        scriptPath = Path.Combine(root, "scripts", "minecraft.ps1");
        settingsPath = Path.Combine(root, "launcher-settings.txt");
        logPath = Path.Combine(root, "launcher.log");

        string bgPath = Path.Combine(root, "photos", "background.png");
        if (File.Exists(bgPath))
        {
            using (var stream = new FileStream(bgPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            {
                background = Image.FromStream(stream);
            }
        }

        Text = "ES Launcher";
        ClientSize = new Size(1482, 660);
        MinimumSize = new Size(1180, 560);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        DoubleBuffered = true;
        Font = new Font("Segoe UI", 10f);
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

        BuildUi();
        LoadSettings();
        UpdateRamLabel();
        SelectVersion("Forge 1.21.11");
        ValidateNickname();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        e.Graphics.SmoothingMode = SmoothingMode.HighQuality;

        if (background != null)
        {
            Rectangle target = GetCoverRectangle(background.Size, ClientSize);
            e.Graphics.DrawImage(background, target);
        }
        else
        {
            using (var brush = new LinearGradientBrush(ClientRectangle, Color.FromArgb(36, 11, 69), Color.FromArgb(6, 41, 23), 45f))
            {
                e.Graphics.FillRectangle(brush, ClientRectangle);
            }
        }

        using (var overlay = new SolidBrush(Color.FromArgb(38, 0, 0, 0)))
        {
            e.Graphics.FillRectangle(overlay, ClientRectangle);
        }
    }

    private static Rectangle GetCoverRectangle(Size imageSize, Size areaSize)
    {
        double imageRatio = (double)imageSize.Width / imageSize.Height;
        double areaRatio = (double)areaSize.Width / areaSize.Height;
        int width;
        int height;

        if (imageRatio > areaRatio)
        {
            height = areaSize.Height;
            width = (int)Math.Ceiling(height * imageRatio);
        }
        else
        {
            width = areaSize.Width;
            height = (int)Math.Ceiling(width / imageRatio);
        }

        return new Rectangle((areaSize.Width - width) / 2, (areaSize.Height - height) / 2, width, height);
    }

    private void BuildUi()
    {
        var logo = MakeButton("ES", new Rectangle(28, 24, 68, 68), Color.FromArgb(22, 23, 27), Color.FromArgb(137, 255, 33), 24f);
        logo.Click += (s, e) => SelectVersion("Forge 1.21.11");
        Controls.Add(logo);

        var title = MakeLabel("ES Launcher", new Rectangle(120, 42, 320, 42), 30f, FontStyle.Bold, Color.White);
        Controls.Add(title);

        var nickPanel = new Panel { Bounds = new Rectangle(ClientSize.Width - 402, 38, 256, 56), BackColor = Color.FromArgb(35, 35, 35) };
        nickPanel.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        var avatar = new Panel { Bounds = new Rectangle(11, 7, 42, 42), BackColor = Color.FromArgb(35, 35, 35) };
        avatar.Paint += DrawSteveAvatar;
        nickBox = new TextBox
        {
            Bounds = new Rectangle(64, 12, 175, 34),
            Text = "player",
            BorderStyle = BorderStyle.None,
            BackColor = Color.FromArgb(35, 35, 35),
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 18f)
        };
        nickBox.TextChanged += (s, e) => ValidateNickname();
        nickPanel.Controls.Add(avatar);
        nickPanel.Controls.Add(nickBox);
        Controls.Add(nickPanel);

        warningLabel = MakeLabel("\u0421\u043c\u0435\u043d\u0438\u0442\u0435 \u0438\u043c\u044f", new Rectangle(ClientSize.Width - 350, 98, 160, 28), 10f, FontStyle.Bold, Color.FromArgb(255, 74, 74));
        warningLabel.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        warningLabel.BackColor = Color.Transparent;
        warningLabel.TextAlign = ContentAlignment.MiddleCenter;
        Controls.Add(warningLabel);

        var gear = new Panel
        {
            Bounds = new Rectangle(ClientSize.Width - 84, 39, 52, 52),
            BackColor = Color.FromArgb(18, 24, 24),
            Cursor = Cursors.Hand
        };
        gear.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        gear.Paint += DrawGearIcon;
        gear.Click += (s, e) => settingsPanel.Visible = !settingsPanel.Visible;
        Controls.Add(gear);

        var versions = MakeLabel("VERSIONS", new Rectangle(42, 136, 180, 24), 11f, FontStyle.Bold, Color.White);
        Controls.Add(versions);

        forgeCard = MakeVersionCard("Forge", "Minecraft 1.21.11", new Rectangle(42, 192, 360, 116));
        forgeCard.Click += (s, e) => SelectVersion("Forge 1.21.11");
        Controls.Add(forgeCard);

        fabricCard = MakeVersionCard("Fabric", "Minecraft 1.21.11", new Rectangle(42, 324, 360, 116));
        fabricCard.Click += (s, e) => SelectVersion("Fabric 1.21.11");
        Controls.Add(fabricCard);

        statusLabel = MakeLabel("", new Rectangle(46, 474, 360, 72), 10f, FontStyle.Regular, Color.White);
        statusLabel.BackColor = Color.Transparent;
        Controls.Add(statusLabel);

        playButton = MakeButton("DOWNLOAD", new Rectangle(ClientSize.Width - 292, ClientSize.Height - 94, 250, 66), Color.FromArgb(255, 182, 41), Color.FromArgb(17, 17, 17), 24f);
        playButton.Anchor = AnchorStyles.Right | AnchorStyles.Bottom;
        playButton.Click += PlayOrDownload;
        Controls.Add(playButton);

        settingsPanel = new Panel
        {
            Bounds = new Rectangle(ClientSize.Width - 364, 106, 330, 230),
            Anchor = AnchorStyles.Top | AnchorStyles.Right,
            BackColor = Color.FromArgb(17, 18, 21),
            Visible = false
        };
        settingsPanel.Controls.Add(MakeLabel("SETTINGS", new Rectangle(16, 12, 250, 26), 12f, FontStyle.Bold, Color.White));
        settingsPanel.Controls.Add(MakeLabel("RAM", new Rectangle(16, 54, 70, 22), 10f, FontStyle.Bold, Color.FromArgb(221, 228, 221)));
        ramValueLabel = MakeLabel("4096 MB", new Rectangle(120, 54, 190, 22), 10f, FontStyle.Bold, Color.White);
        ramValueLabel.TextAlign = ContentAlignment.MiddleRight;
        settingsPanel.Controls.Add(ramValueLabel);
        ramSlider = new TrackBar
        {
            Bounds = new Rectangle(12, 80, 306, 45),
            Minimum = 1024,
            Maximum = 16384,
            SmallChange = 512,
            LargeChange = 1024,
            TickFrequency = 2048,
            Value = 4096,
            BackColor = Color.FromArgb(17, 18, 21)
        };
        ramSlider.ValueChanged += (s, e) => UpdateRamLabel();
        settingsPanel.Controls.Add(ramSlider);
        var save = MakeButton("SAVE", new Rectangle(16, 142, 298, 34), Color.FromArgb(113, 229, 28), Color.FromArgb(17, 17, 17), 11f);
        save.Click += (s, e) => SaveSettings(GetRamMb());
        settingsPanel.Controls.Add(save);
        var folder = MakeButton("GAME FOLDER", new Rectangle(16, 184, 298, 34), Color.FromArgb(39, 45, 49), Color.White, 11f);
        folder.Click += (s, e) =>
        {
            Directory.CreateDirectory(Path.Combine(gameRoot, "mods"));
            Process.Start("explorer.exe", "\"" + gameRoot + "\"");
        };
        settingsPanel.Controls.Add(folder);
        Controls.Add(settingsPanel);
    }

    private void DrawSteveAvatar(object sender, PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.None;
        int s = 6;
        Color skin = Color.FromArgb(196, 132, 88);
        Color hair = Color.FromArgb(61, 38, 24);
        Color eye = Color.FromArgb(36, 74, 150);
        Color shirt = Color.FromArgb(62, 150, 148);
        using (var b = new SolidBrush(skin)) e.Graphics.FillRectangle(b, 3, 3, 36, 36);
        using (var b = new SolidBrush(hair))
        {
            e.Graphics.FillRectangle(b, 3, 3, 36, s * 2);
            e.Graphics.FillRectangle(b, 3, 3, s, 24);
            e.Graphics.FillRectangle(b, 33, 3, s, 18);
        }
        using (var b = new SolidBrush(eye))
        {
            e.Graphics.FillRectangle(b, 12, 18, 6, 6);
            e.Graphics.FillRectangle(b, 27, 18, 6, 6);
        }
        using (var b = new SolidBrush(Color.FromArgb(105, 62, 42))) e.Graphics.FillRectangle(b, 18, 27, 9, 3);
        using (var b = new SolidBrush(shirt)) e.Graphics.FillRectangle(b, 3, 36, 36, 6);
    }

    private void DrawGearIcon(object sender, PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (var pen = new Pen(Color.White, 4f))
        {
            var center = new Point(26, 26);
            for (int i = 0; i < 8; i++)
            {
                double angle = i * Math.PI / 4.0;
                int x1 = center.X + (int)(Math.Cos(angle) * 15);
                int y1 = center.Y + (int)(Math.Sin(angle) * 15);
                int x2 = center.X + (int)(Math.Cos(angle) * 21);
                int y2 = center.Y + (int)(Math.Sin(angle) * 21);
                e.Graphics.DrawLine(pen, x1, y1, x2, y2);
            }
            e.Graphics.DrawEllipse(pen, 13, 13, 26, 26);
            e.Graphics.DrawEllipse(pen, 21, 21, 10, 10);
        }
    }

    private static Label MakeLabel(string text, Rectangle bounds, float size, FontStyle style, Color color)
    {
        return new Label
        {
            Text = text,
            Bounds = bounds,
            ForeColor = color,
            BackColor = Color.Transparent,
            Font = new Font("Segoe UI", size, style),
            AutoSize = false
        };
    }

    private static Button MakeButton(string text, Rectangle bounds, Color back, Color fore, float size)
    {
        return new Button
        {
            Text = text,
            Bounds = bounds,
            BackColor = back,
            ForeColor = fore,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", size, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
    }

    private Panel MakeVersionCard(string name, string sub, Rectangle bounds)
    {
        var panel = new Panel { Bounds = bounds, BackColor = Color.FromArgb(20, 23, 28), Cursor = Cursors.Hand };
        panel.Paint += (s, e) =>
        {
            bool active = panel == (selectedVersion.StartsWith("Forge") ? forgeCard : fabricCard);
            Color border = active ? Color.FromArgb(128, 255, 49) : Color.FromArgb(85, 95, 96);
            using (var pen = new Pen(border, active ? 2f : 1f))
            {
                e.Graphics.DrawRectangle(pen, 0, 0, panel.Width - 1, panel.Height - 1);
            }
        };
        var title = MakeLabel(name, new Rectangle(20, 24, 260, 38), 21f, FontStyle.Bold, Color.White);
        var subtitle = MakeLabel(sub, new Rectangle(20, 72, 260, 28), 12f, FontStyle.Regular, Color.FromArgb(200, 255, 190));
        title.Click += (s, e) => SelectVersion(name + " 1.21.11");
        subtitle.Click += (s, e) => SelectVersion(name + " 1.21.11");
        panel.Controls.Add(title);
        panel.Controls.Add(subtitle);
        return panel;
    }

    private void SelectVersion(string version)
    {
        selectedVersion = version;
        if (forgeCard != null) forgeCard.Invalidate();
        if (fabricCard != null) fabricCard.Invalidate();
        statusLabel.Text = "";
        UpdatePlayButton();
    }

    private void UpdatePlayButton()
    {
        bool installed = IsVersionInstalled(selectedVersion);
        playButton.Text = installed ? "PLAY" : "DOWNLOAD";
        playButton.BackColor = installed ? Color.FromArgb(113, 229, 28) : Color.FromArgb(255, 182, 41);
    }

    private bool IsVersionInstalled(string version)
    {
        string versionsDir = Path.Combine(gameRoot, "versions");
        if (!Directory.Exists(versionsDir)) return false;
        string[] dirs = Directory.GetDirectories(versionsDir).Select(Path.GetFileName).ToArray();
        if (version.StartsWith("Fabric"))
            return dirs.Any(x => x.StartsWith("fabric-loader-") && x.EndsWith("-1.21.11"));
        return dirs.Any(x => x.Equals("Forge-1.21.11", StringComparison.OrdinalIgnoreCase) || x.Equals("Forge 1.21.11", StringComparison.OrdinalIgnoreCase) || x.ToLowerInvariant().Contains("forge") && x.Contains("1.21.11"));
    }

    private void ValidateNickname()
    {
        string name = nickBox.Text.Trim();
        warningLabel.Visible = string.IsNullOrWhiteSpace(name) || name.Equals("player", StringComparison.OrdinalIgnoreCase);
    }

    private int GetRamMb()
    {
        int value;
        value = ramSlider == null ? 4096 : ramSlider.Value;
        if (value < 1024) value = 1024;
        if (value > 16384) value = 16384;
        return value;
    }

    private void UpdateRamLabel()
    {
        int mb = GetRamMb();
        ramValueLabel.Text = mb >= 1024 ? (mb / 1024.0).ToString("0.#") + " GB (" + mb + " MB)" : mb + " MB";
    }

    private void LoadSettings()
    {
        if (File.Exists(settingsPath))
        {
            string text = File.ReadAllText(settingsPath).Trim();
            int value;
            if (int.TryParse(text, out value))
            {
                if (value < 1024) value = 1024;
                if (value > 16384) value = 16384;
                ramSlider.Value = value;
                UpdateRamLabel();
            }
        }
    }

    private void SaveSettings(int ramMb)
    {
        File.WriteAllText(settingsPath, ramMb.ToString());
        ramSlider.Value = ramMb;
        UpdateRamLabel();
        statusLabel.Text = "RAM saved: " + ramMb + " MB";
    }

    private void PlayOrDownload(object sender, EventArgs e)
    {
        SaveSettings(GetRamMb());

        if (!File.Exists(scriptPath))
        {
            MessageBox.Show("scripts\\minecraft.ps1 not found.", "ES Launcher", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        if (!IsVersionInstalled(selectedVersion))
        {
            statusLabel.Text = "Downloading " + selectedVersion + "...";
            Enabled = false;
            Application.DoEvents();
            int exit = RunPowerShellHidden("-File \"" + scriptPath + "\" install -Version \"" + selectedVersion + "\" -RamMb " + GetRamMb(), true);
            Enabled = true;
            UpdatePlayButton();
            statusLabel.Text = IsVersionInstalled(selectedVersion)
                ? selectedVersion + " downloaded. Press PLAY."
                : "Download failed. Check launcher.log.";
            if (exit != 0 && !IsVersionInstalled(selectedVersion))
            {
                MessageBox.Show("Download failed. Check launcher.log.", "ES Launcher", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            return;
        }

        if (warningLabel.Visible)
        {
            statusLabel.Text = "Change nickname before launch.";
            return;
        }

        string nick = nickBox.Text.Trim();
        statusLabel.Text = "Launching " + selectedVersion + " as " + nick + "...";
        RunPowerShellHidden("-File \"" + scriptPath + "\" launch -Version \"" + selectedVersion + "\" -Nickname \"" + nick + "\" -RamMb " + GetRamMb(), false);
    }

    private int RunPowerShellHidden(string arguments, bool wait)
    {
        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = "-NoProfile -ExecutionPolicy Bypass " + arguments,
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };

        try
        {
            using (var process = Process.Start(psi))
            {
                if (!wait) return 0;
                string output = process.StandardOutput.ReadToEnd();
                string error = process.StandardError.ReadToEnd();
                process.WaitForExit();
                File.AppendAllText(logPath, "[" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "] powershell " + arguments + Environment.NewLine + output + Environment.NewLine + error + Environment.NewLine + "ExitCode=" + process.ExitCode + Environment.NewLine + Environment.NewLine);
                return process.ExitCode;
            }
        }
        catch (Exception ex)
        {
            File.AppendAllText(logPath, "[" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "] " + ex + Environment.NewLine);
            return 1;
        }
    }
}

internal static class ESLauncherWrapper
{
    [STAThread]
    private static void Main()
    {
        try
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
        catch (Exception ex)
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string path = Path.Combine(root, "launcher-crash.log");
            File.AppendAllText(path, "[" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "] " + ex + Environment.NewLine);
            MessageBox.Show("ES Launcher crashed. Check launcher-crash.log.", "ES Launcher", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}


