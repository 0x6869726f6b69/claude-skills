# skills/ 配下の各スキルを dist/<name>.zip にパッケージ化する（_ で始まるフォルダは除外）
# 使い方: powershell -ExecutionPolicy Bypass -File .\package.ps1 [スキル名]
param([string]$Name)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

$skillsDir = Join-Path $PSScriptRoot 'skills'
$distDir   = Join-Path $PSScriptRoot 'dist'
$exclude   = @('.gitkeep', '.DS_Store', 'Thumbs.db')

$targets = @(Get-ChildItem $skillsDir -Directory | Where-Object { $_.Name -notlike '_*' })
if ($Name) { $targets = @($targets | Where-Object { $_.Name -eq $Name }) }
if ($targets.Count -eq 0) { Write-Warning '対象のスキルがありません'; exit 1 }

foreach ($dir in $targets) {
    # SKILL.md と frontmatter (name / description) の検証
    $skillMd = Join-Path $dir.FullName 'SKILL.md'
    if (-not (Test-Path $skillMd)) { Write-Warning "$($dir.Name): SKILL.md がありません"; continue }
    $text = Get-Content $skillMd -Raw -Encoding UTF8
    if ($text -notmatch '(?s)^﻿?---\r?\n(.*?)\r?\n---') { Write-Warning "$($dir.Name): frontmatter がありません"; continue }
    $fm = $Matches[1]
    if ($fm -notmatch '(?m)^name:\s*(.+)$' -or $Matches[1].Trim() -ne $dir.Name) { Write-Warning "$($dir.Name): name がフォルダ名と一致しません"; continue }
    if ($fm -notmatch '(?m)^description:\s*\S') { Write-Warning "$($dir.Name): description がありません"; continue }

    # zip 作成（ルートにスキルフォルダ、区切りは / ）
    $zip = Join-Path $distDir "$($dir.Name).zip"
    if (Test-Path $zip) { Remove-Item $zip }
    $archive = [IO.Compression.ZipFile]::Open($zip, 'Create')
    try {
        Get-ChildItem $dir.FullName -Recurse -File |
            Where-Object { $exclude -notcontains $_.Name -and $_.FullName -notmatch '__pycache__' } |
            ForEach-Object {
                $entry = $_.FullName.Substring($skillsDir.Length + 1) -replace '\\', '/'
                [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entry)
            }
    } finally { $archive.Dispose() }
    Write-Host "OK: dist\$($dir.Name).zip"
}
