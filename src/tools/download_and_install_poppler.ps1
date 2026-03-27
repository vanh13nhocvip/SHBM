<#
Automatically download and extract Poppler (latest Windows release) into tools/deps/poppler.

This script:
1. Queries GitHub API to find latest oschwartz10612/poppler-windows release
2. Downloads the Windows .zip asset
3. Extracts to tools/deps/poppler
4. No manual URL editing needed

Usage (PowerShell):
  .\tools\download_and_install_poppler.ps1

Requirements:
  - PowerShell 3.0+ (or Windows 7+ with .NET 3.5+)
  - Internet connection
  - GitHub API accessible (no auth required for public releases)
#>

param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent -Path $PSScriptRoot
$destDir = Join-Path $repoRoot "tools\deps\poppler"

Write-Host "=== Poppler Windows Auto-Installer ===" -ForegroundColor Green
Write-Host "Destination: $destDir" -ForegroundColor Cyan

# Step 1: Fetch latest release info from GitHub
Write-Host "Fetching latest Poppler release from GitHub..." -ForegroundColor Yellow
try {
    $apiUrl = "https://api.github.com/repos/oschwartz10612/poppler-windows/releases/latest"
    $release = Invoke-RestMethod -Uri $apiUrl -ErrorAction Stop
    $releaseName = $release.name
    Write-Host "Found release: $releaseName" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not fetch GitHub API. Check internet connection or try again later." -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Step 2: Find the Windows .zip asset (usually named Release-X.X.X.zip)
Write-Host "Looking for Windows .zip asset..." -ForegroundColor Yellow
$zipAsset = $release.assets | Where-Object { $_.name -like "Release-*.zip" } | Select-Object -First 1
if (-not $zipAsset) {
    Write-Host "ERROR: No Release-*.zip asset found in this release." -ForegroundColor Red
    Write-Host "Available assets:" -ForegroundColor Yellow
    $release.assets | ForEach-Object { Write-Host "  - $($_.name)" }
    exit 1
}

$downloadUrl = $zipAsset.browser_download_url
$assetName = $zipAsset.name
Write-Host "Asset: $assetName" -ForegroundColor Green
Write-Host "URL: $downloadUrl" -ForegroundColor Cyan

# Step 3: Create destination directory
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Write-Host "Prepared destination directory: $destDir" -ForegroundColor Green

# Step 4: Download zip file
$zipPath = Join-Path $env:TEMP "poppler_windows_latest.zip"
Write-Host "Downloading Poppler..." -ForegroundColor Yellow
try {
    $ProgressPreference = 'SilentlyContinue'  # Suppress progress bar for cleaner output
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -ErrorAction Stop
    Write-Host "Downloaded: $zipPath" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to download Poppler." -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Step 5: Extract zip to destination
Write-Host "Extracting Poppler..." -ForegroundColor Yellow
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $destDir)
    Write-Host "Extracted to: $destDir" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to extract Poppler." -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Step 6: Clean up zip file
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Write-Host "Cleaned up temporary zip file." -ForegroundColor Green

# Step 7: Verify Poppler binaries were extracted
$pdftopiPath = Join-Path $destDir "Library\bin\pdftoinfo.exe"
if (Test-Path $pdftopiPath) {
    Write-Host "✓ Poppler binaries verified at: $destDir\Library\bin" -ForegroundColor Green
    Write-Host "✓ Installation complete! Poppler is ready to use." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. src/config.py already prefers tools/deps/poppler/Library/bin if present (no changes needed)" -ForegroundColor White
    Write-Host "2. Install Tesseract OCR (see tools/INSTALL_TESSERACT.md)" -ForegroundColor White
    Write-Host "3. Run extraction:" -ForegroundColor White
    Write-Host '   $env:PYTHONPATH = "$PWD"; .\venv\Scripts\python.exe -m src.cli_metadata --input "E:\New folder" --output out.xlsx --format excel --recursive' -ForegroundColor Cyan
} else {
    Write-Host "WARNING: Poppler binaries not found at expected location." -ForegroundColor Yellow
    Write-Host "Checked path: $pdftopiPath" -ForegroundColor Yellow
    Write-Host "Listing contents of $($destDir):" -ForegroundColor Yellow
    Get-ChildItem -Path $destDir -Recurse | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
}
