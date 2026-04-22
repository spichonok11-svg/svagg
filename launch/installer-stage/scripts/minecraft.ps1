param(
    [Parameter(Position=0)]
    [ValidateSet('launch','status','dry-run','install')]
    [string]$Command = 'status',

    [ValidateSet('Forge 1.21.11','Fabric 1.21.11')]
    [string]$Version = 'Forge 1.21.11',

    [string]$Nickname = 'player',

    [int]$RamMb = 4096
)

$ErrorActionPreference = 'Stop'
$script:LauncherRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script:GameRoot = Join-Path $script:LauncherRoot 'game\.minecraft'
$script:SourceRoot = Join-Path $env:APPDATA '.minecraft'

function Get-MinecraftRoot {
    $script:GameRoot
}

function Get-SourceMinecraftRoot {
    $script:SourceRoot
}

function Get-VersionId {
    param(
        [string]$FriendlyVersion,
        [string]$Root = (Get-MinecraftRoot)
    )

    $versionsDir = Join-Path $Root 'versions'
    if (-not (Test-Path -LiteralPath $versionsDir)) {
        throw "Minecraft versions folder was not found: $versionsDir"
    }

    if ($FriendlyVersion -eq 'Fabric 1.21.11') {
        $fabric = Get-ChildItem -LiteralPath $versionsDir -Directory |
            Where-Object { $_.Name -like 'fabric-loader-*-1.21.11' -or $_.Name -like 'fabric-loader-*-minecraft-1.21.11' } |
            Sort-Object Name -Descending |
            Select-Object -First 1

        if ($fabric) {
            return $fabric.Name
        }

        if (Test-Path -LiteralPath (Join-Path $versionsDir 'Fabric 1.21.11')) {
            return 'Fabric 1.21.11'
        }

        throw 'Fabric 1.21.11 is not installed in .minecraft\versions.'
    }

    $forgeCandidates = @(
        'Forge-1.21.11',
        '1.21.11-forge',
        'forge-1.21.11',
        'Forge 1.21.11'
    )

    foreach ($candidate in $forgeCandidates) {
        if (Test-Path -LiteralPath (Join-Path $versionsDir $candidate)) {
            return $candidate
        }
    }

    $forge = Get-ChildItem -LiteralPath $versionsDir -Directory |
        Where-Object { $_.Name -like '*forge*1.21.11*' -or $_.Name -like '*1.21.11*forge*' } |
        Sort-Object Name -Descending |
        Select-Object -First 1

    if ($forge) {
        return $forge.Name
    }

    throw 'Forge 1.21.11 is not installed in .minecraft\versions.'
}

function Read-VersionJson {
    param(
        [string]$VersionId,
        [string]$Root = (Get-MinecraftRoot)
    )

    $jsonPath = Join-Path (Join-Path (Join-Path $Root 'versions') $VersionId) "$VersionId.json"
    if (-not (Test-Path -LiteralPath $jsonPath)) {
        throw "Version json was not found: $jsonPath"
    }

    $json = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    if ($Command -eq 'dry-run') {
        Write-Host "Read debug $VersionId path=$jsonPath args: $(@($json.arguments.jvm).Count)/$(@($json.arguments.game).Count)"
    }
    [pscustomobject]@{ Data = $json }
}

function Merge-VersionJson {
    param(
        [string]$VersionId,
        [string]$Root = (Get-MinecraftRoot)
    )

    $jsonPath = Join-Path (Join-Path (Join-Path $Root 'versions') $VersionId) "$VersionId.json"
    if (-not (Test-Path -LiteralPath $jsonPath)) {
        throw "Version json was not found: $jsonPath"
    }
    $jsonRoot = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
    if (-not $jsonRoot.inheritsFrom) {
        [pscustomobject]@{ Data = $jsonRoot }
        return
    }

    $parent = (Merge-VersionJson -VersionId $jsonRoot.inheritsFrom -Root $Root).Data

    $merged = [ordered]@{}
    foreach ($prop in $parent.PSObject.Properties) {
        $merged[$prop.Name] = $prop.Value
    }
    foreach ($prop in $jsonRoot.PSObject.Properties) {
        if ($prop.Name -eq 'libraries') {
            $merged['libraries'] = @($parent.libraries) + @($jsonRoot.libraries)
        } elseif ($prop.Name -eq 'arguments') {
            $combinedArguments = [ordered]@{}
            $combinedArguments['jvm'] = @($parent.arguments.jvm) + @($jsonRoot.arguments.jvm)
            $combinedArguments['game'] = @($parent.arguments.game) + @($jsonRoot.arguments.game)
            $merged['arguments'] = [pscustomobject]$combinedArguments
        } else {
            $merged[$prop.Name] = $prop.Value
        }
    }

    [pscustomobject]@{ Data = ([pscustomobject]$merged) }
}

function Copy-DirectoryContents {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | Copy-Item -Destination $Destination -Recurse -Force
}

function Copy-VersionTree {
    param(
        [string]$VersionId,
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    $sourceVersion = Join-Path (Join-Path $SourceRoot 'versions') $VersionId
    $destinationVersion = Join-Path (Join-Path $DestinationRoot 'versions') $VersionId
    Copy-DirectoryContents -Source $sourceVersion -Destination $destinationVersion

    try {
        $json = Read-VersionJson -VersionId $VersionId -Root $SourceRoot
        if ($json.inheritsFrom) {
            Copy-VersionTree -VersionId $json.inheritsFrom -SourceRoot $SourceRoot -DestinationRoot $DestinationRoot
        }
    } catch {
    }
}

function Ensure-NoSpaceForgeAlias {
    param([string]$Root = (Get-MinecraftRoot))

    $versionsDir = Join-Path $Root 'versions'
    $sourceDir = Join-Path $versionsDir 'Forge 1.21.11'
    $aliasDir = Join-Path $versionsDir 'Forge-1.21.11'

    if (-not (Test-Path -LiteralPath $sourceDir)) {
        return
    }

    if (-not (Test-Path -LiteralPath $aliasDir)) {
        Copy-DirectoryContents -Source $sourceDir -Destination $aliasDir
    }

    $sourceJson = Join-Path $aliasDir 'Forge 1.21.11.json'
    $aliasJson = Join-Path $aliasDir 'Forge-1.21.11.json'
    if ((Test-Path -LiteralPath $sourceJson) -and -not (Test-Path -LiteralPath $aliasJson)) {
        Copy-Item -LiteralPath $sourceJson -Destination $aliasJson -Force
    }

    $sourceJar = Join-Path $aliasDir 'Forge 1.21.11.jar'
    $aliasJar = Join-Path $aliasDir 'Forge-1.21.11.jar'
    if ((Test-Path -LiteralPath $sourceJar) -and -not (Test-Path -LiteralPath $aliasJar)) {
        Copy-Item -LiteralPath $sourceJar -Destination $aliasJar -Force
    }
}

function Download-FileIfMissing {
    param(
        [string]$Url,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Url) -or [string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    if (Test-Path -LiteralPath $Path) {
        return
    }

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing
}

function Download-ModFile {
    param(
        [string]$Url,
        [string]$DestinationFolder,
        [string]$FallbackName
    )

    New-Item -ItemType Directory -Path $DestinationFolder -Force | Out-Null

    $fileName = ''
    try {
        $fileName = [IO.Path]::GetFileName(([Uri]$Url).AbsolutePath)
    } catch {
    }
    if ([string]::IsNullOrWhiteSpace($fileName) -or -not $fileName.EndsWith('.jar')) {
        $fileName = $FallbackName
    }

    if (-not $fileName.EndsWith('.jar')) {
        $fileName = "$fileName.jar"
    }

    $target = Join-Path $DestinationFolder $fileName
    if (Test-Path -LiteralPath $target) {
        return
    }

    Write-Host "Downloading mod $Url"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $target -UseBasicParsing -Headers @{
            'User-Agent' = 'Mozilla/5.0 ESLauncher'
            'Referer' = 'https://minecraft-inside.ru/'
        }
    } catch {
        Write-Host "Could not download mod: $Url"
        Write-Host $_.Exception.Message
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
        return
    }

    $firstBytes = [byte[]](Get-Content -LiteralPath $target -Encoding Byte -TotalCount 4)
    if ($firstBytes.Length -lt 2 -or $firstBytes[0] -ne 0x50 -or $firstBytes[1] -ne 0x4B) {
        Write-Host "Warning: downloaded mod does not look like a jar: $target"
        Remove-Item -LiteralPath $target -Force
        return
    }

    return $target
}

function Install-VanillaOnline {
    param([string]$GameVersion = '1.21.11')

    $root = Get-MinecraftRoot
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    $manifestUrl = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
    $manifest = Invoke-RestMethod -Uri $manifestUrl -UseBasicParsing
    $entry = $manifest.versions | Where-Object { $_.id -eq $GameVersion } | Select-Object -First 1
    if (-not $entry) {
        throw "Minecraft $GameVersion was not found in Mojang version manifest."
    }

    $versionDir = Join-Path (Join-Path $root 'versions') $GameVersion
    New-Item -ItemType Directory -Path $versionDir -Force | Out-Null
    $versionJsonPath = Join-Path $versionDir "$GameVersion.json"
    Download-FileIfMissing -Url $entry.url -Path $versionJsonPath

    $json = Get-Content -LiteralPath $versionJsonPath -Raw | ConvertFrom-Json
    if ($json.downloads -and $json.downloads.client -and $json.downloads.client.url) {
        Download-FileIfMissing -Url $json.downloads.client.url -Path (Join-Path $versionDir "$GameVersion.jar")
    }

    Install-LibrariesFromJson -VersionJson $json
    Install-AssetsFromJson -VersionJson $json
}

function Install-LibrariesFromJson {
    param($VersionJson)

    foreach ($library in @($VersionJson.libraries)) {
        if (-not (Test-LibraryRules $library)) {
            continue
        }

        if ($library.downloads -and $library.downloads.artifact -and $library.downloads.artifact.url -and $library.downloads.artifact.path) {
            $path = Join-Path (Join-Path (Get-MinecraftRoot) 'libraries') $library.downloads.artifact.path.Replace('/', '\')
            Download-FileIfMissing -Url $library.downloads.artifact.url -Path $path
        }

        if ($library.downloads -and $library.downloads.classifiers) {
            foreach ($property in $library.downloads.classifiers.PSObject.Properties) {
                if ($property.Name -like 'natives-windows*' -and $property.Value.url -and $property.Value.path) {
                    $path = Join-Path (Join-Path (Get-MinecraftRoot) 'libraries') $property.Value.path.Replace('/', '\')
                    Download-FileIfMissing -Url $property.Value.url -Path $path
                }
            }
        }

        if ($library.url -and $library.name) {
            $relative = Get-ArtifactPathFromName $library.name
            if ($relative) {
                $baseUrl = $library.url.TrimEnd('/')
                $url = "$baseUrl/$($relative.Replace('\','/'))"
                $path = Join-Path (Join-Path (Get-MinecraftRoot) 'libraries') $relative
                Download-FileIfMissing -Url $url -Path $path
            }
        }
    }
}

function Install-AssetsFromJson {
    param($VersionJson)

    if (-not $VersionJson.assetIndex -or -not $VersionJson.assetIndex.url -or -not $VersionJson.assetIndex.id) {
        return
    }

    $assetsRoot = Join-Path (Get-MinecraftRoot) 'assets'
    $indexPath = Join-Path (Join-Path $assetsRoot 'indexes') "$($VersionJson.assetIndex.id).json"
    Download-FileIfMissing -Url $VersionJson.assetIndex.url -Path $indexPath

    $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
    foreach ($property in $index.objects.PSObject.Properties) {
        $hash = [string]$property.Value.hash
        if ([string]::IsNullOrWhiteSpace($hash) -or $hash.Length -lt 2) {
            continue
        }
        $prefix = $hash.Substring(0, 2)
        $assetPath = Join-Path (Join-Path (Join-Path $assetsRoot 'objects') $prefix) $hash
        Download-FileIfMissing -Url "https://resources.download.minecraft.net/$prefix/$hash" -Path $assetPath
    }
}

function Install-FabricOnline {
    param([string]$GameVersion = '1.21.11')

    Install-VanillaOnline -GameVersion $GameVersion

    $loaderList = Invoke-RestMethod -Uri "https://meta.fabricmc.net/v2/versions/loader/$GameVersion" -UseBasicParsing
    $loader = $loaderList | Where-Object { $_.loader -and $_.loader.stable } | Select-Object -First 1
    if (-not $loader) {
        $loader = $loaderList | Select-Object -First 1
    }
    if (-not $loader -or -not $loader.loader.version) {
        throw "Fabric loader for Minecraft $GameVersion was not found."
    }

    $loaderVersion = $loader.loader.version
    $versionId = "fabric-loader-$loaderVersion-$GameVersion"
    $versionDir = Join-Path (Join-Path (Get-MinecraftRoot) 'versions') $versionId
    New-Item -ItemType Directory -Path $versionDir -Force | Out-Null
    $profileUrl = "https://meta.fabricmc.net/v2/versions/loader/$GameVersion/$loaderVersion/profile/json"
    $profilePath = Join-Path $versionDir "$versionId.json"
    Invoke-WebRequest -Uri $profileUrl -OutFile $profilePath -UseBasicParsing

    $json = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
    Install-LibrariesFromJson -VersionJson $json
}

function Install-ForgeOnline {
    param([string]$GameVersion = '1.21.11')

    Install-VanillaOnline -GameVersion $GameVersion

    $forgeVersion = '61.1.0'
    $installerName = "forge-$GameVersion-$forgeVersion-installer.jar"
    $installerPath = Join-Path (Join-Path (Get-MinecraftRoot) 'downloads') $installerName
    $installerUrl = "https://maven.minecraftforge.net/net/minecraftforge/forge/$GameVersion-$forgeVersion/$installerName"
    Download-FileIfMissing -Url $installerUrl -Path $installerPath

    $java = Get-JavaPath -RequiredMajor 21 -Component 'java-runtime-delta'
    Write-Host "Installing Forge $GameVersion-$forgeVersion into $(Get-MinecraftRoot)"
    $output = & $java -jar $installerPath --installClient (Get-MinecraftRoot) 2>&1
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "Forge installer failed with exit code $exit."
    }
}

function Install-FromLocalMinecraft {
    param([string]$FriendlyVersion)

    $source = Get-SourceMinecraftRoot
    $target = Get-MinecraftRoot
    if (-not (Test-Path -LiteralPath $source)) {
        return $false
    }

    try {
        $versionId = Get-VersionId -FriendlyVersion $FriendlyVersion -Root $source
    } catch {
        return $false
    }

    Write-Host "Copying Minecraft files into $target"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($dir in @('assets','libraries','runtime')) {
        Copy-DirectoryContents -Source (Join-Path $source $dir) -Destination (Join-Path $target $dir)
    }
    Copy-VersionTree -VersionId $versionId -SourceRoot $source -DestinationRoot $target
    return $true
}

function Install-MinecraftVersion {
    param([string]$FriendlyVersion)

    if (Install-FromLocalMinecraft -FriendlyVersion $FriendlyVersion) {
        return
    }

    if ($FriendlyVersion -eq 'Fabric 1.21.11') {
        Install-FabricOnline -GameVersion '1.21.11'
        return
    }

    if ($FriendlyVersion -eq 'Forge 1.21.11') {
        Install-ForgeOnline -GameVersion '1.21.11'
        return
    }

    Install-VanillaOnline -GameVersion '1.21.11'
}

function Add-UniquePath {
    param(
        [System.Collections.Generic.List[string]]$Paths,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    if (-not $Paths.Contains($Path)) {
        [void]$Paths.Add($Path)
    }
}

function Get-VersionModFolders {
    param([string]$FriendlyVersion = '')

    $root = Get-MinecraftRoot
    $versionsDir = Join-Path $root 'versions'
    $folders = New-Object 'System.Collections.Generic.List[string]'
    $versionDirs = New-Object 'System.Collections.Generic.List[string]'

    if (-not (Test-Path -LiteralPath $versionsDir)) {
        return @()
    }

    try {
        $versionId = Get-VersionId -FriendlyVersion $FriendlyVersion -Root $root
        Add-UniquePath -Paths $versionDirs -Path (Join-Path $versionsDir $versionId)
    } catch {
    }

    if ($FriendlyVersion -like 'Forge*') {
        foreach ($name in @('Forge-1.21.11','Forge 1.21.11')) {
            Add-UniquePath -Paths $versionDirs -Path (Join-Path $versionsDir $name)
        }

        Get-ChildItem -LiteralPath $versionsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '*forge*1.21.11*' -or $_.Name -like '*1.21.11*forge*' } |
            ForEach-Object { Add-UniquePath -Paths $versionDirs -Path $_.FullName }
    }

    if ($FriendlyVersion -like 'Fabric*') {
        foreach ($name in @('Fabric 1.21.11')) {
            Add-UniquePath -Paths $versionDirs -Path (Join-Path $versionsDir $name)
        }

        Get-ChildItem -LiteralPath $versionsDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'fabric-loader-*-1.21.11' -or $_.Name -like 'fabric-loader-*-minecraft-1.21.11' } |
            ForEach-Object { Add-UniquePath -Paths $versionDirs -Path $_.FullName }
    }

    foreach ($versionDir in $versionDirs) {
        if (Test-Path -LiteralPath $versionDir) {
            $modsDir = Join-Path $versionDir 'mods'
            New-Item -ItemType Directory -Path $modsDir -Force | Out-Null
            Add-UniquePath -Paths $folders -Path $modsDir
        }
    }

    return $folders.ToArray()
}

function Copy-ModJars {
    param(
        [string]$SourceFolder,
        [string[]]$Targets
    )

    if (-not (Test-Path -LiteralPath $SourceFolder)) {
        return
    }

    $files = Get-ChildItem -LiteralPath $SourceFolder -Filter '*.jar' -File -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        foreach ($target in $Targets) {
            if ([string]::IsNullOrWhiteSpace($target)) {
                continue
            }
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        }
    }
}

function Sync-LauncherMods {
    param([string]$FriendlyVersion = '')

    $rootMods = Join-Path $script:LauncherRoot 'mods'
    $gameMods = Join-Path (Get-MinecraftRoot) 'mods'
    $versionMods = Get-VersionModFolders -FriendlyVersion $FriendlyVersion
    $modTargets = @($gameMods) + $versionMods
    New-Item -ItemType Directory -Path $rootMods -Force | Out-Null
    foreach ($target in $modTargets) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }

    if (Test-Path -LiteralPath $rootMods) {
        Copy-ModJars -SourceFolder $rootMods -Targets $modTargets

        $commonMods = Join-Path $rootMods 'common'
        Copy-ModJars -SourceFolder $commonMods -Targets $modTargets

        if ($FriendlyVersion -like 'Forge*') {
            $forgeMods = Join-Path $rootMods 'forge'
            Copy-ModJars -SourceFolder $forgeMods -Targets $modTargets
        }

        if ($FriendlyVersion -like 'Fabric*') {
            $fabricMods = Join-Path $rootMods 'fabric'
            Copy-ModJars -SourceFolder $fabricMods -Targets $modTargets
        }

        $urlLists = @((Join-Path $rootMods 'mod-urls.txt'))
        if ($FriendlyVersion -like 'Forge*') {
            $urlLists += (Join-Path $rootMods 'forge-urls.txt')
        }
        if ($FriendlyVersion -like 'Fabric*') {
            $urlLists += (Join-Path $rootMods 'fabric-urls.txt')
        }

        $index = 1
        foreach ($urlList in $urlLists) {
            if (-not (Test-Path -LiteralPath $urlList)) {
                continue
            }
            foreach ($line in (Get-Content -LiteralPath $urlList)) {
                $url = $line.Trim()
                if ([string]::IsNullOrWhiteSpace($url) -or $url.StartsWith('#')) {
                    continue
                }

                $prefix = if ($FriendlyVersion -like 'Fabric*') { 'fabric-mod' } elseif ($FriendlyVersion -like 'Forge*') { 'forge-mod' } else { 'mod' }
                $downloaded = Download-ModFile -Url $url -DestinationFolder $gameMods -FallbackName "$prefix-$index.jar"
                if ($downloaded -and (Test-Path -LiteralPath $downloaded)) {
                    foreach ($versionMod in $versionMods) {
                        Copy-Item -LiteralPath $downloaded -Destination $versionMod -Force
                    }
                }
                $index++
            }
        }
    }
}

function Ensure-MinecraftVersion {
    param([string]$FriendlyVersion)

    try {
        [void](Get-VersionId -FriendlyVersion $FriendlyVersion -Root (Get-MinecraftRoot))
    } catch {
        Install-MinecraftVersion -FriendlyVersion $FriendlyVersion
    }

    if ($FriendlyVersion -like 'Forge*') {
        Ensure-NoSpaceForgeAlias -Root (Get-MinecraftRoot)
    }
    if ($Command -ne 'dry-run') {
        Sync-LauncherMods -FriendlyVersion $FriendlyVersion
    }
}

function Test-InstalledVersion {
    param([string]$FriendlyVersion)

    try {
        [void](Get-VersionId -FriendlyVersion $FriendlyVersion -Root (Get-MinecraftRoot))
        return $true
    } catch {
        return $false
    }
}

function Test-Rules {
    param($Item)

    if (-not $Item.rules) {
        return $true
    }

    if (@($Item.rules).Count -eq 0) {
        return $true
    }

    $allowed = $false
    foreach ($rule in @($Item.rules)) {
        if ($rule -is [string]) {
            continue
        }
        $applies = $true
        if ($rule.os -and $rule.os.name -and $rule.os.name -ne 'windows') {
            $applies = $false
        }
        if ($rule.os -and $rule.os.arch) {
            if ($rule.os.arch -eq 'x86' -and [Environment]::Is64BitOperatingSystem) {
                $applies = $false
            }
            if ($rule.os.arch -eq 'x64' -and -not [Environment]::Is64BitOperatingSystem) {
                $applies = $false
            }
        }
        if ($rule.features) {
            $applies = $false
        }
        if ($applies) {
            $allowed = ($rule.action -eq 'allow')
        }
    }
    return $allowed
}

function Test-LibraryRules {
    param($Library)

    Test-Rules $Library
}

function Get-ArtifactPathFromName {
    param([string]$Name)

    $parts = $Name.Split(':')
    if ($parts.Length -lt 3) {
        return $null
    }

    $groupPath = $parts[0].Replace('.', '\')
    $artifact = $parts[1]
    $version = $parts[2]
    $classifier = if ($parts.Length -gt 3) { "-$($parts[3])" } else { '' }

    "$groupPath\$artifact\$version\$artifact-$version$classifier.jar"
}

function Get-LibraryPath {
    param($Library)

    $root = Get-MinecraftRoot
    if ($Library.downloads -and $Library.downloads.artifact -and $Library.downloads.artifact.path) {
        return Join-Path (Join-Path $root 'libraries') $Library.downloads.artifact.path.Replace('/', '\')
    }

    if ($Library.artifact -and $Library.artifact.path) {
        $relative = $Library.artifact.path.Replace('/', '\')
        if ($relative -like 'libraries\*') {
            return Join-Path $root $relative
        }
        return Join-Path (Join-Path $root 'libraries') $relative
    }

    $relative = Get-ArtifactPathFromName $Library.name
    if ($relative) {
        return Join-Path (Join-Path $root 'libraries') $relative
    }

    return $null
}

function Test-NativeLibrary {
    param($Library)

    if ($Library.natives) {
        return $true
    }

    if (-not $Library.name) {
        return $false
    }

    $parts = $Library.name.Split(':')
    if ($parts.Length -lt 4) {
        return $false
    }

    $classifier = $parts[3]
    if ($classifier -notlike 'natives-windows*') {
        return $false
    }

    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($classifier -like '*arm64*') {
        return $arch -eq 'ARM64'
    }
    if ($classifier -like '*x86*') {
        return -not [Environment]::Is64BitOperatingSystem
    }

    return $true
}

function Get-NativeLibraryPath {
    param($Library)

    if (-not $Library.natives -or -not $Library.natives.windows) {
        if (Test-NativeLibrary $Library) {
            return Get-LibraryPath $Library
        }
        return $null
    }

    $classifier = $Library.natives.windows -replace '\$\{arch\}', '64'
    if ($Library.downloads -and $Library.downloads.classifiers -and $Library.downloads.classifiers.$classifier -and $Library.downloads.classifiers.$classifier.path) {
        return Join-Path (Join-Path (Get-MinecraftRoot) 'libraries') $Library.downloads.classifiers.$classifier.path.Replace('/', '\')
    }

    $parts = $Library.name.Split(':')
    if ($parts.Length -lt 3) {
        return $null
    }

    $groupPath = $parts[0].Replace('.', '\')
    $artifact = $parts[1]
    $libVersion = $parts[2]
    return Join-Path (Join-Path (Get-MinecraftRoot) 'libraries') "$groupPath\$artifact\$libVersion\$artifact-$libVersion-$classifier.jar"
}

function Expand-Natives {
    param($Libraries)

    $nativeDir = Join-Path $env:TEMP ("es-launcher-natives-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $nativeDir -Force | Out-Null
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    foreach ($library in $Libraries) {
        if (-not (Test-LibraryRules $library)) {
            continue
        }

        $nativePath = Get-NativeLibraryPath $library
        if ($nativePath -and (Test-Path -LiteralPath $nativePath)) {
            $archive = [System.IO.Compression.ZipFile]::OpenRead($nativePath)
            try {
                foreach ($entry in $archive.Entries) {
                    if ([string]::IsNullOrWhiteSpace($entry.Name)) {
                        continue
                    }
                    if ($entry.FullName -like 'META-INF/*') {
                        continue
                    }

                    $target = Join-Path $nativeDir $entry.FullName.Replace('/', '\')
                    $targetDir = Split-Path -Parent $target
                    if (-not (Test-Path -LiteralPath $targetDir)) {
                        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
                    }
                    if (Test-Path -LiteralPath $target) {
                        Remove-Item -LiteralPath $target -Force
                    }
                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target)
                }
            } finally {
                $archive.Dispose()
            }
        }
    }

    return $nativeDir
}

function Get-JavaMajorVersion {
    param([string]$JavaPath)

    $javaForVersion = $JavaPath
    if ([IO.Path]::GetFileName($JavaPath).ToLowerInvariant() -eq 'javaw.exe') {
        $sibling = Join-Path (Split-Path -Parent $JavaPath) 'java.exe'
        if (Test-Path -LiteralPath $sibling) {
            $javaForVersion = $sibling
        }
    }

    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $versionText = (& $javaForVersion -version 2>&1 | ForEach-Object { $_.ToString() }) -join "`n"
        if ($versionText -match 'version "1\.(\d+)') {
            return [int]$Matches[1]
        }
        if ($versionText -match 'version "(\d+)') {
            return [int]$Matches[1]
        }
    } catch {
        return 0
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }

    return 0
}

function Get-JavaPath {
    param(
        [int]$RequiredMajor = 0,
        [string]$Component = ''
    )

    $candidates = New-Object System.Collections.Generic.List[string]

    $runtimeRoot = Join-Path (Get-MinecraftRoot) 'runtime'
    if (Test-Path -LiteralPath $runtimeRoot) {
        if ($Component) {
            $componentRoot = Join-Path $runtimeRoot $Component
            if (Test-Path -LiteralPath $componentRoot) {
                foreach ($path in (Get-ChildItem -LiteralPath $componentRoot -Recurse -Filter javaw.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)) {
                    $candidates.Add($path)
                }
            }
        }

        foreach ($path in (Get-ChildItem -LiteralPath $runtimeRoot -Recurse -Filter javaw.exe -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName)) {
            $candidates.Add($path)
        }
    }

    $pathJava = Get-Command javaw.exe -ErrorAction SilentlyContinue
    if ($pathJava) {
        $candidates.Add($pathJava.Source)
    }

    $pathJavaConsole = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($pathJavaConsole) {
        $candidates.Add($pathJavaConsole.Source)
    }

    $existing = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
    foreach ($java in $existing) {
        if ($RequiredMajor -le 0) {
            return $java
        }

        $major = Get-JavaMajorVersion $java
        if ($major -ge $RequiredMajor) {
            return $java
        }
    }

    if ($existing) {
        throw "Java $RequiredMajor or newer is required. Run the official Minecraft Launcher once or install Java $RequiredMajor."
    }

    throw "Java was not found. Run the official Minecraft Launcher once or install Java $RequiredMajor."
}

function Get-ClassPath {
    param(
        [string]$VersionId,
        $VersionJson
    )

    $items = New-Object System.Collections.Generic.List[string]
    foreach ($library in @($VersionJson.libraries)) {
        if (-not (Test-LibraryRules $library)) {
            continue
        }

        if (Test-NativeLibrary $library) {
            continue
        }

        $path = Get-LibraryPath $library
        if ($path -and (Test-Path -LiteralPath $path)) {
            $items.Add($path)
        }
    }

    $clientJar = Join-Path (Join-Path (Join-Path (Get-MinecraftRoot) 'versions') $VersionId) "$VersionId.jar"
    if (-not (Test-Path -LiteralPath $clientJar) -and $VersionJson.inheritsFrom) {
        $clientJar = Join-Path (Join-Path (Join-Path (Get-MinecraftRoot) 'versions') $VersionJson.inheritsFrom) "$($VersionJson.inheritsFrom).jar"
    }

    if (-not (Test-Path -LiteralPath $clientJar)) {
        throw "Client jar was not found: $clientJar"
    }

    $items.Add($clientJar)
    $items -join ';'
}

function Resolve-GameArguments {
    param(
        $VersionJson,
        [string]$VersionId,
        [string]$Nickname,
        [string]$NativeDir,
        [string]$ClassPath,
        [int]$RamMb = 4096
    )

    $mcRoot = Get-MinecraftRoot
    $assetsRoot = Join-Path $mcRoot 'assets'
    $assetIndex = if ($VersionJson.assetIndex -and $VersionJson.assetIndex.id) { $VersionJson.assetIndex.id } elseif ($VersionJson.assets) { $VersionJson.assets } else { 'legacy' }

    $replacements = @{
        '${auth_player_name}' = $Nickname
        '${version_name}' = $VersionId
        '${game_directory}' = $mcRoot
        '${assets_root}' = $assetsRoot
        '${assets_index_name}' = $assetIndex
        '${auth_uuid}' = ([guid]::NewGuid().ToString('N'))
        '${auth_access_token}' = '0'
        '${clientid}' = '0'
        '${auth_xuid}' = '0'
        '${user_type}' = 'legacy'
        '${version_type}' = 'release'
        '${natives_directory}' = $NativeDir
        '${launcher_name}' = 'ESLauncher'
        '${launcher_version}' = '1.0'
        '${classpath}' = $ClassPath
        '${classpath_separator}' = ';'
        '${quickPlayPath}' = ''
        '${quickPlaySingleplayer}' = ''
        '${quickPlayMultiplayer}' = ''
        '${quickPlayRealms}' = ''
    }

    $jvmArgs = New-Object System.Collections.Generic.List[string]
    $gameArgs = New-Object System.Collections.Generic.List[string]

    function Add-ArgumentItem {
        param(
            [System.Collections.Generic.List[string]]$List,
            $Item
        )

        if ($Item -is [string]) {
            $List.Add($Item)
            return
        }

        if ($Item -and (Test-Rules $Item)) {
            $argumentValues = $null
            if ($Item.PSObject.Properties['value']) {
                $argumentValues = $Item.value
            } elseif ($Item.PSObject.Properties['values']) {
                $argumentValues = $Item.values
            }

            if ($null -eq $argumentValues) {
                return
            }

            if ($argumentValues -is [System.Array]) {
                foreach ($value in $argumentValues) {
                    if ($null -ne $value) {
                        $List.Add([string]$value)
                    }
                }
            } else {
                $List.Add([string]$argumentValues)
            }
        }
    }

    if ($VersionJson.arguments -and $VersionJson.arguments.jvm) {
        foreach ($arg in $VersionJson.arguments.jvm) {
            Add-ArgumentItem -List $jvmArgs -Item $arg
        }
    } else {
        $jvmArgs.Add('-Djava.library.path=${natives_directory}')
        $jvmArgs.Add('-cp')
        $jvmArgs.Add('${classpath}')
    }

    if ($VersionJson.arguments -and $VersionJson.arguments.game) {
        foreach ($arg in $VersionJson.arguments.game) {
            Add-ArgumentItem -List $gameArgs -Item $arg
        }
    } elseif ($VersionJson.minecraftArguments) {
        foreach ($arg in $VersionJson.minecraftArguments.Split(' ')) {
            if ($arg) {
                $gameArgs.Add($arg)
            }
        }
    }

    $allArgs = New-Object System.Collections.Generic.List[string]
    $allArgs.Add("-Xmx$($RamMb)M")
    $allArgs.Add('-Xms512M')
    foreach ($arg in $jvmArgs) {
        if ($arg -notmatch '^-Xm[xs]') {
            $allArgs.Add($arg)
        }
    }
    $allArgs.Add($VersionJson.mainClass)
    foreach ($arg in $gameArgs) {
        $allArgs.Add($arg)
    }

    for ($i = 0; $i -lt $allArgs.Count; $i++) {
        foreach ($key in $replacements.Keys) {
            $allArgs[$i] = $allArgs[$i].Replace($key, [string]$replacements[$key])
        }
    }

    return $allArgs.ToArray()
}

function Show-Status {
    $versionsDir = Join-Path (Get-MinecraftRoot) 'versions'
    Write-Host "Launcher Minecraft root: $(Get-MinecraftRoot)"
    Write-Host "Source Minecraft root: $(Get-SourceMinecraftRoot)"
    Write-Host "Versions folder: $versionsDir"
    foreach ($friendly in @('Forge 1.21.11','Fabric 1.21.11')) {
        try {
            $id = Get-VersionId -FriendlyVersion $friendly -Root (Get-MinecraftRoot)
            Write-Host "$friendly => $id"
        } catch {
            Write-Host "$friendly => not found"
        }
    }
}

if ($Command -eq 'status') {
    Show-Status
    exit 0
}

if ($Command -eq 'install') {
    Install-MinecraftVersion -FriendlyVersion $Version
    if ($Version -like 'Forge*') {
        Ensure-NoSpaceForgeAlias -Root (Get-MinecraftRoot)
    }
    Sync-LauncherMods -FriendlyVersion $Version
    Write-Host "Install ready: $Version"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Nickname) -or $Nickname.ToLowerInvariant() -eq 'player') {
    throw 'Change nickname before launch.'
}

if ($Nickname -notmatch '^[A-Za-z0-9_]{3,16}$') {
    throw 'Nickname must contain 3-16 letters, numbers, or underscores.'
}

if ($RamMb -lt 1024) {
    $RamMb = 1024
}
if ($RamMb -gt 32768) {
    $RamMb = 32768
}

Ensure-MinecraftVersion -FriendlyVersion $Version

$versionId = Get-VersionId -FriendlyVersion $Version -Root (Get-MinecraftRoot)
$versionJson = (Merge-VersionJson -VersionId $versionId -Root (Get-MinecraftRoot)).Data
$nativeDir = Expand-Natives @($versionJson.libraries)
$classPath = Get-ClassPath -VersionId $versionId -VersionJson $versionJson
$requiredJava = if ($versionJson.javaVersion -and $versionJson.javaVersion.majorVersion) { [int]$versionJson.javaVersion.majorVersion } else { 21 }
$javaComponent = if ($versionJson.javaVersion -and $versionJson.javaVersion.component) { [string]$versionJson.javaVersion.component } else { '' }
$java = Get-JavaPath -RequiredMajor $requiredJava -Component $javaComponent
$arguments = Resolve-GameArguments -VersionJson $versionJson -VersionId $versionId -Nickname $Nickname -NativeDir $nativeDir -ClassPath $classPath -RamMb $RamMb

if ($Command -eq 'dry-run') {
    Write-Host "Dry run OK for $Version ($versionId) as $Nickname"
    Write-Host "Java: $java"
    Write-Host "Native directory: $nativeDir"
    Write-Host "Arguments prepared: $($arguments.Count)"
    exit 0
}

Write-Host "Starting $Version ($versionId) as $Nickname"

function ConvertTo-CommandLineArgument {
    param([string]$Value)

    if ($null -eq $Value) {
        return '""'
    }

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

$javaToRun = $java
if ([IO.Path]::GetFileName($java).ToLowerInvariant() -eq 'javaw.exe') {
    $consoleJava = Join-Path (Split-Path -Parent $java) 'java.exe'
    if (Test-Path -LiteralPath $consoleJava) {
        $javaToRun = $consoleJava
    }
}

$logsDir = Join-Path (Get-MinecraftRoot) 'logs'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$stdoutPath = Join-Path $logsDir 'launcher-java-out.log'
$stderrPath = Join-Path $logsDir 'launcher-java-err.log'
$argsFilePath = Join-Path $logsDir 'launcher-java.args'
Set-Content -LiteralPath $stdoutPath -Value '' -Encoding UTF8
Set-Content -LiteralPath $stderrPath -Value '' -Encoding UTF8
$argLinesList = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $arguments.Count; $i++) {
    $value = [string]$arguments[$i]
    if ($i -gt 0 -and [string]$arguments[$i - 1] -eq '-cp') {
        $argLinesList.Add($value)
    } else {
        $argLinesList.Add((ConvertTo-CommandLineArgument $value))
    }
}
$argLines = [string[]]$argLinesList.ToArray()
[IO.File]::WriteAllLines($argsFilePath, $argLines, (New-Object System.Text.UTF8Encoding($false)))

$commandLine = (ConvertTo-CommandLineArgument $javaToRun) + ' @' + (ConvertTo-CommandLineArgument $argsFilePath) +
    ' > ' + (ConvertTo-CommandLineArgument $stdoutPath) +
    ' 2> ' + (ConvertTo-CommandLineArgument $stderrPath)
Set-Content -LiteralPath (Join-Path $logsDir 'launcher-command.txt') -Value $commandLine -Encoding UTF8

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $env:ComSpec
$startInfo.Arguments = '/d /c ' + (ConvertTo-CommandLineArgument $commandLine)
$startInfo.WorkingDirectory = Get-MinecraftRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($startInfo)

Write-Host "Java process started: $($process.Id)"
