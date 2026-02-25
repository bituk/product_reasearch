# Apify Setup for TikTok & Instagram Videos

This guide helps you configure your Apify account so the pipeline returns TikTok and Instagram videos that can be downloaded, uploaded to S3, and saved in the database.

## 1. Get Your API Token

1. Go to [Apify Console](https://console.apify.com/)
2. Sign in or create a free account
3. Click your profile (top right) → **Settings** → **Integrations**
4. Copy your **API Token** (starts with `apify_api_`)
5. Add to `.env`:
   ```
   APIFY_API_TOKEN=apify_api_your_token_here
   ```

## 2. Actors Used

| Platform   | Actor                               | Purpose                    |
|-----------|--------------------------------------|----------------------------|
| TikTok    | `clockworks/tiktok-hashtag-scraper`  | Scrape videos by hashtag   |
| Instagram | `apify/instagram-hashtag-scraper`    | Scrape reels by hashtag    |

## 3. TikTok Configuration

- **Hashtags**: Derived from your product keywords (e.g. `#perfume`, `#productreview`)
- **shouldDownloadVideos**: `true` (default) – Apify downloads videos to its storage so we get direct CDN URLs for faster download
- **Cost**: Higher when downloading; limit is 8 per hashtag when enabled

## 4. Instagram Configuration

- **resultsType**: `reels` – Only reels (videos), no image posts
- **Hashtags**: Same as TikTok, from product keywords
- **videoUrl**: Apify returns direct CDN URLs for reels – we use these for fast download

## 5. Ensure Apify Is Not Skipped

In `.env`, do **not** set:
```
# SKIP_APIFY=1   ← Remove or comment out
```

When starting the pipeline via API, do **not** pass `skip_apify: true`.

## 6. Test the Setup

Run the Apify test script:
```bash
cd product_reasearch
python3 test_apify_video_scrape.py
```

This will:
- Scrape TikTok and Instagram by hashtag
- Verify video URLs and structure
- Optionally test download

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| No TikTok videos | Check `APIFY_API_TOKEN` is set; TikTok may rate-limit |
| No Instagram videos | Ensure `resultsType: reels`; hashtags must match product |
| "Instagram post" with tag URL | Fixed: we now use `shortCode` for proper reel URLs and filter to Video type only |
| Download fails | For TikTok: set `TIKTOK_COOKIES_FROM_BROWSER=chrome` in `.env` (close browser first) |

## 8. Cost

- **Free tier**: ~$5 credit ≈ 2,000 results
- **Pay-per-result**: ~$2.30–2.60 per 1,000 results
- TikTok with `shouldDownloadVideos=true` uses more compute
