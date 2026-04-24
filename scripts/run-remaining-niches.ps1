# ============================================================
# Run title generation for all remaining niches
# ============================================================
# Usage: .\scripts\run-remaining-niches.ps1
#
# Prerequisites: Steps 0-3 must be complete for each niche
# (product-universe.md, keywords-raw.csv, group-a/b, authority-map.txt)
#
# This script calls generate-titles.ps1 for each niche sequentially.
# After each niche, run QA (Step 5) in Claude Code before continuing.
# ============================================================

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$genScript = Join-Path $scriptDir "generate-titles.ps1"
$baseDir   = Split-Path -Parent $scriptDir
$outputDir = Join-Path $baseDir "outputs"

# Define remaining niches (update this list as you complete them)
$niches = @(
    @{ Slug = "healthy-cooking";    Name = "Healthy Cooking";       Roundup = 130; Info = 100 }
    @{ Slug = "water-air-quality";  Name = "Water & Air Quality";   Roundup = 110; Info = 90  }
    @{ Slug = "home-cleaning";      Name = "Home Cleaning";         Roundup = 130; Info = 100 }
    @{ Slug = "korean-skincare";    Name = "Korean Skincare";       Roundup = 130; Info = 100 }
    @{ Slug = "makeup-beauty";      Name = "Makeup & Beauty";       Roundup = 130; Info = 100 }
    @{ Slug = "korean-medical-tourism"; Name = "Korean Medical Tourism"; Roundup = 130; Info = 100 }
    @{ Slug = "korean-used-cars";   Name = "Korean Used Cars & Parts"; Roundup = 100; Info = 70 }
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Bulk Affiliate Title Generator" -ForegroundColor Cyan
Write-Host " Remaining niches: $($niches.Count)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

foreach ($niche in $niches) {
    $nicheDir = Join-Path $outputDir $niche.Slug

    # Check if niche output folder exists with required files
    if (-not (Test-Path (Join-Path $nicheDir "group-a-roundup.txt"))) {
        Write-Host "`n[SKIP] $($niche.Name) — Steps 0-3 not complete yet (no group-a-roundup.txt)" -ForegroundColor Yellow
        continue
    }

    # Check if already has titles
    if (Test-Path (Join-Path $nicheDir "bulk-combined.txt")) {
        $lineCount = (Get-Content (Join-Path $nicheDir "bulk-combined.txt") | Where-Object { $_ -match "\{outline_focus=" }).Count
        if ($lineCount -ge 150) {
            Write-Host "`n[SKIP] $($niche.Name) — already has $lineCount titles in bulk-combined.txt" -ForegroundColor Gray
            continue
        }
    }

    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host " Processing: $($niche.Name) ($($niche.Slug))" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    & $genScript -Niche $niche.Slug -NicheName $niche.Name `
        -RoundupTarget $niche.Roundup -InfoTarget $niche.Info

    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[ERROR] $($niche.Name) failed. Fix the issue and rerun." -ForegroundColor Red
        Write-Host "Stopping batch. Completed niches above are saved." -ForegroundColor Yellow
        exit 1
    }

    Write-Host "`n[PAUSE] $($niche.Name) titles generated." -ForegroundColor Green
    Write-Host "Run QA pass (Step 5) in Claude Code before continuing." -ForegroundColor Yellow
    $continue = Read-Host "Continue to next niche? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Stopped. Resume by running this script again (completed niches auto-skip)." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " ALL NICHES COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Next: Run validation-summary.md QA for each niche in Claude Code"
