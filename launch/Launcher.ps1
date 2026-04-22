param(
    [switch]$NoExitOnLaunch
)

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$script:Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:Assets = Join-Path $script:Root 'photos'
$script:LaunchScript = Join-Path $script:Root 'scripts\minecraft.ps1'
$script:GameRoot = Join-Path $script:Root 'game\.minecraft'
$script:SettingsPath = Join-Path $script:Root 'launcher-settings.json'
$script:LogPath = Join-Path $script:Root 'launcher.log'
$script:SelectedVersion = 'Forge 1.21.11'

[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="ES Launcher"
        Width="1482"
        Height="660"
        MinWidth="1180"
        MinHeight="560"
        WindowStartupLocation="CenterScreen"
        Background="#07110F"
        FontFamily="Segoe UI"
        ResizeMode="NoResize">
  <Grid ClipToBounds="True">
    <Grid.Background>
      <LinearGradientBrush StartPoint="0,0" EndPoint="1,1">
        <GradientStop Color="#240B45" Offset="0"/>
        <GradientStop Color="#062917" Offset="1"/>
      </LinearGradientBrush>
    </Grid.Background>

    <Image x:Name="BackgroundImage" Stretch="UniformToFill" Opacity="1"/>
    <Rectangle Fill="#26000000"/>

    <Grid>
      <Grid Margin="28,24,28,28" VerticalAlignment="Top" Height="82">
        <Grid.ColumnDefinitions>
          <ColumnDefinition Width="Auto"/>
          <ColumnDefinition Width="*"/>
          <ColumnDefinition Width="Auto"/>
          <ColumnDefinition Width="58"/>
        </Grid.ColumnDefinitions>

        <Button x:Name="HomeButton"
                Width="68"
                Height="68"
                Cursor="Hand"
                ToolTip="Home"
                Background="#E316171B"
                BorderBrush="#1B1B1F"
                Foreground="#89FF21"
                FontSize="24"
                FontWeight="Black"
                Content="ES">
          <Button.Resources>
            <Style TargetType="Border">
              <Setter Property="CornerRadius" Value="8"/>
            </Style>
          </Button.Resources>
        </Button>

        <TextBlock Grid.Column="1"
                   Text="ES Launcher"
                   VerticalAlignment="Center"
                   Margin="24,0,0,0"
                   Foreground="#FFFFFF"
                   FontSize="30"
                   FontWeight="Bold"/>

        <StackPanel Grid.Column="2" Width="256" VerticalAlignment="Center">
          <Border Height="56"
                  Background="#E3232323"
                  CornerRadius="28">
            <Grid>
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="64"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <Ellipse Width="42" Height="42" Fill="#D8D8D8" VerticalAlignment="Center" HorizontalAlignment="Center"/>
              <TextBox x:Name="NicknameBox"
                       Grid.Column="1"
                       Text="player"
                       BorderThickness="0"
                       Background="Transparent"
                       Foreground="#F7F7F7"
                       CaretBrush="#90FF36"
                       SelectionBrush="#803BEF4C"
                       FontSize="25"
                       VerticalContentAlignment="Center"
                       Padding="4,0,18,3"/>
            </Grid>
          </Border>
          <Border x:Name="NameWarning"
                  Visibility="Collapsed"
                  HorizontalAlignment="Center"
                  Margin="0,6,0,0"
                  Padding="12,4"
                  Background="#D61A0909"
                  BorderBrush="#FF3E3E"
                  BorderThickness="1"
                  CornerRadius="6">
            <TextBlock x:Name="NameWarningText"
                       Text="&#x0421;&#x043C;&#x0435;&#x043D;&#x0438;&#x0442;&#x0435; &#x0438;&#x043C;&#x044F;"
                       Foreground="#FF4A4A"
                       FontSize="14"
                       FontWeight="Bold"/>
          </Border>
        </StackPanel>

        <Button x:Name="SettingsButton"
                Grid.Column="3"
                Width="52"
                Height="52"
                Margin="12,0,0,0"
                VerticalAlignment="Center"
                Cursor="Hand"
                ToolTip="Open launcher folder"
                Background="Transparent"
                BorderThickness="0"
                Foreground="White"
                FontSize="34"
                Content="&#x2699;"/>
      </Grid>

      <Border x:Name="SettingsPanel"
              Visibility="Collapsed"
              Width="330"
              HorizontalAlignment="Right"
              VerticalAlignment="Top"
              Margin="0,106,34,0"
              Background="#E5111215"
              BorderBrush="#6F9FFF31"
              BorderThickness="1"
              CornerRadius="8"
              Padding="16">
        <StackPanel>
          <TextBlock Text="SETTINGS"
                     Foreground="#FFFFFF"
                     FontSize="16"
                     FontWeight="Bold"
                     Margin="0,0,0,12"/>
          <TextBlock Text="RAM, MB"
                     Foreground="#DDE4DD"
                     FontSize="13"
                     FontWeight="Bold"
                     Margin="0,0,0,6"/>
          <TextBox x:Name="RamBox"
                   Height="38"
                   Text="4096"
                   Background="#20242A"
                   Foreground="#FFFFFF"
                   BorderBrush="#56605A"
                   CaretBrush="#90FF36"
                   SelectionBrush="#803BEF4C"
                   FontSize="18"
                   Padding="10,5"/>
          <Button x:Name="SaveSettingsButton"
                  Height="40"
                  Margin="0,12,0,0"
                  Cursor="Hand"
                  Background="#71E51C"
                  BorderBrush="#A5FF45"
                  Foreground="#111111"
                  FontSize="16"
                  FontWeight="Bold"
                  Content="SAVE"/>
          <Button x:Name="OpenGameFolderButton"
                  Height="40"
                  Margin="0,10,0,0"
                  Cursor="Hand"
                  Background="#272D31"
                  BorderBrush="#6C7479"
                  Foreground="#FFFFFF"
                  FontSize="16"
                  FontWeight="Bold"
                  Content="GAME FOLDER"/>
        </StackPanel>
      </Border>

      <Grid Margin="42,136,42,36">
        <Grid.ColumnDefinitions>
          <ColumnDefinition Width="360"/>
          <ColumnDefinition Width="*"/>
        </Grid.ColumnDefinitions>

        <StackPanel Grid.Column="0" VerticalAlignment="Top">
          <TextBlock Text="VERSIONS"
                     Foreground="#EDEAF1"
                     FontSize="15"
                     FontWeight="Bold"
                     Margin="0,0,0,12"/>

          <Border x:Name="ForgeCard"
                  Height="116"
                  CornerRadius="8"
                  BorderThickness="2"
                  BorderBrush="#9FFF31"
                  Background="#D7191D21"
                  Margin="0,0,0,16"
                  Cursor="Hand">
            <Grid Margin="18">
              <Grid.RowDefinitions>
                <RowDefinition Height="*"/>
                <RowDefinition Height="Auto"/>
              </Grid.RowDefinitions>
              <TextBlock Text="Forge"
                         Foreground="#FFFFFF"
                         FontSize="30"
                         FontWeight="Bold"/>
              <TextBlock Grid.Row="1"
                         Text="Minecraft 1.21.11"
                         Foreground="#BDEFB1"
                         FontSize="17"/>
            </Grid>
          </Border>

          <Border x:Name="FabricCard"
                  Height="116"
                  CornerRadius="8"
                  BorderThickness="2"
                  BorderBrush="#55FFFFFF"
                  Background="#B014171C"
                  Margin="0,0,0,16"
                  Cursor="Hand">
            <Grid Margin="18">
              <Grid.RowDefinitions>
                <RowDefinition Height="*"/>
                <RowDefinition Height="Auto"/>
              </Grid.RowDefinitions>
              <TextBlock Text="Fabric"
                         Foreground="#FFFFFF"
                         FontSize="30"
                         FontWeight="Bold"/>
              <TextBlock Grid.Row="1"
                         Text="Minecraft 1.21.11"
                         Foreground="#C8C8D0"
                         FontSize="17"/>
            </Grid>
          </Border>

          <TextBlock x:Name="StatusText"
                     Text=""
                     Foreground="#DCDCE4"
                     FontSize="14"
                     TextWrapping="Wrap"
                     Margin="4,16,0,0"/>
        </StackPanel>

        <Grid Grid.Column="1">
          <Button x:Name="PlayButton"
                  Width="208"
                  Height="66"
                  HorizontalAlignment="Right"
                  VerticalAlignment="Bottom"
                  Cursor="Hand"
                  Background="#71E51C"
                  BorderBrush="#A5FF45"
                  Foreground="#111111"
                  FontSize="28"
                  FontWeight="Black"
                  Content="PLAY">
            <Button.Resources>
              <Style TargetType="Border">
                <Setter Property="CornerRadius" Value="8"/>
              </Style>
            </Button.Resources>
          </Button>
        </Grid>
      </Grid>
    </Grid>
  </Grid>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)

function Find-Control {
    param([string]$Name)
    $window.FindName($Name)
}

$backgroundImage = Find-Control 'BackgroundImage'
$forgeCard = Find-Control 'ForgeCard'
$fabricCard = Find-Control 'FabricCard'
$nicknameBox = Find-Control 'NicknameBox'
$nameWarning = Find-Control 'NameWarning'
$nameWarningText = Find-Control 'NameWarningText'
$statusText = Find-Control 'StatusText'
$playButton = Find-Control 'PlayButton'
$settingsButton = Find-Control 'SettingsButton'
$homeButton = Find-Control 'HomeButton'
$settingsPanel = Find-Control 'SettingsPanel'
$ramBox = Find-Control 'RamBox'
$saveSettingsButton = Find-Control 'SaveSettingsButton'
$openGameFolderButton = Find-Control 'OpenGameFolderButton'
$changeNameText = [System.Net.WebUtility]::HtmlDecode('&#x0421;&#x043C;&#x0435;&#x043D;&#x0438;&#x0442;&#x0435; &#x0438;&#x043C;&#x044F;')

function Get-LauncherSettings {
    $settings = [ordered]@{ ramMb = 4096 }
    if (Test-Path -LiteralPath $script:SettingsPath) {
        try {
            $loaded = Get-Content -LiteralPath $script:SettingsPath -Raw | ConvertFrom-Json
            if ($loaded.ramMb) {
                $settings.ramMb = [int]$loaded.ramMb
            }
        } catch {
        }
    }
    return [pscustomobject]$settings
}

function Save-LauncherSettings {
    param([int]$RamMb)

    if ($RamMb -lt 1024) {
        $RamMb = 1024
    }
    if ($RamMb -gt 32768) {
        $RamMb = 32768
    }

    [pscustomobject]@{ ramMb = $RamMb } |
        ConvertTo-Json |
        Set-Content -LiteralPath $script:SettingsPath -Encoding UTF8
    $ramBox.Text = [string]$RamMb
    $statusText.Text = "RAM saved: $RamMb MB"
}

function Get-RamMb {
    $value = 4096
    if ([int]::TryParse($ramBox.Text.Trim(), [ref]$value)) {
        if ($value -lt 1024) {
            return 1024
        }
        if ($value -gt 32768) {
            return 32768
        }
        return $value
    }
    return 4096
}

function Start-HiddenPowerShell {
    param(
        [string]$Arguments,
        [switch]$Wait
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = 'powershell.exe'
    $startInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass $Arguments"
    $startInfo.WorkingDirectory = $script:Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()

    if ($Wait) {
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $log = @(
            "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] powershell $Arguments",
            $stdout,
            $stderr,
            "ExitCode=$($process.ExitCode)",
            ''
        ) -join [Environment]::NewLine
        Add-Content -LiteralPath $script:LogPath -Value $log -Encoding UTF8
        return $process.ExitCode
    }

    return 0
}

function Set-ImageIfExists {
    param(
        [Parameter(Mandatory=$true)] $ImageControl,
        [Parameter(Mandatory=$true)] [string]$Path
    )

    if (Test-Path -LiteralPath $Path) {
        $bitmap = New-Object System.Windows.Media.Imaging.BitmapImage
        $bitmap.BeginInit()
        $bitmap.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
        $bitmap.UriSource = New-Object System.Uri($Path, [System.UriKind]::Absolute)
        $bitmap.EndInit()
        $ImageControl.Source = $bitmap
    }
}

function Set-SelectedVersion {
    param([string]$Version)

    $script:SelectedVersion = $Version
    if ($Version -like 'Forge*') {
        $forgeCard.BorderBrush = '#9FFF31'
        $forgeCard.Background = '#D7191D21'
        $fabricCard.BorderBrush = '#55FFFFFF'
        $fabricCard.Background = '#B014171C'
    } else {
        $forgeCard.BorderBrush = '#55FFFFFF'
        $forgeCard.Background = '#B014171C'
        $fabricCard.BorderBrush = '#9FFF31'
        $fabricCard.Background = '#D7191D21'
    }
    $statusText.Text = "Selected: $Version"
    Update-PlayButton
}

function Test-VersionInstalled {
    param([string]$Version)

    $versionsDir = Join-Path $script:GameRoot 'versions'
    if (-not (Test-Path -LiteralPath $versionsDir)) {
        return $false
    }

    if ($Version -like 'Fabric*') {
        $fabric = Get-ChildItem -LiteralPath $versionsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'fabric-loader-*-1.21.11' -or $_.Name -like 'fabric-loader-*-minecraft-1.21.11' } |
            Select-Object -First 1
        return [bool]$fabric
    }

    if (Test-Path -LiteralPath (Join-Path $versionsDir 'Forge 1.21.11')) {
        return $true
    }

    $forge = Get-ChildItem -LiteralPath $versionsDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*forge*1.21.11*' -or $_.Name -like '*1.21.11*forge*' } |
        Select-Object -First 1
    return [bool]$forge
}

function Update-PlayButton {
    if (Test-VersionInstalled $script:SelectedVersion) {
        $playButton.Content = 'PLAY'
        $playButton.Background = '#71E51C'
    } else {
        $playButton.Content = 'DOWNLOAD'
        $playButton.Background = '#FFB629'
    }
}

function Test-Nickname {
    $name = $nicknameBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($name) -or $name.ToLowerInvariant() -eq 'player') {
        $nameWarningText.Text = $changeNameText
        $nameWarning.Visibility = 'Visible'
        return $false
    }

    if ($name -notmatch '^[A-Za-z0-9_]{3,16}$') {
        $nameWarningText.Text = 'Use 3-16 letters, numbers, underscore'
        $nameWarning.Visibility = 'Visible'
        return $false
    }

    $nameWarningText.Text = $changeNameText
    $nameWarning.Visibility = 'Collapsed'
    return $true
}

Set-ImageIfExists -ImageControl $backgroundImage -Path (Join-Path $script:Assets 'background.png')
$settings = Get-LauncherSettings
$ramBox.Text = [string]$settings.ramMb
Set-SelectedVersion 'Forge 1.21.11'
[void](Test-Nickname)

$forgeCard.Add_MouseLeftButtonUp({ Set-SelectedVersion 'Forge 1.21.11' })
$fabricCard.Add_MouseLeftButtonUp({ Set-SelectedVersion 'Fabric 1.21.11' })
$homeButton.Add_Click({ Set-SelectedVersion 'Forge 1.21.11' })
$settingsButton.Add_Click({
    if ($settingsPanel.Visibility -eq 'Visible') {
        $settingsPanel.Visibility = 'Collapsed'
    } else {
        $settingsPanel.Visibility = 'Visible'
    }
})
$saveSettingsButton.Add_Click({
    Save-LauncherSettings -RamMb (Get-RamMb)
})
$openGameFolderButton.Add_Click({
    New-Item -ItemType Directory -Path $script:GameRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $script:GameRoot 'mods') -Force | Out-Null
    Start-Process explorer.exe -ArgumentList "`"$script:GameRoot`""
})
$nicknameBox.Add_TextChanged({ [void](Test-Nickname) })

$playButton.Add_Click({
    $ramMb = Get-RamMb
    Save-LauncherSettings -RamMb $ramMb

    if (-not (Test-VersionInstalled $script:SelectedVersion)) {
        $statusText.Text = "Downloading $script:SelectedVersion..."
        $installArgs = "-File `"$script:LaunchScript`" install -Version `"$script:SelectedVersion`" -RamMb $ramMb"
        [void](Start-HiddenPowerShell -Arguments $installArgs -Wait)
        Update-PlayButton
        if (Test-VersionInstalled $script:SelectedVersion) {
            $statusText.Text = "$script:SelectedVersion downloaded. Press Play."
        } else {
            $statusText.Text = "Download did not finish. Check launcher.log."
        }
        return
    }

    if (-not (Test-Nickname)) {
        $statusText.Text = 'Enter your own Minecraft nickname before launch.'
        return
    }

    if (-not (Test-Path -LiteralPath $script:LaunchScript)) {
        $statusText.Text = "Launch script not found: $script:LaunchScript"
        return
    }

    $nickname = $nicknameBox.Text.Trim()
    $statusText.Text = "Launching $script:SelectedVersion as $nickname..."

    $args = "-File `"$script:LaunchScript`" launch -Version `"$script:SelectedVersion`" -Nickname `"$nickname`" -RamMb $ramMb"

    if ($NoExitOnLaunch) {
        $args = "-NoExit $args"
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass $args" -WorkingDirectory $script:Root
        return
    }

    [void](Start-HiddenPowerShell -Arguments $args)
})

[void]$window.ShowDialog()
