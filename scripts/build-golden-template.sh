#!/bin/bash
# =============================================================================
# build-golden-template.sh
# Creates the golden template WordPress site on CyberPanel/OpenLiteSpeed
# Run ONCE on your VPS. All future sites clone from this template.
#
# Usage: sudo bash build-golden-template.sh
#
# Prerequisites:
#   - CyberPanel installed with OpenLiteSpeed
#   - WP-CLI installed: curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && sudo mv wp-cli.phar /usr/local/bin/wp
#   - GeneratePress Premium ZIP downloaded to /root/generatepress-premium.zip
#   - wp-ai-affiliate plugin ZIP at /root/wp-ai-affiliate.zip (your custom plugin)
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION — Edit these values
# =============================================================================
TEMPLATE_DOMAIN="golden-template.com"        # Domain for the template site
ADMIN_USER="admin"                           # WP admin username
ADMIN_PASS="$(openssl rand -base64 20)"      # Auto-generated secure password
ADMIN_EMAIL="admin@example.com"              # WP admin email
SITE_TITLE="Affiliate Site"                  # Default title (overridden per clone)
MYSQL_ROOT_PASS=""                           # Your MySQL root password

# Theme & plugin files (upload these to /root/ before running)
GP_PREMIUM_ZIP="/root/generatepress-premium.zip"
AI_AFFILIATE_ZIP="/root/wp-ai-affiliate.zip"

# Amazon affiliate config (leave blank if not ready yet)
AMAZON_TRACKING_ID=""                        # e.g., yourtag-20
AMAZON_ACCESS_KEY=""
AMAZON_SECRET_KEY=""

# =============================================================================
# DERIVED VALUES — Don't edit
# =============================================================================
WP_PATH="/home/${TEMPLATE_DOMAIN}/public_html"
DB_NAME="golden_template_db"
DB_USER="golden_template_u"
DB_PASS="$(openssl rand -base64 16)"

echo "============================================"
echo "Building Golden Template: ${TEMPLATE_DOMAIN}"
echo "============================================"

# =============================================================================
# STEP 1: Create CyberPanel website + database
# =============================================================================
echo "[1/10] Creating CyberPanel website..."

# Create hosting package if it doesn't exist
cyberpanel createPackage --packageName BulkAffiliate \
    --diskSpace 5000 --bandwidth 50000 --ftpAccounts 1 \
    --dataBases 1 --emails 1 2>/dev/null || true

# Create website
cyberpanel createWebsite --package BulkAffiliate --owner admin \
    --domainName "$TEMPLATE_DOMAIN" --email "$ADMIN_EMAIL" \
    --php 8.1 --ssl 0 --dkim 0 --openBasedir 1

# Create database
echo "[1/10] Creating database..."
mysql -u root ${MYSQL_ROOT_PASS:+-p"$MYSQL_ROOT_PASS"} -e "
    CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`;
    CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
    GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
    FLUSH PRIVILEGES;"

# =============================================================================
# STEP 2: Install WordPress via WP-CLI
# =============================================================================
echo "[2/10] Installing WordPress..."

# Clean the public_html directory
rm -rf "${WP_PATH:?}"/*

# Download and install WP
wp core download --path="$WP_PATH" --allow-root
wp config create \
    --path="$WP_PATH" \
    --dbname="$DB_NAME" \
    --dbuser="$DB_USER" \
    --dbpass="$DB_PASS" \
    --dbhost="localhost" \
    --allow-root

# Add performance constants to wp-config.php
wp config set WP_POST_REVISIONS 3 --raw --path="$WP_PATH" --allow-root
wp config set AUTOSAVE_INTERVAL 300 --raw --path="$WP_PATH" --allow-root
wp config set WP_MEMORY_LIMIT "'256M'" --raw --path="$WP_PATH" --allow-root
wp config set WP_MAX_MEMORY_LIMIT "'512M'" --raw --path="$WP_PATH" --allow-root
wp config set DISALLOW_FILE_EDIT true --raw --path="$WP_PATH" --allow-root

wp core install \
    --path="$WP_PATH" \
    --url="https://${TEMPLATE_DOMAIN}" \
    --title="$SITE_TITLE" \
    --admin_user="$ADMIN_USER" \
    --admin_password="$ADMIN_PASS" \
    --admin_email="$ADMIN_EMAIL" \
    --skip-email \
    --allow-root

echo "  WP Admin: ${ADMIN_USER} / ${ADMIN_PASS}"

# =============================================================================
# STEP 3: Install GeneratePress + GP Premium
# =============================================================================
echo "[3/10] Installing GeneratePress theme..."

# Install free GeneratePress from WP.org
wp theme install generatepress --activate --path="$WP_PATH" --allow-root

# Install GP Premium from local ZIP
if [ -f "$GP_PREMIUM_ZIP" ]; then
    wp plugin install "$GP_PREMIUM_ZIP" --activate --path="$WP_PATH" --allow-root
    echo "  GP Premium installed and activated"
else
    echo "  WARNING: GP Premium ZIP not found at ${GP_PREMIUM_ZIP}"
    echo "  Upload it later and activate manually"
fi

# Remove default themes to save space
wp theme delete twentytwentyfive twentytwentyfour twentytwentythree --path="$WP_PATH" --allow-root 2>/dev/null || true

# =============================================================================
# STEP 4: Install required plugins
# =============================================================================
echo "[4/10] Installing plugins..."

# Rank Math SEO (free — includes IndexNow)
wp plugin install seo-by-rank-math --activate --path="$WP_PATH" --allow-root

# LiteSpeed Cache
wp plugin install litespeed-cache --activate --path="$WP_PATH" --allow-root

# WP Affiliate Disclosure (auto FTC text on every post)
wp plugin install flavor --activate --path="$WP_PATH" --allow-root 2>/dev/null || echo "  Note: Install WP Affiliate Disclosure manually if not in WP.org repo"

# Custom Amazon affiliate plugin
if [ -f "$AI_AFFILIATE_ZIP" ]; then
    wp plugin install "$AI_AFFILIATE_ZIP" --activate --path="$WP_PATH" --allow-root
    echo "  wp-ai-affiliate installed and activated"
else
    echo "  WARNING: wp-ai-affiliate ZIP not found at ${AI_AFFILIATE_ZIP}"
    echo "  Upload it later and activate manually"
fi

# Remove default plugins
wp plugin delete hello akismet --path="$WP_PATH" --allow-root 2>/dev/null || true

# =============================================================================
# STEP 5: Configure WordPress settings
# =============================================================================
echo "[5/10] Configuring WordPress settings..."

# Permalinks — post name structure (required for SEO)
wp rewrite structure '/%postname%/' --path="$WP_PATH" --allow-root
wp rewrite flush --path="$WP_PATH" --allow-root

# Timezone
wp option update timezone_string 'America/New_York' --path="$WP_PATH" --allow-root

# Discussion — disable comments (affiliate sites don't need them)
wp option update default_comment_status 'closed' --path="$WP_PATH" --allow-root
wp option update default_ping_status 'closed' --path="$WP_PATH" --allow-root

# Reading — show full posts, not excerpts
wp option update rss_use_excerpt 0 --path="$WP_PATH" --allow-root

# Uploads — organize by year/month
wp option update uploads_use_yearmonth_org 1 --path="$WP_PATH" --allow-root

# Remove sample content
wp post delete 1 2 --force --path="$WP_PATH" --allow-root 2>/dev/null || true
wp comment delete 1 --force --path="$WP_PATH" --allow-root 2>/dev/null || true

# =============================================================================
# STEP 6: Create category taxonomy
# =============================================================================
echo "[6/10] Creating categories..."

# Delete default "Uncategorized" and set a proper default
REVIEWS_ID=$(wp term create category "Reviews" --slug=reviews --description="In-depth product reviews" --porcelain --path="$WP_PATH" --allow-root)
wp term create category "Buying Guides" --slug=buying-guides --description="Comprehensive buying guides" --path="$WP_PATH" --allow-root
wp term create category "Best Products" --slug=best-products --description="Best product roundups" --path="$WP_PATH" --allow-root
wp term create category "How-To Guides" --slug=how-to-guides --description="Step-by-step how-to guides" --path="$WP_PATH" --allow-root
wp term create category "Comparisons" --slug=comparisons --description="Product comparisons and vs articles" --path="$WP_PATH" --allow-root
wp term create category "Tips & Care" --slug=tips-care --description="Product tips, maintenance, and care" --path="$WP_PATH" --allow-root

# Set Reviews as default category, then delete Uncategorized
wp option update default_category "$REVIEWS_ID" --path="$WP_PATH" --allow-root
wp term delete category 1 --path="$WP_PATH" --allow-root 2>/dev/null || true

echo "  Categories created: Reviews, Buying Guides, Best Products, How-To Guides, Comparisons, Tips & Care"

# =============================================================================
# STEP 7: Create legal pages
# =============================================================================
echo "[7/10] Creating legal pages..."

# Privacy Policy
wp post create --post_type=page --post_title='Privacy Policy' --post_status=publish \
    --post_content='<!-- Privacy Policy — will be customized per-site by post-clone script -->
<h2>Who We Are</h2>
<p>This website is an independently operated product review and recommendation site. We are not affiliated with Amazon or any product manufacturer.</p>

<h2>What Data We Collect</h2>
<p>We do not collect personal information directly. Our site uses:</p>
<ul>
<li><strong>Google Analytics</strong> — anonymous traffic data (pages visited, time on site, device type)</li>
<li><strong>Cookies</strong> — affiliate tracking cookies from Amazon Associates and advertising partners</li>
<li><strong>Server logs</strong> — standard web server access logs (IP address, browser type, referring URL)</li>
</ul>

<h2>Affiliate Links &amp; Cookies</h2>
<p>This site participates in the Amazon Services LLC Associates Program. When you click affiliate links and make a purchase, a cookie is placed by Amazon to track the referral. This cookie does not collect personal information.</p>

<h2>Third-Party Services</h2>
<p>We may use advertising networks that place cookies for ad targeting. You can opt out of personalized advertising at <a href="https://www.aboutads.info/choices/">aboutads.info/choices</a>.</p>

<h2>Your Rights</h2>
<p>Under GDPR and CCPA, you have the right to request access to, deletion of, or restriction of your data. Contact us at the email below for any privacy-related requests.</p>

<h2>Contact</h2>
<p>For privacy questions, email: [CONTACT_EMAIL]</p>' \
    --path="$WP_PATH" --allow-root

# Affiliate Disclosure
wp post create --post_type=page --post_title='Affiliate Disclosure' --post_status=publish \
    --post_content='<p><strong>As an Amazon Associate I earn from qualifying purchases.</strong></p>
<p>This site contains affiliate links to products. We may receive a commission for purchases made through these links at no extra cost to you. This helps us keep the site running and continue providing honest product recommendations.</p>
<p>Our editorial content is not influenced by affiliate partnerships. We recommend products based on research, testing, and reader feedback — not commission rates.</p>' \
    --path="$WP_PATH" --allow-root

# About Page
wp post create --post_type=page --post_title='About' --post_status=publish \
    --post_content='<!-- About page — will be customized per-site by post-clone script -->
<p>Welcome to [SITE_NAME].</p>
<p>We help you find the best products without the guesswork. Our team researches, compares, and tests products so you can make confident buying decisions.</p>
<p>Every recommendation on this site is based on thorough research, real user feedback, and hands-on experience where possible. We are not paid by manufacturers to feature their products.</p>
<p>Have a question or suggestion? Reach out at [CONTACT_EMAIL].</p>' \
    --path="$WP_PATH" --allow-root

# Contact Page
wp post create --post_type=page --post_title='Contact' --post_status=publish \
    --post_content='<p>Have a question, correction, or partnership inquiry?</p>
<p>Email us at: <strong>[CONTACT_EMAIL]</strong></p>
<p>We typically respond within 48 hours.</p>' \
    --path="$WP_PATH" --allow-root

# Terms of Service
wp post create --post_type=page --post_title='Terms of Service' --post_status=publish \
    --post_content='<h2>Agreement</h2>
<p>By using this website, you agree to these terms. If you do not agree, please do not use the site.</p>

<h2>Content Accuracy</h2>
<p>We strive to provide accurate product information, but prices, availability, and specifications change frequently. Always verify details on the retailer site before purchasing.</p>

<h2>Affiliate Links</h2>
<p>This site contains affiliate links. Clicking these links and making purchases may earn us a commission. See our <a href="/affiliate-disclosure/">Affiliate Disclosure</a> for details.</p>

<h2>Limitation of Liability</h2>
<p>This site provides general product recommendations and information only. We are not liable for purchasing decisions made based on our content.</p>

<h2>Changes</h2>
<p>We may update these terms at any time. Continued use of the site constitutes acceptance of any changes.</p>' \
    --path="$WP_PATH" --allow-root

echo "  Pages created: Privacy Policy, Affiliate Disclosure, About, Contact, Terms of Service"

# =============================================================================
# STEP 8: Configure Rank Math (basic settings via WP-CLI)
# =============================================================================
echo "[8/10] Configuring Rank Math SEO..."

# Enable modules
wp option update rank_math_modules '["sitemap","seo-analysis","rich-snippet","instant-indexing","link-counter"]' --format=json --path="$WP_PATH" --allow-root 2>/dev/null || true

# Set default SEO title format
wp option update rank-math-options-titles '{
    "title_separator": "-",
    "homepage_title": "%sitename% %sep% %sitedesc%",
    "post_title": "%title% %sep% %sitename%",
    "page_title": "%title% %sep% %sitename%",
    "author_archive_title": "%name% %sep% %sitename%",
    "noindex_empty_taxonomies": "on",
    "noindex_post_tag": "on",
    "noindex_post_format": "on"
}' --format=json --path="$WP_PATH" --allow-root 2>/dev/null || true

echo "  Rank Math basic config applied. Import full JSON settings after first login."
echo "  NOTE: Enable IndexNow module in Rank Math > Dashboard > Modules"

# =============================================================================
# STEP 9: Fix permissions + PHP config + cron
# =============================================================================
echo "[9/10] Fixing permissions, PHP config, and cron..."

# Find the actual CyberPanel site user (not always the domain name)
SITE_OWNER=$(stat -c '%U' "$WP_PATH/wp-config.php" 2>/dev/null || echo "$TEMPLATE_DOMAIN")
echo "  Site owner detected: ${SITE_OWNER}"

# Fix ownership — MUST be site user, NOT root (wp-cyberpanel-deploy skill rule #1)
chown -R "${SITE_OWNER}:${SITE_OWNER}" "$WP_PATH"
find "$WP_PATH" -type d -exec chmod 755 {} \;
find "$WP_PATH" -type f -exec chmod 644 {} \;

# PHP overrides via .user.ini
cat > "${WP_PATH}/.user.ini" << 'PHPINI'
upload_max_filesize = 512M
post_max_size = 512M
memory_limit = 512M
max_execution_time = 300
PHPINI
chown "${SITE_OWNER}:${SITE_OWNER}" "${WP_PATH}/.user.ini"

# Disable WP-Cron (use system cron instead — more reliable)
wp config set DISABLE_WP_CRON true --raw --path="$WP_PATH" --allow-root

# Add system cron for this template site
LSPHP_BIN=$(ls /usr/local/lsws/lsphp*/bin/php 2>/dev/null | tail -1 || echo "/usr/local/lsws/lsphp81/bin/php")
CRON_LINE="*/5 * * * * cd ${WP_PATH} && ${LSPHP_BIN} wp-cron.php >/dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v "${TEMPLATE_DOMAIN}"; echo "${CRON_LINE}") | crontab -

# Restart OLS to pick up .user.ini and clear opcache
killall -9 lsphp 2>/dev/null || true
systemctl restart lsws

# =============================================================================
# STEP 10: Final verification
# =============================================================================
echo "[10/10] Verifying installation..."

echo ""
echo "  WordPress version: $(wp core version --path="$WP_PATH" --allow-root)"
echo "  Active theme:      $(wp theme list --status=active --field=name --path="$WP_PATH" --allow-root)"
echo "  Active plugins:"
wp plugin list --status=active --fields=name,version --path="$WP_PATH" --allow-root
echo ""
echo "  Categories:"
wp term list category --fields=term_id,name,slug --path="$WP_PATH" --allow-root
echo ""
echo "  Pages:"
wp post list --post_type=page --fields=ID,post_title,post_status --path="$WP_PATH" --allow-root

echo ""
echo "============================================"
echo "Golden Template Build Complete!"
echo "============================================"
echo ""
echo "  Domain:     ${TEMPLATE_DOMAIN}"
echo "  WP Admin:   https://${TEMPLATE_DOMAIN}/wp-admin/"
echo "  Username:   ${ADMIN_USER}"
echo "  Password:   ${ADMIN_PASS}"
echo "  DB Name:    ${DB_NAME}"
echo "  DB User:    ${DB_USER}"
echo "  DB Pass:    ${DB_PASS}"
echo ""
echo "NEXT STEPS (manual — must be done in WP Admin UI):"
echo ""
echo "  1. Log in to WP Admin: https://${TEMPLATE_DOMAIN}/wp-admin/"
echo ""
echo "  2. ACTIVATE GP PREMIUM LICENSE:"
echo "     Appearance > GeneratePress > click 'Updates' tab > enter license key"
echo "     License: $59/yr from generatepress.com (covers 500 sites)"
echo ""
echo "  3. IMPORT MARKETER STARTER SITE:"
echo "     Appearance > GeneratePress > Site Library tab"
echo "     Find 'Marketer' > click Import"
echo "     This sets up: blog homepage, content+sidebar layout, clean nav"
echo "     (Alternative: 'Scribe' if you prefer hero post + 3-col grid)"
echo ""
echo "  4. CONFIGURE RANK MATH:"
echo "     Run setup wizard OR import a JSON config"
echo "     Enable modules: Sitemap, Rich Snippet, Instant Indexing, Link Counter"
echo "     Titles & Meta > Tags > set to noindex"
echo "     Status & Tools > Export settings JSON (save for reference)"
echo ""
echo "  5. CONFIGURE LITESPEED CACHE:"
echo "     Cache tab: Enable Page Cache"
echo "     Page Optimization: CSS/JS Minify ON, CSS Combine ON"
echo "     Image Optimization: Request QUIC.cloud domain key, enable WebP"
echo "     Browser: Browser Cache ON (TTL 1 year)"
echo "     Toolbox > Export (save .data file for reference)"
echo ""
echo "  6. CONFIGURE WP-AI-AFFILIATE (if ready):"
echo "     Settings > AI Affiliate > enter Anthropic API key"
echo "     Settings > AI Affiliate > enter Amazon PA API credentials"
echo "     (Can be done later — plugin works without config, just won't scan)"
echo ""
echo "  7. VERIFY PERFORMANCE:"
echo "     Run PageSpeed Insights on https://${TEMPLATE_DOMAIN}/"
echo "     Target: 95+ desktop, 90+ mobile (GP Marketer hits 99 out of box)"
echo ""
echo "  8. EXPORT SETTINGS FOR CLONES:"
echo "     Rank Math: Status & Tools > Import/Export > Export (JSON)"
echo "     LiteSpeed: LiteSpeed Cache > Toolbox > Export (.data)"
echo "     Save both files — import into cloned sites if settings drift"
echo ""
echo "  9. CLONE TO REAL DOMAINS:"
echo "     sudo bash mass-clone.sh domains.txt"
echo "     Then: sudo bash post-clone-config.sh site-configs.csv"
echo "     Then: sudo bash batch-indexing.sh domains.txt"
echo ""
echo "SAVE THESE CREDENTIALS — they won't be shown again."
