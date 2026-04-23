$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$launcher = Join-Path $root 'ES Launcher.exe'
$icon = Join-Path $root 'assets\es-icon.ico'

$compilerParameters = New-Object System.CodeDom.Compiler.CompilerParameters
$compilerParameters.GenerateExecutable = $true
$compilerParameters.OutputAssembly = $launcher
$compilerParameters.CompilerOptions = '/target:winexe /win32icon:"' + $icon + '"'
$compilerParameters.ReferencedAssemblies.Add('System.Windows.Forms.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.Drawing.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.dll') | Out-Null
$compilerParameters.ReferencedAssemblies.Add('System.Core.dll') | Out-Null

Add-Type `
    -TypeDefinition (Get-Content -LiteralPath "$root\src\ESLauncherWrapper.cs" -Raw -Encoding UTF8) `
    -CompilerParameters $compilerParameters

Write-Host "Built: $launcher"

