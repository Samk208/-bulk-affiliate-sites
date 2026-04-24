#!/bin/bash
# deploy-to-vps.sh — Deploy bulk affiliate pipeline to Contabo VPS
# Usage: bash deploy/deploy-to-vps.sh
# Requires: SSH access to root@62.84.185.148

set -euo pipefail

VPS_HOST="root@62.84.185.148"
VPS_DIR="/opt/bulk-affiliate"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Bulk Affiliate Pipeline — VPS Deployment ==="
echo "Local: $LOCAL_DIR"
echo "Remote: $VPS_HOST:$VPS_DIR"
echo ""

# ---- Step 1: Create directory structure on VPS ----
echo "[1/6] Creating directory structure on VPS..."
ssh "$VPS_HOST" "mkdir -p $VPS_DIR/{scripts,outputs,logs}"

# ---- Step 2: Copy Python scripts ----
echo "[2/6] Copying Python scripts..."
scp -r "$LOCAL_DIR/scripts/"*.py "$VPS_HOST:$VPS_DIR/scripts/"

# ---- Step 3: Copy niche data (titles, link maps, serp research) ----
echo "[3/6] Copying niche data files..."
for niche_dir in "$LOCAL_DIR/outputs"/*/; do
    niche=$(basename "$niche_dir")
    ssh "$VPS_HOST" "mkdir -p $VPS_DIR/outputs/$niche/articles"

    # Copy input files (NOT generated articles — those stay local until sync)
    for f in informational-titles.txt roundup-titles.txt link-map.json \
             serp-research.json product-universe.md authority-map.txt \
             phase2-titles.txt bulk-combined.txt; do
        if [ -f "$niche_dir/$f" ]; then
            scp "$niche_dir/$f" "$VPS_HOST:$VPS_DIR/outputs/$niche/$f"
        fi
    done
done

# ---- Step 4: Copy generation state ----
echo "[4/6] Copying generation state..."
[ -f "$LOCAL_DIR/generation-state.json" ] && \
    scp "$LOCAL_DIR/generation-state.json" "$VPS_HOST:$VPS_DIR/generation-state.json"
[ -f "$LOCAL_DIR/outputs/generation-schedule.json" ] && \
    scp "$LOCAL_DIR/outputs/generation-schedule.json" "$VPS_HOST:$VPS_DIR/outputs/generation-schedule.json"

# ---- Step 5: Install Python dependencies ----
echo "[5/6] Installing Python dependencies..."
scp "$LOCAL_DIR/deploy/requirements.txt" "$VPS_HOST:$VPS_DIR/requirements.txt"
ssh "$VPS_HOST" "cd $VPS_DIR && pip3 install -r requirements.txt -q"

# ---- Step 6: Create .env.cowork from local keys ----
echo "[6/6] Setting up environment variables..."
if [ -f "$LOCAL_DIR/.env.cowork" ]; then
    scp "$LOCAL_DIR/.env.cowork" "$VPS_HOST:$VPS_DIR/.env.cowork"
    ssh "$VPS_HOST" "chmod 600 $VPS_DIR/.env.cowork"
    echo "  .env.cowork copied and secured (chmod 600)"
else
    echo "  WARNING: No .env.cowork found locally. Copy deploy/.env.vps.template to VPS manually."
fi

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Test with:"
echo "  ssh $VPS_HOST \"cd $VPS_DIR && python3 scripts/serp_researcher.py korean-skincare --limit 2\""
echo "  ssh $VPS_HOST \"cd $VPS_DIR && python3 scripts/article_generator.py korean-skincare --limit 2\""
echo ""
echo "Next steps:"
echo "  1. Import n8n workflows from deploy/n8n-*.json into n8n.kmedtour.com"
echo "  2. Configure n8n credentials (OpenRouter, Perplexity, SMTP)"
echo "  3. Set cron schedules and activate workflows"
echo "  4. Disable Cowork tasks: gen-tier2-session-b, gen-tier2-session-c"
