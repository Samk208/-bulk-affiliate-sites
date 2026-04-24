# VPS Deployment — Bulk Affiliate Pipeline

## Why

Cowork scheduled tasks run behind a sandbox proxy that blocks external API calls (Perplexity, OpenRouter). This moves the Tier 2 pipeline to n8n on the Contabo VPS where APIs work unrestricted.

## What Moves to n8n

| Task | Was | Now |
|------|-----|-----|
| Tier 2 generation (Kimi K2.5) | `gen-tier2-session-b/c` in Cowork | n8n cron on VPS |
| SERP research (Perplexity) | Same tasks | n8n cron on VPS |
| HTML cleanup + QA | Same tasks | n8n on VPS |
| Email reports | Same tasks | n8n on VPS |

## What Stays in Cowork

Tier 1 pillars (Claude brain), EAE/DC content, GSC monitoring, KmedTour/OneLink sessions.

## Deployment

### 1. Run deploy script

```bash
cd wordpress/bulk-affiliate-sites
bash deploy/deploy-to-vps.sh
```

This copies scripts, niche data, and API keys to `/opt/bulk-affiliate/` on the VPS.

### 2. Test on VPS

```bash
ssh root@62.84.185.148
cd /opt/bulk-affiliate
python3 scripts/serp_researcher.py korean-skincare --limit 2
python3 scripts/article_generator.py korean-skincare --limit 2
```

### 3. Import n8n workflows

1. Open https://n8n.kmedtour.com
2. Go to Workflows > Import from File
3. Import `deploy/n8n-tier2-pipeline.json`
4. Import `deploy/n8n-error-handler.json`
5. In the tier2 pipeline, set the error workflow to "Bulk Affiliate - Error Handler"
6. Activate both workflows

### 4. Configure n8n environment

The Execute Command nodes need access to env vars. Either:
- Source the env file in commands: `cd /opt/bulk-affiliate && source .env.cowork && python3 ...`
- Or export vars in n8n's Docker container environment

### 5. Disable Cowork tasks

In Claude Code, disable:
- `gen-tier2-session-b`
- `gen-tier2-session-c`
- `bulk-affiliate-daily`

### 6. Sync outputs back to local

After n8n generates articles on VPS, pull them locally:

```bash
rsync -avz root@62.84.185.148:/opt/bulk-affiliate/outputs/ ./outputs/
```

## Schedule (n8n cron, UTC times)

| UTC Time | Seoul Time | What |
|----------|-----------|------|
| 04:01 | 1:01 PM | Tier 2 batch 1 (35 articles) |
| 10:02 | 7:02 PM | Tier 2 batch 2 (35 articles) |

## Niche Rotation (14-day cycle)

| Day | Niche | Articles |
|-----|-------|----------|
| 1 | dog-comfort | 90 |
| 2 | camping-gear | 76 |
| 3 | cat-care | 80 |
| 4 | home-coffee | 82 |
| 5 | mens-grooming | 94 |
| 6 | oral-care | 56 |
| 7 | home-cleaning | 82 |
| 8 | healthy-cooking | 86 |
| 9 | home-office | 80 |
| 10 | water-air-quality | 86 |
| 11 | korean-skincare | 79 |
| 12 | makeup-beauty | 74 |
| 13 | korean-medical-tourism | 113 |
| 14 | korean-used-cars | 67 |

## Cowork Fallback

Articles that fail on Kimi K2.5 (<800 words or API error) are saved to `outputs/<niche>/articles/cowork-queue.json`. Cowork session A3 (4:02 PM) checks for these and rewrites them using Claude at $0 cost.

## Monitoring

- **n8n UI:** https://n8n.kmedtour.com — execution history, per-node logs
- **Error log:** `/opt/bulk-affiliate/logs/errors.log`
- **Run log:** `/opt/bulk-affiliate/logs/pipeline-runs.log`
- **Email alerts:** Sent on failure via SMTP
- **Daily reports:** `outputs/daily-report-day{N}.txt`
