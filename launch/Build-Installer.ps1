$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$stage = Join-Path $root 'installer-stage'
$package = Join-Path $root 'package.zip'
$setup = Join-Path $root 'ES Launcher Setup.exe'

if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
if (Test-Path -LiteralPath $package) {
    Remove-Item -LiteralPath $package -Force
}

New-Item -ItemType Directory -Path $stage -Force | Out-Null

$items = @(
    'ES Launcher.exe',
    'README.md',
    'scripts',
    'photos',
    'mods'
)

foreach ($item in $items) {
    $source = Join-Path $root $item
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination $stage -Recurse -Force
    }
}

Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $package -Force

$compilerParameters = New-Object System.CodeDom.Compiler.CompilerParameters
$compilerParameters.GenerateExecutable = $true
$compilerParameters.OutputAssembly = $setup
$compilerParameters.CompilerOptions = '/target:winexe'
$compilerParameters.ReferencedAssemblies.Add('System.Windows.Forms.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.Drawing.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.IO.Compression.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.IO.Compression.FileSystem.dll') | Out-Null
$compilerParameters.EmbeddedResources.Add($package) | Out-Null

Add-Type `
    -TypeDefinition (Get-Content -LiteralPath "$root\src\ESLauncherInstaller.cs" -Raw -Encoding UTF8) `
    -CompilerParameters $compilerParameters

Write-Host "Built: $setup"
