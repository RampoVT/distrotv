import requests
import time
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("distrotv_scraper")

class DistroTVScraper:
    """Standalone scraper for DistroTV channels based on official API endpoints"""
    
    def __init__(self):
        self.feed_url = "https://tv.jsrdn.com/tv_v5/getfeed.php"
        self.epg_url = "https://tv.jsrdn.com/epg/query.php"
        
        # Specific headers required to mimic the Android app
        self.headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'
        }
        
        self.feed_cache = None
        self.feed_cache_time = 0
        self.cache_duration = 43200  # 12 hours

    def fetch_raw_feed(self) -> Dict[str, Any]:
        """Fetch and cache the raw DistroTV feed"""
        if self.feed_cache is not None and (time.time() - self.feed_cache_time < self.cache_duration):
            return self.feed_cache
        
        try:
            logger.info(f"Fetching DistroTV feed from {self.feed_url}")
            response = requests.get(self.feed_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            self.feed_cache = {
                "topics": [t for t in data.get("topics", []) if t.get("type") == "live"],
                "shows": {k: v for k, v in data.get("shows", {}).items() if v.get("type") == "live"},
            }
            self.feed_cache_time = time.time()
            return self.feed_cache
            
        except Exception as e:
            logger.error(f"Error loading DistroTV feed: {e}")
            return {"topics": [], "shows": {}}

    def get_channels(self) -> List[Dict[str, Any]]:
        """Process the feed into a list of standardized channel dictionaries"""
        feed = self.fetch_raw_feed()
        
        if not feed.get("shows"):
            logger.warning("No live shows found in DistroTV feed")
            return []
        
        channels = []
        for ch_key, ch_data in feed["shows"].items():
            try:
                # Navigate nested structure: seasons -> episodes -> content -> url
                seasons = ch_data.get("seasons", [])
                if not seasons:
                    continue
                
                episodes = seasons[0].get("episodes", [])
                if not episodes:
                    continue
                
                content = episodes[0].get("content", {})
                stream_url = content.get("url", "")
                
                if not stream_url:
                    continue
                
                # Clean URL of query parameters
                clean_url = stream_url.split('?', 1)[0]
                
                channel_name = ch_data.get("name", "")
                title = ch_data.get("title", "").strip()
                
                if not channel_name or not title:
                    continue

                genre = ch_data.get("genre", "")
                group = genre if genre else "DistroTV"
                
                channels.append({
                    'id': f"distrotv-{channel_name}",
                    'name': title,
                    'stream_url': clean_url,
                    'logo': ch_data.get("img_logo", ""),
                    'group': group,
                    'description': ch_data.get("description", "").strip(),
                    'language': 'en',
                    'scraped_at': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.debug(f"Skipping channel {ch_key} due to error: {e}")
                continue
        
        logger.info(f"Successfully scraped {len(channels)} channels")
        return channels

    def save_to_json(self, filename="distrotv_channels.json"):
        """Utility to save results to a local file"""
        channels = self.get_channels()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=4)
        logger.info(f"Saved data to {filename}")

if __name__ == "__main__":
    scraper = DistroTVScraper()
    scraper.save_to_json()
