param(
    [string]$WorkPath = 'F:\Temp\VideoBatchConverter\build',
    [string]$OutputPath = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $projectRoot 'dist' }
New-Item -ItemType Directory -Force -Path $WorkPath | Out-Null
$appOutput = Join-Path $OutputPath 'VideoBatchConverter'
$existingSettings = Join-Path $appOutput 'settings.ini'
$preservedSettings = Join-Path $WorkPath 'settings.ini.preserved'
$hasPreservedSettings = Test-Path -LiteralPath $existingSettings
if ($hasPreservedSettings) {
    # Keep an independent in-memory snapshot even if a clean build removes its
    # temporary backup. Never finish a successful rebuild without restoring it.
    $settingsSnapshot = [System.IO.File]::ReadAllBytes($existingSettings)
    Copy-Item -LiteralPath $existingSettings -Destination $preservedSettings
}
$previousCache = $env:PYINSTALLER_CONFIG_DIR
$env:PYINSTALLER_CONFIG_DIR = Join-Path $WorkPath 'cache'
Push-Location $projectRoot
try {
    $brandAssets = Join-Path $projectRoot 'assets\brand'
    $fluentAssets = Join-Path $projectRoot 'assets\icons'
    $fontAssets = Join-Path $projectRoot 'assets\fonts'
    $languageAssets = Join-Path $projectRoot 'assets\i18n'
    $audioAssets = Join-Path $projectRoot 'assets\audio'
    $appIcon = Join-Path $brandAssets 'app-icon.ico'
    $versionInfo = Join-Path $projectRoot 'tools\windows_version_info.txt'
    python -m PyInstaller --noconfirm --clean --windowed --onedir --contents-directory bin --name VideoBatchConverter --icon $appIcon --version-file $versionInfo --add-data "$brandAssets;brand" --add-data "$fluentAssets;icons" --add-data "$fontAssets;fonts" --add-data "$languageAssets;i18n" --add-data "$audioAssets;audio" --specpath $WorkPath --workpath (Join-Path $WorkPath 'work') --distpath $OutputPath (Join-Path $projectRoot 'main.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path $OutputPath 'VideoBatchConverter\LICENSE')
    $runtimePath = Join-Path $projectRoot 'assets\ffmpeg'
    if (Test-Path -LiteralPath $runtimePath) {
        $runtimeOutput = Join-Path $OutputPath 'VideoBatchConverter\bin\ffmpeg'
        New-Item -ItemType Directory -Force -Path $runtimeOutput | Out-Null
        Copy-Item -LiteralPath (Join-Path $runtimePath 'ffmpeg.exe'),(Join-Path $runtimePath 'ffprobe.exe') -Destination $runtimeOutput
    }
    Write-Output (Join-Path $OutputPath 'VideoBatchConverter\VideoBatchConverter.exe')
} finally {
    if ($hasPreservedSettings) {
        New-Item -ItemType Directory -Force -Path $appOutput | Out-Null
        [System.IO.File]::WriteAllBytes($existingSettings, $settingsSnapshot)
        if ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($existingSettings)) -cne
            [Convert]::ToBase64String($settingsSnapshot)) { throw 'settings.ini restoration failed' }
    }
    $env:PYINSTALLER_CONFIG_DIR = $previousCache
    Pop-Location
}
