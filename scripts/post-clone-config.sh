#!/bin/bash
# =============================================================================
# post-clone-config.sh
# Customizes cloned sites with niche-specific branding
# Run AFTER mass-clone.sh, AFTER DNS is pointed, AFTER SSL is issued
#
# Usage: sudo bash post-clone-config.sh site-configs.csv
#
# site-configs.csv format (comma-separated, no spaces around commas):
#   domain,site_title,tagline,niche_slug,author_name,contact_email
#   bestdogbeds.com,Best Dog Beds HQ,Honest dog bed reviews your pup will love,dog-comfort,Sarah Mitchell,hello@bestdogbeds.com
#   coffeemakerguide.com,Coffee Maker Guide,Find your perfect brew,home-coffee,James Park,hello@coffeemakerguide.com
#
# What this script does per site:
#   1. Updates site title + tagline
#   2. Creates author profile with credentials
#   3. Customizes About page with niche-specific content
#   4. Updates contact email in legal pages
#   5. Sets up niche-specific categories (adds sub-categories)
#   6. Configures Rank Math meta
# =============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: sudo bash post-clone-config.sh site-configs.csv"
    exit 1
fi

CONFIG_FILE="$1"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

echo "============================================"
echo "Post-Clone Configuration"
echo "============================================"
echo ""

# Skip header line
FIRST_LINE=true

while IFS=',' read -r DOMAIN SITE_TITLE TAGLINE NICHE_SLUG AUTHOR_NAME CONTACT_EMAIL; do
    # Skip header
    if $FIRST_LINE; then
        FIRST_LINE=false
        [[ "$DOMAIN" == "domain" ]] && continue
    fi

    # Skip empty lines and comments
    [ -z "$DOMAIN" ] && continue
    [[ "$DOMAIN" =~ ^# ]] && continue

    WP_PATH="/home/${DOMAIN}/public_html"

    if [ ! -d "$WP_PATH" ]; then
        echo "SKIP: ${DOMAIN} — WP path not found"
        continue
    fi

    echo "--- Configuring: ${DOMAIN} ---"

    # -----------------------------------------------------------------
    # 1. Site title + tagline
    # -----------------------------------------------------------------
    wp option update blogname "$SITE_TITLE" --path="$WP_PATH" --allow-root
    wp option update blogdescription "$TAGLINE" --path="$WP_PATH" --allow-root
    echo "  Title: ${SITE_TITLE}"

    # -----------------------------------------------------------------
    # 2. Create/update author profile
    # -----------------------------------------------------------------
    # Check if author user exists (not admin)
    AUTHOR_SLUG=$(echo "$AUTHOR_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    if ! wp user get "$AUTHOR_SLUG" --path="$WP_PATH" --allow-root 2>/dev/null; then
        AUTHOR_PASS=$(openssl rand -base64 12)
        wp user create "$AUTHOR_SLUG" "${CONTACT_EMAIL}" \
            --role=author \
            --display_name="$AUTHOR_NAME" \
            --user_pass="$AUTHOR_PASS" \
            --path="$WP_PATH" --allow-root
        echo "  Author created: ${AUTHOR_NAME} (${AUTHOR_SLUG})"
    fi

    # Set author bio
    AUTHOR_ID=$(wp user get "$AUTHOR_SLUG" --field=ID --path="$WP_PATH" --allow-root)
    wp user meta update "$AUTHOR_ID" description \
        "${AUTHOR_NAME} is the lead reviewer at ${SITE_TITLE}. With years of hands-on product testing experience, ${AUTHOR_NAME} helps readers find the best products through thorough research and honest reviews." \
        --path="$WP_PATH" --allow-root

    # -----------------------------------------------------------------
    # 3. Update About page with niche content
    # -----------------------------------------------------------------
    ABOUT_ID=$(wp post list --post_type=page --name=about --field=ID --path="$WP_PATH" --allow-root 2>/dev/null || echo "")
    if [ -n "$ABOUT_ID" ]; then
        wp post update "$ABOUT_ID" --post_content="<p>Welcome to ${SITE_TITLE}.</p>
<p>We help you find the best products without the guesswork. Our team researches, compares, and tests products so you can make confident buying decisions.</p>
<p>Every recommendation on this site is based on thorough research, real user feedback, and hands-on experience where possible. We are not paid by manufacturers to feature their products.</p>
<p>Questions? Reach out at <a href=\"mailto:${CONTACT_EMAIL}\">${CONTACT_EMAIL}</a>.</p>" \
            --path="$WP_PATH" --allow-root
        echo "  About page updated"
    fi

    # -----------------------------------------------------------------
    # 4. Update contact email across legal pages
    # -----------------------------------------------------------------
    # Replace placeholder in all pages
    wp search-replace '[CONTACT_EMAIL]' "$CONTACT_EMAIL" \
        --path="$WP_PATH" --allow-root --quiet 2>/dev/null || true
    wp search-replace '[SITE_NAME]' "$SITE_TITLE" \
        --path="$WP_PATH" --allow-root --quiet 2>/dev/null || true
    echo "  Legal pages updated with ${CONTACT_EMAIL}"

    # -----------------------------------------------------------------
    # 5. Rank Math homepage meta
    # -----------------------------------------------------------------
    wp option update rank-math-options-homepage '{
        "homepage_title": "'"${SITE_TITLE}"' %sep% '"${TAGLINE}"'",
        "homepage_description": "'"${TAGLINE}"'. Honest reviews, detailed comparisons, and buying guides to help you choose the best products."
    }' --format=json --path="$WP_PATH" --allow-root 2>/dev/null || true
    echo "  Rank Math meta configured"

    # -----------------------------------------------------------------
    # 6. Flush cache
    # -----------------------------------------------------------------
    rm -rf "${WP_PATH}/wp-content/cache/litespeed"/* 2>/dev/null || true
    wp cache flush --path="$WP_PATH" --allow-root 2>/dev/null || true

    echo "  DONE: ${DOMAIN}"
    echo ""

done < "$CONFIG_FILE"

# Restart OLS to clear opcache for all sites
killall -9 lsphp 2>/dev/null || true
systemctl restart lsws

echo "============================================"
echo "Post-Clone Configuration Complete"
echo "============================================"
