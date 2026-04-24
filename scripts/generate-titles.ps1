# ============================================================
# Bulk Affiliate Title Generator — OpenRouter + Kimi K2.5
# ============================================================
# Usage: .\scripts\generate-titles.ps1 -Niche "healthy-cooking" -NicheName "Healthy Cooking"
#
# Prerequisites:
#   - .env file with OPENROUTER_API_KEY=sk-or-...
#   - outputs/<niche>/product-universe.md (Step 0 done)
#   - outputs/<niche>/group-a-roundup.txt (Step 2 done)
#   - outputs/<niche>/group-b-info.txt (Step 2 done)
#   - outputs/<niche>/authority-map.txt (Step 3 done)
#
# What it does:
#   1. Reads keyword files + authority map
#   2. Builds a single optimized prompt with all anti-cannibalization rules
#   3. Sends ONE request to Kimi K2.5 via OpenRouter (~$0.02)
#   4. Parses response into roundup-titles.txt, informational-titles.txt, phase2-titles.txt
#   5. Builds bulk-combined.txt
#   6. Runs basic dedup check
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Niche,          # e.g., "healthy-cooking"

    [Parameter(Mandatory=$true)]
    [string]$NicheName,      # e.g., "Healthy Cooking"

    [string]$Model = "moonshotai/kimi-k2.5",
    [int]$MaxTokens = 8000,
    [double]$Temperature = 0.7,
    [int]$RoundupTarget = 130,
    [int]$InfoTarget = 100,
    [switch]$DryRun          # Just build prompt, don't call API
)

$ErrorActionPreference = "Stop"
$baseDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$outputDir = Join-Path $baseDir "outputs\$Niche"

# ---- Load API Key ----
$envFile = Join-Path $baseDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "No .env file found at $envFile. Create it with OPENROUTER_API_KEY=sk-or-..."
    exit 1
}
$envContent = Get-Content $envFile -Encoding UTF8
$apiKeyLine = $envContent | Where-Object { $_ -match "^OPENROUTER_API_KEY=" }
if (-not $apiKeyLine) {
    Write-Error "OPENROUTER_API_KEY not found in .env file"
    exit 1
}
$apiKey = ($apiKeyLine -split "=", 2)[1].Trim()
Write-Host "[OK] API key loaded (${($apiKey.Substring(0,12))}...)" -ForegroundColor Green

# ---- Verify input files exist ----
$requiredFiles = @("product-universe.md", "group-a-roundup.txt", "group-b-info.txt", "authority-map.txt")
foreach ($f in $requiredFiles) {
    $path = Join-Path $outputDir $f
    if (-not (Test-Path $path)) {
        Write-Error "Missing required file: $path`nRun Steps 0-3 first before title generation."
        exit 1
    }
}
Write-Host "[OK] All input files found in $outputDir" -ForegroundColor Green

# ---- Load input data ----
$groupA = (Get-Content (Join-Path $outputDir "group-a-roundup.txt") -Encoding UTF8 |
    Where-Object { $_.Trim() -ne "" }) -join "`n"
$groupB = (Get-Content (Join-Path $outputDir "group-b-info.txt") -Encoding UTF8 |
    Where-Object { $_.Trim() -ne "" }) -join "`n"

# Load authority map (first 200 lines to stay within token budget)
$authorityMap = (Get-Content (Join-Path $outputDir "authority-map.txt") -Encoding UTF8 |
    Select-Object -First 200) -join "`n"

# Load product universe (for cluster names)
$productUniverse = (Get-Content (Join-Path $outputDir "product-universe.md") -Encoding UTF8 |
    Select-Object -First 80) -join "`n"

$groupACount = ($groupA -split "`n").Count
$groupBCount = ($groupB -split "`n").Count
Write-Host "[OK] Keywords loaded: Group A=$groupACount commercial, Group B=$groupBCount informational" -ForegroundColor Green

# ---- Build the prompt ----
$prompt = @"
You are an SEO expert generating ZimmWriter bulk input titles for a $NicheName affiliate site.

OUTPUT FORMAT (every line must match exactly):
Title{outline_focus=buyer persona, max 120 chars}{slug=url-slug}{category=Category}

VALID CATEGORIES (use ONLY these):
Best Products | Reviews | Buying Guides | Comparisons | How-To Guides | Tips & Care

SLUG RULES: lowercase, hyphens only, max 6 words, NO stop words (a the for of in on to and or is with your my at by)

PRODUCT UNIVERSE AND CLUSTERS:
$productUniverse

AUTHORITY MAP (hub-spoke structure):
$authorityMap

TOP COMMERCIAL KEYWORDS (Group A):
$groupA

INFORMATIONAL KEYWORDS (Group B):
$groupB

ANTI-CANNIBALIZATION RULES (CRITICAL — follow these exactly):
- C1: ONE title per unique Google SERP. If two titles would show the same top-10 results, keep only the higher-volume one.
- C2: NEVER generate both "Best X" AND "Best X Review" — they are the same article. Keep "Best X" only.
- C3: NEVER generate both "Best [Product] for [Condition]" (roundup) AND "[Condition] [Product] Guide" (info) — same searcher. Keep the roundup.
- C4: SYNONYM COLLAPSE — before generating, group synonyms and generate ONE title per group:
  Examples: chew-proof/indestructible = 1 title, XXL/XL/extra large = 1 title, portable/travel = 1 title (unless SERPs genuinely differ)
- C5: HOW-TO VARIANT MERGE — "how to help/cure/fix/stop/deal with/get rid of [problem]" = ONE pillar article using the highest-volume verb. NOT 7 separate articles.
- C6: No cross-cluster duplicates. Each product/topic appears in ONE cluster only.
- C7: No literal duplicates. Every title and every slug must be unique.

TARGETS:
ROUNDUP ($RoundupTarget titles): categories Best Products, Reviews, Buying Guides, Comparisons.
  - Min 8 titles per cluster. Cover ALL clusters from the authority map.
  - Include price-bracket titles (under $100, under $200, under $300) where relevant.
  - Include comparison titles (X vs Y) for top competing products.
INFORMATIONAL ($InfoTarget titles): categories How-To Guides, Tips & Care.
  - Min 5 per cluster. These are the topical authority backbone.
  - Cover setup guides, maintenance, troubleshooting, health/ergonomics, buying education.
PHASE 2 (3-5 titles): KD 30+ head terms only. Prefix each line with [PHASE2].
  - These are ultra-competitive generic terms. We publish them later when domain authority builds.

QUALITY RULES:
- outline_focus = buyer INTENT and PROBLEM (never restate the title). Max 120 chars.
  GOOD: "Remote workers with chronic lower back pain seeking lumbar support under $400"
  BAD: "People looking for the best ergonomic office chair"
- No markdown, headers, numbers, bullets, or separators in output — ONLY formatted title lines.
- Each title targets a UNIQUE Google SERP.

OUTPUT ORDER: All roundup titles first, then all informational titles, then phase2 titles.
Separate sections with these exact markers on their own lines:
=== ROUNDUP ===
=== INFORMATIONAL ===
=== PHASE2 ===

BEGIN:
"@

Write-Host "[OK] Prompt built: $($prompt.Length) chars" -ForegroundColor Green

if ($DryRun) {
    $prompt | Set-Content (Join-Path $outputDir "_prompt_preview.txt") -Encoding UTF8
    Write-Host "[DRY RUN] Prompt saved to _prompt_preview.txt. No API call made." -ForegroundColor Yellow
    exit 0
}

# ---- Call OpenRouter API ----
$headers = @{
    "Authorization" = "Bearer $apiKey"
    "Content-Type"  = "application/json; charset=utf-8"
}

$bodyObj = @{
    model       = $Model
    messages    = @(@{ role = "user"; content = $prompt })
    max_tokens  = $MaxTokens
    temperature = $Temperature
}

$bodyJson = $bodyObj | ConvertTo-Json -Depth 10 -Compress

Write-Host "`n[CALLING] $Model via OpenRouter..." -ForegroundColor Cyan
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

try {
    $response = Invoke-RestMethod -Uri "https://openrouter.ai/api/v1/chat/completions" `
        -Method POST -Headers $headers `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($bodyJson)) `
        -TimeoutSec 300

    $stopwatch.Stop()
    $content = $response.choices[0].message.content
    $tokensIn  = $response.usage.prompt_tokens
    $tokensOut = $response.usage.completion_tokens
    $modelUsed = $response.model

    Write-Host "[OK] Response received in $($stopwatch.Elapsed.TotalSeconds.ToString('F1'))s" -ForegroundColor Green
    Write-Host "     Model: $modelUsed" -ForegroundColor Gray
    Write-Host "     Tokens: $tokensIn in / $tokensOut out" -ForegroundColor Gray

    # Estimate cost (Kimi K2.5 pricing)
    $costIn  = ($tokensIn / 1000000) * 0.42
    $costOut = ($tokensOut / 1000000) * 0.42
    $totalCost = $costIn + $costOut
    Write-Host "     Cost: ~`$$($totalCost.ToString('F4'))" -ForegroundColor Gray

} catch {
    $stopwatch.Stop()
    Write-Host "[ERROR] API call failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Response: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    Write-Host "`nFallback: Run this niche through Claude Code session instead." -ForegroundColor Yellow
    exit 1
}

# ---- Save raw response ----
$content | Set-Content (Join-Path $outputDir "_kimi_raw.txt") -Encoding UTF8
Write-Host "[OK] Raw response saved to _kimi_raw.txt" -ForegroundColor Green

# ---- Parse into sections ----
$lines = $content -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match "\{outline_focus=" }

# Split by section markers in raw content
$section = "roundup"
$roundupLines = @()
$infoLines = @()
$phase2Lines = @()

foreach ($line in ($content -split "`n")) {
    $trimmed = $line.Trim()
    if ($trimmed -match "===\s*INFORMATIONAL\s*===") { $section = "info"; continue }
    if ($trimmed -match "===\s*PHASE\s*2\s*===")     { $section = "phase2"; continue }
    if ($trimmed -match "===\s*ROUNDUP\s*===")        { $section = "roundup"; continue }

    if ($trimmed -match "\{outline_focus=") {
        if ($trimmed -match "^\[PHASE2\]") {
            $phase2Lines += ($trimmed -replace "^\[PHASE2\]\s*", "")
        } elseif ($section -eq "phase2") {
            $phase2Lines += ($trimmed -replace "^\[PHASE2\]\s*", "")
        } elseif ($section -eq "info") {
            $infoLines += $trimmed
        } else {
            $roundupLines += $trimmed
        }
    }
}

# Fallback: if section markers weren't used, split by category
if ($roundupLines.Count -eq 0 -and $infoLines.Count -eq 0) {
    Write-Host "[WARN] No section markers found, splitting by category..." -ForegroundColor Yellow
    foreach ($line in $lines) {
        if ($line -match "^\[PHASE2\]") {
            $phase2Lines += ($line -replace "^\[PHASE2\]\s*", "")
        } elseif ($line -match "category=(How-To Guides|Tips & Care)") {
            $infoLines += $line
        } else {
            $roundupLines += $line
        }
    }
}

Write-Host "`n[COUNTS]" -ForegroundColor Cyan
Write-Host "  Roundup:       $($roundupLines.Count) (target: $RoundupTarget)" -ForegroundColor $(if ($roundupLines.Count -ge ($RoundupTarget * 0.8)) { "Green" } else { "Yellow" })
Write-Host "  Informational: $($infoLines.Count) (target: $InfoTarget)" -ForegroundColor $(if ($infoLines.Count -ge ($InfoTarget * 0.8)) { "Green" } else { "Yellow" })
Write-Host "  Phase 2:       $($phase2Lines.Count)" -ForegroundColor Gray
$total = $roundupLines.Count + $infoLines.Count + $phase2Lines.Count
Write-Host "  TOTAL:         $total" -ForegroundColor $(if ($total -ge 200 -and $total -le 270) { "Green" } else { "Yellow" })

# ---- Write output files ----
$roundupLines | Set-Content (Join-Path $outputDir "roundup-titles.txt") -Encoding UTF8
$infoLines    | Set-Content (Join-Path $outputDir "informational-titles.txt") -Encoding UTF8
$phase2Lines  | Set-Content (Join-Path $outputDir "phase2-titles.txt") -Encoding UTF8

# Build combined file
$combined = @()
$combined += "=== ROUNDUP POSTS (paste into ZimmWriter > Product Roundup) ==="
$combined += $roundupLines
$combined += ""
$combined += "=== INFORMATIONAL ARTICLES (paste into ZimmWriter > Bulk Blog Writer) ==="
$combined += $infoLines
$combined += ""
$combined += "=== PHASE 2 TITLES (KD 30+ — publish after site gains authority) ==="
$combined += ($phase2Lines | ForEach-Object { "[PHASE2] $_" })
$combined | Set-Content (Join-Path $outputDir "bulk-combined.txt") -Encoding UTF8

Write-Host "[OK] Files written:" -ForegroundColor Green
Write-Host "     roundup-titles.txt ($($roundupLines.Count) lines)"
Write-Host "     informational-titles.txt ($($infoLines.Count) lines)"
Write-Host "     phase2-titles.txt ($($phase2Lines.Count) lines)"
Write-Host "     bulk-combined.txt ($total lines)"

# ---- Basic dedup check ----
Write-Host "`n[QA] Running dedup check..." -ForegroundColor Cyan
$allSlugs = ($roundupLines + $infoLines + $phase2Lines) | ForEach-Object {
    if ($_ -match "slug=([^}]+)") { $Matches[1] }
}
$dupSlugs = $allSlugs | Group-Object | Where-Object { $_.Count -gt 1 }
if ($dupSlugs.Count -gt 0) {
    Write-Host "[WARN] Duplicate slugs found:" -ForegroundColor Red
    $dupSlugs | ForEach-Object { Write-Host "  - $($_.Name) (x$($_.Count))" -ForegroundColor Red }
} else {
    Write-Host "[OK] 0 duplicate slugs" -ForegroundColor Green
}

# Check roundup/info split
$splitPct = [math]::Round(($roundupLines.Count / ($roundupLines.Count + $infoLines.Count)) * 100, 1)
Write-Host "[OK] Roundup/Info split: $splitPct% / $([math]::Round(100 - $splitPct, 1))%" -ForegroundColor $(if ($splitPct -ge 55 -and $splitPct -le 65) { "Green" } else { "Yellow" })

Write-Host "`n[DONE] Title generation complete for $NicheName" -ForegroundColor Green
Write-Host "Next: Run QA pass in Claude Code session (Step 5)" -ForegroundColor Cyan
