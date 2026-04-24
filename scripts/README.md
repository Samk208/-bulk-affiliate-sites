# Deployment Scripts — ZimmWriter Bulk Affiliate Sites

## Pipeline Overview

```
1. build-golden-template.sh    →  One-time: builds the master WP site
2. mass-clone.sh               →  Clones template to all domains (< 2 min/site)
3. post-clone-config.sh        →  Customizes branding, author, legal pages per site
4. batch-indexing.sh            →  IndexNow + sitemap submission for all sites
```

## Prerequisites

- Contabo VPS with CyberPanel + OpenLiteSpeed installed
- WP-CLI: `curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && sudo mv wp-cli.phar /usr/local/bin/wp`
- Upload to `/root/` on VPS before running:
  - `generatepress-premium.zip` (buy at generatepress.com)
  - `wp-ai-affiliate.zip` (your custom plugin from `C:\Users\Lenovo\Desktop\Amazon Affiliate Plugin\wp-ai-affiliate\`)

## Step-by-Step

### Step 1: Build Golden Template (run once, ~10 min)

```bash
# Upload scripts to VPS
scp scripts/*.sh root@YOUR_VPS_IP:/root/

# SSH in and run
ssh root@YOUR_VPS_IP
sudo bash /root/build-golden-template.sh
```

Edit the CONFIGURATION section at the top first:
- `TEMPLATE_DOMAIN` — use a throwaway domain or `golden-template.com`
- `ADMIN_EMAIL` — your email
- `MYSQL_ROOT_PASS` — your MySQL root password

After running, log in to WP Admin and:
1. Activate GP Premium license key
2. Import the "Marketer" starter site (Appearance > GeneratePress)
3. Walk through Rank Math setup wizard
4. Configure LiteSpeed Cache (Page Cache ON, Browser Cache ON, CSS/JS Minify ON)
5. Verify PageSpeed > 95

### Step 2: Buy Domains + Point DNS

1. Find expired domains on Spamzilla ($37/mo) or register EMDs on Namecheap
2. Add each domain to Cloudflare
3. Point A record to your VPS IP
4. Wait for DNS propagation (usually 5-30 min with Cloudflare)

### Step 3: Mass Clone (< 2 min per site)

```bash
# Edit domains.txt with your actual domains
nano /root/domains.txt

# Run
sudo bash /root/mass-clone.sh /root/domains.txt
```

Credentials are saved to `/root/cloned-sites-{date}.txt`

### Step 4: Customize Each Site

```bash
# Edit site-configs.csv with real titles, authors, emails
nano /root/site-configs.csv

# Run
sudo bash /root/post-clone-config.sh /root/site-configs.csv
```

### Step 5: Index All Sites

```bash
sudo bash /root/batch-indexing.sh /root/domains.txt
```

Then manually:
1. Verify all 10 in Google Search Console
2. Import to Bing WMT from GSC (one click, 100 at a time)

### Step 6: Import Content via ZimmWriter

1. Paste roundup titles into ZimmWriter Product Roundup tool
2. Paste informational titles into ZimmWriter Bulk Blog Writer
3. Use ZimmWriter Bulk Importer plugin to upload to each site
4. Rank Math IndexNow auto-submits every published post

## File Reference

| File | Purpose |
|------|---------|
| `build-golden-template.sh` | One-time: creates master WP site with all plugins + config |
| `mass-clone.sh` | Clones template to N domains from a text file |
| `post-clone-config.sh` | Customizes title, author, legal pages per site from CSV |
| `batch-indexing.sh` | IndexNow submission + sitemap setup for all sites |
| `sample-domains.txt` | Example domains file |
| `sample-site-configs.csv` | Example per-site configuration |

## Key CyberPanel/OLS Notes (from wp-cyberpanel-deploy skill)

- **File ownership** must be `{site-user}:{site-user}`, never `root`
- **Permissions**: directories 755, files 644
- **After code changes**: `killall -9 lsphp && systemctl restart lsws`
- **Three cache layers**: OLS server cache, LiteSpeed plugin cache, Cloudflare edge
- **WP-Cron**: disabled in wp-config, replaced by system cron (*/5 * * * *)
