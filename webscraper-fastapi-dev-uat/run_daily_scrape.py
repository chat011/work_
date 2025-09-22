import asyncio
import json
import logging
import pathlib
import sys
from datetime import datetime

from scraper_simple_deep import scrape_urls_simple_api

# ----------------------------------------------------
# Setup
# ----------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily_scrape")

DATA_FILE = pathlib.Path("data/targets.json")
LOGS_DIR = pathlib.Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Choose behavior: "latest" or "all"
SCRAPE_MODE = "all"   # ✅ Always process all saved URLs, deduplicated


def main():
    if not DATA_FILE.exists():
        logger.error(f"No targets file found at {DATA_FILE}. Exiting.")
        sys.exit(1)

    # Load URLs from saved targets.json
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in targets file")
            sys.exit(1)

    urls = []
    if isinstance(payload, dict):
        urls = payload.get("urls", [])
    elif isinstance(payload, list):
        if SCRAPE_MODE == "latest":
            if payload:
                urls = payload[-1].get("urls", [])
        elif SCRAPE_MODE == "all":
            all_urls = []
            for entry in payload:
                all_urls.extend(entry.get("urls", []))
            urls = list(dict.fromkeys(all_urls))  # deduplicate
    else:
        logger.error("Unsupported targets.json format")
        sys.exit(1)

    if not urls:
        logger.error("No URLs found; exiting.")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = LOGS_DIR / f"cron_scrape_{timestamp}.json"

    try:
        logger.info(f"Starting scrape for {len(urls)} urls")
        result = asyncio.run(
            asyncio.wait_for(scrape_urls_simple_api(urls, max_pages=50), timeout=3600)
        )

        # Result already contains metadata + products
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved results to {out_file}")
        sys.exit(0)
    except asyncio.TimeoutError:
        logger.error("Scrape timed out after 3600s")
        sys.exit(2)
    except Exception as e:
        logger.exception("Scrape failed")
        sys.exit(3)


if __name__ == "__main__":
    main()
