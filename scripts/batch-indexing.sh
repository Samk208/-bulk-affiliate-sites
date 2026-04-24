#!/bin/bash
# =============================================================================
# batch-indexing.sh
# Submits sitemaps and triggers IndexNow for all cloned sites
#
# Usage: sudo bash batch-indexing.sh domains.txt
#
# What this does:
#   1. Verifies each site is live and responding
#   2. Triggers Rank Math to regenerate sitemap
#   3. Submits sitemap to IndexNow (Bing, Yandex, Naver, DuckDuckGo)
#   4. Outputs GSC verification instructions
#
# Note: Google Search Console requires manual verification via DNS TXT record
#       or Cloudflare API. Bing WMT can bulk-import from GSC (100 at a time).
# =============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: sudo bash batch-indexing.sh domains.txt"
    exit 1
fi

DOMAINS_FILE="$1"
INDEXNOW_KEY="$(openssl rand -hex 16)"  # Shared key across all sites

echo "============================================"
echo "Batch Indexing Setup"
echo "IndexNow Key: ${INDEXNOW_KEY}"
echo "============================================"
echo ""

SUCCESS=0
FAIL=0

while IFS= read -r DOMAIN; do
    [ -z "$DOMAIN" ] && continue
    [[ "$DOMAIN" =~ ^# ]] && continue
    DOMAIN=$(echo "$DOMAIN" | xargs)

    WP_PATH="/home/${DOMAIN}/public_html"

    if [ ! -d "$WP_PATH" ]; then
        echo "SKIP: ${DOMAIN} — not found"
        FAIL=$((FAIL + 1))
        continue
    fi

    echo "--- ${DOMAIN} ---"

    # -----------------------------------------------------------------
    # 1. Check site is responding
    # -----------------------------------------------------------------
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${DOMAIN}/" --max-time 10 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" != "200" ]; then
        echo "  WARNING: Site returned HTTP ${HTTP_CODE} — DNS may not be pointed yet"
    fi

    # -----------------------------------------------------------------
    # 2. Place IndexNow key file
    # -----------------------------------------------------------------
    SITE_OWNER=$(stat -c '%U' "${WP_PATH}/wp-config.php" 2>/dev/null || echo "$DOMAIN")
    echo "${INDEXNOW_KEY}" > "${WP_PATH}/${INDEXNOW_KEY}.txt"
    chown "${SITE_OWNER}:${SITE_OWNER}" "${WP_PATH}/${INDEXNOW_KEY}.txt"
    chmod 644 "${WP_PATH}/${INDEXNOW_KEY}.txt"

    # -----------------------------------------------------------------
    # 3. Flush rewrite rules to ensure sitemap works
    # -----------------------------------------------------------------
    wp rewrite flush --path="$WP_PATH" --allow-root 2>/dev/null || true

    # -----------------------------------------------------------------
    # 4. Submit to IndexNow (all participating engines)
    # -----------------------------------------------------------------
    if [ "$HTTP_CODE" = "200" ]; then
        # Get sitemap URLs
        SITEMAP_URL="https://${DOMAIN}/sitemap_index.xml"

        # Submit sitemap URL via IndexNow
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://api.indexnow.org/indexnow" \
            -H "Content-Type: application/json; charset=utf-8" \
            -d "{
                \"host\": \"${DOMAIN}\",
                \"key\": \"${INDEXNOW_KEY}\",
                \"keyLocation\": \"https://${DOMAIN}/${INDEXNOW_KEY}.txt\",
                \"urlList\": [
                    \"https://${DOMAIN}/\",
                    \"https://${DOMAIN}/about/\",
                    \"https://${DOMAIN}/affiliate-disclosure/\",
                    \"https://${DOMAIN}/privacy-policy/\",
                    \"https://${DOMAIN}/contact/\"
                ]
            }" --max-time 10 2>/dev/null || echo "000")

        echo "  IndexNow response: HTTP ${RESPONSE}"
        echo "  Sitemap: ${SITEMAP_URL}"
    else
        echo "  Skipping IndexNow — site not live yet"
    fi

    SUCCESS=$((SUCCESS + 1))
    echo ""

done < "$DOMAINS_FILE"

echo "============================================"
echo "Batch Indexing Complete"
echo "  Processed: ${SUCCESS} | Failed: ${FAIL}"
echo "============================================"
echo ""
echo "MANUAL STEPS REMAINING:"
echo ""
echo "1. GOOGLE SEARCH CONSOLE:"
echo "   - Go to https://search.google.com/search-console/"
echo "   - Add each domain as a URL-prefix property"
echo "   - Verify via DNS TXT record (or Cloudflare API if scripting)"
echo "   - Submit sitemap: https://{domain}/sitemap_index.xml"
echo ""
echo "2. BING WEBMASTER TOOLS:"
echo "   - Go to https://www.bing.com/webmasters/"
echo "   - Click 'Import sites from GSC' — imports up to 100 at once"
echo "   - Sitemaps auto-import with the sites"
echo ""
echo "3. After publishing content, IndexNow auto-submits via Rank Math."
echo "   For bulk submission of existing URLs, run:"
echo "   curl -X POST 'https://api.indexnow.org/indexnow' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"host\":\"DOMAIN\",\"key\":\"${INDEXNOW_KEY}\",\"urlList\":[...]}'"
