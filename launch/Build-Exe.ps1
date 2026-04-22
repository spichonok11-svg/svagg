Add-Type `
    -TypeDefinition (Get-Content -LiteralPath "$PSScriptRoot\src\ESLauncherWrapper.cs" -Raw -Encoding UTF8) `
    -ReferencedAssemblies 'System.Windows.Forms.dll','System.Drawing.dll','System.dll' `
    -OutputAssembly "$PSScriptRoot\ES Launcher.exe" `
    -OutputType WindowsApplication `
    -ErrorAction Stop

Write-Host "Built: $PSScriptRoot\ES Launcher.exe"
