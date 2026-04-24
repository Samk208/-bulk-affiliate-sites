#!/bin/bash
# =============================================================================
# mass-clone.sh
# Clones the golden template to every domain in a file
# Based on wp-cyberpanel-deploy skill patterns (permissions, cache layers, lsphp)
#
# Usage: sudo bash mass-clone.sh domains.txt
#
# domains.txt format (one domain per line):
#   bestdogbeds.com
#   coffeemakerguide.com
#   mensgroomhub.com
#
# Prerequisites:
#   - Golden template built via build-golden-template.sh
#   - WP-CLI installed
#   - CyberPanel running
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION — Match these to your golden template
# =============================================================================
SOURCE_DOMAIN="golden-template.com"
SOURCE_PATH="/home/${SOURCE_DOMAIN}/public_html"
MYSQL_ROOT_PASS=""                # Your MySQL root password (empty if using socket auth)
ADMIN_USER="admin"                # WP admin user for cloned sites
ADMIN_PASS="$(openssl rand -base64 16)"  # Shared initial password (change per site if needed)
ADMIN_EMAIL="admin@example.com"

# Detect lsphp path
LSPHP_BIN=$(ls /usr/local/lsws/lsphp*/bin/php 2>/dev/null | tail -1 || echo "/usr/local/lsws/lsphp81/bin/php")

# =============================================================================
# VALIDATION
# =============================================================================
if [ $# -lt 1 ]; then
    echo "Usage: sudo bash mass-clone.sh domains.txt"
    exit 1
fi

DOMAINS_FILE="$1"
if [ ! -f "$DOMAINS_FILE" ]; then
    echo "ERROR: File not found: $DOMAINS_FILE"
    exit 1
fi

if [ ! -d "$SOURCE_PATH" ]; then
    echo "ERROR: Golden template not found at $SOURCE_PATH"
    echo "Run build-golden-template.sh first."
    exit 1
fi

# =============================================================================
# EXPORT GOLDEN TEMPLATE DATABASE (once)
# =============================================================================
echo "Exporting golden template database..."
DUMP_FILE="/tmp/golden_template_$(date +%s).sql"
wp db export "$DUMP_FILE" --path="$SOURCE_PATH" --allow-root
echo "  Database exported to $DUMP_FILE"

# =============================================================================
# CLONE LOOP
# =============================================================================
CLONE_COUNT=0
FAIL_COUNT=0
CREDENTIALS_LOG="/root/cloned-sites-$(date +%Y%m%d_%H%M%S).txt"

echo ""
echo "============================================"
echo "Starting mass clone from: ${SOURCE_DOMAIN}"
echo "Domains file: ${DOMAINS_FILE}"
echo "Credentials log: ${CREDENTIALS_LOG}"
echo "============================================"
echo ""

while IFS= read -r TARGET_DOMAIN; do
    # Skip empty lines and comments
    [ -z "$TARGET_DOMAIN" ] && continue
    [[ "$TARGET_DOMAIN" =~ ^# ]] && continue

    # Trim whitespace
    TARGET_DOMAIN=$(echo "$TARGET_DOMAIN" | xargs)

    TARGET_PATH="/home/${TARGET_DOMAIN}/public_html"
    CLONE_START=$(date +%s)

    echo "--- Cloning: ${TARGET_DOMAIN} ---"

    # Generate unique DB credentials
    DB_NAME=$(echo "${TARGET_DOMAIN}" | tr '.-' '__' | cut -c1-16)_db
    DB_USER=$(echo "${TARGET_DOMAIN}" | tr '.-' '__' | cut -c1-14)_u
    DB_PASS=$(openssl rand -base64 16)

    # -----------------------------------------------------------------
    # Step 1: Create CyberPanel website
    # -----------------------------------------------------------------
    echo "  [1/7] Creating CyberPanel site..."
    cyberpanel createWebsite --package BulkAffiliate --owner admin \
        --domainName "$TARGET_DOMAIN" --email "admin@${TARGET_DOMAIN}" \
        --php 8.1 --ssl 1 --dkim 0 --openBasedir 1 2>&1 || {
        echo "  ERROR: CyberPanel createWebsite failed for ${TARGET_DOMAIN}. Skipping."
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    }

    # -----------------------------------------------------------------
    # Step 2: Create database
    # -----------------------------------------------------------------
    echo "  [2/7] Creating database..."
    mysql -u root ${MYSQL_ROOT_PASS:+-p"$MYSQL_ROOT_PASS"} -e "
        CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`;
        DROP USER IF EXISTS '${DB_USER}'@'localhost';
        CREATE USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
        GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
        FLUSH PRIVILEGES;" 2>&1 || {
        echo "  ERROR: Database creation failed for ${TARGET_DOMAIN}. Skipping."
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    }

    # -----------------------------------------------------------------
    # Step 3: Copy files from golden template
    # -----------------------------------------------------------------
    echo "  [3/7] Copying files..."
    rsync -a --delete "${SOURCE_PATH}/" "${TARGET_PATH}/"

    # -----------------------------------------------------------------
    # Step 4: Update wp-config.php with new DB credentials
    # -----------------------------------------------------------------
    echo "  [4/7] Updating wp-config.php..."
    sed -i "s/define( *'DB_NAME'.*/define( 'DB_NAME', '${DB_NAME}' );/" "${TARGET_PATH}/wp-config.php"
    sed -i "s/define( *'DB_USER'.*/define( 'DB_USER', '${DB_USER}' );/" "${TARGET_PATH}/wp-config.php"
    sed -i "s/define( *'DB_PASSWORD'.*/define( 'DB_PASSWORD', '${DB_PASS}' );/" "${TARGET_PATH}/wp-config.php"

    # Generate fresh salts
    SALTS=$(curl -s https://api.wordpress.org/secret-key/1.1/salt/)
    if [ -n "$SALTS" ]; then
        # Remove old salts and append new ones
        sed -i "/AUTH_KEY/d;/SECURE_AUTH_KEY/d;/LOGGED_IN_KEY/d;/NONCE_KEY/d;/AUTH_SALT/d;/SECURE_AUTH_SALT/d;/LOGGED_IN_SALT/d;/NONCE_SALT/d" "${TARGET_PATH}/wp-config.php"
        # Insert before "That's all" comment
        sed -i "/That's all, stop editing/i\\${SALTS}" "${TARGET_PATH}/wp-config.php" 2>/dev/null || true
    fi

    # -----------------------------------------------------------------
    # Step 5: Import database + search-replace URLs
    # -----------------------------------------------------------------
    echo "  [5/7] Importing database + URL replacement..."
    wp db import "$DUMP_FILE" --path="$TARGET_PATH" --allow-root
    wp search-replace "$SOURCE_DOMAIN" "$TARGET_DOMAIN" \
        --all-tables --path="$TARGET_PATH" --allow-root --quiet
    wp search-replace "http://${TARGET_DOMAIN}" "https://${TARGET_DOMAIN}" \
        --all-tables --path="$TARGET_PATH" --allow-root --quiet

    # Update site title and admin
    wp option update blogname "$TARGET_DOMAIN" --path="$TARGET_PATH" --allow-root
    wp option update blogdescription "" --path="$TARGET_PATH" --allow-root

    # -----------------------------------------------------------------
    # Step 6: Fix permissions (wp-cyberpanel-deploy critical rule #1 & #2)
    # -----------------------------------------------------------------
    echo "  [6/7] Fixing permissions..."

    # CyberPanel creates a site-specific user — detect it
    SITE_OWNER=$(stat -c '%U' /home/${TARGET_DOMAIN}/ 2>/dev/null || echo "$TARGET_DOMAIN")

    chown -R "${SITE_OWNER}:${SITE_OWNER}" "$TARGET_PATH"
    find "$TARGET_PATH" -type d -exec chmod 755 {} \;
    find "$TARGET_PATH" -type f -exec chmod 644 {} \;

    # -----------------------------------------------------------------
    # Step 7: Flush cache + add system cron
    # -----------------------------------------------------------------
    echo "  [7/7] Flushing cache + setting up cron..."

    # Clear all 3 cache layers (wp-cyberpanel-deploy pattern)
    rm -rf "${TARGET_PATH}/wp-content/cache/litespeed"/* 2>/dev/null || true
    rm -rf "${TARGET_PATH}/wp-content/litespeed/ccss"/* 2>/dev/null || true
    rm -rf "${TARGET_PATH}/wp-content/litespeed/ucss"/* 2>/dev/null || true
    rm -rf "${TARGET_PATH}/wp-content/litespeed/css"/* 2>/dev/null || true
    rm -rf "${TARGET_PATH}/wp-content/litespeed/js"/* 2>/dev/null || true

    wp rewrite flush --path="$TARGET_PATH" --allow-root
    wp cache flush --path="$TARGET_PATH" --allow-root

    # Add system cron for this site
    CRON_LINE="*/5 * * * * cd ${TARGET_PATH} && ${LSPHP_BIN} wp-cron.php >/dev/null 2>&1"
    (crontab -l 2>/dev/null | grep -v "${TARGET_DOMAIN}"; echo "${CRON_LINE}") | crontab -

    # -----------------------------------------------------------------
    # Done — log credentials
    # -----------------------------------------------------------------
    CLONE_END=$(date +%s)
    ELAPSED=$((CLONE_END - CLONE_START))
    CLONE_COUNT=$((CLONE_COUNT + 1))

    echo "${TARGET_DOMAIN} | DB: ${DB_NAME} | DBUser: ${DB_USER} | DBPass: ${DB_PASS} | Admin: ${ADMIN_USER}/${ADMIN_PASS}" >> "$CREDENTIALS_LOG"

    echo "  DONE: ${TARGET_DOMAIN} (${ELAPSED}s)"
    echo ""

done < "$DOMAINS_FILE"

# =============================================================================
# CLEANUP + RESTART
# =============================================================================
rm -f "$DUMP_FILE"

# Restart OLS once at the end (not per-site — saves time)
echo "Restarting OpenLiteSpeed..."
killall -9 lsphp 2>/dev/null || true
systemctl restart lsws

echo ""
echo "============================================"
echo "Mass Clone Complete"
echo "============================================"
echo "  Cloned:  ${CLONE_COUNT} sites"
echo "  Failed:  ${FAIL_COUNT} sites"
echo "  Creds:   ${CREDENTIALS_LOG}"
echo ""
echo "NEXT STEPS:"
echo "  1. Point each domain's DNS to this server IP"
echo "  2. Run: sudo bash post-clone-config.sh domains.txt"
echo "  3. Verify SSL: cyberpanel issueSSL --domainName {domain}"
echo "  4. Import content via ZimmWriter Bulk Importer"
echo "============================================"
