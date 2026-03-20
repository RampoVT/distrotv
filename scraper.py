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
                
                # Clean URL of query parameters (keeps playlist URLs clean)
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
        
        logger.info(f"Successfully processed {len(channels)} channels")
        return channels

    def generate_m3u(self, channels: List[Dict[str, Any]] = None) -> str:
        """Generates an M3U8 playlist string from the processed channels"""
        if channels is None:
            channels = self.get_channels()

        m3u_lines = ["#EXTM3U"]
        
        # Sort channels by name for tidier list
        sorted_channels = sorted(channels, key=lambda x: x['name'].lower())

        for channel in sorted_channels:
            # Map scraped data to M3U fields
            # tvg-id: used for EPG matching
            # tvg-logo: channel icon
            # group-title: genre grouping in players
            metadata_parts = [
                f'tvg-id="{channel["id"]}"',
                f'tvg-name="{channel["name"]}"',
                f'tvg-logo="{channel["logo"]}"',
                f'group-title="{channel["group"]}"'
            ]
            
            metadata_str = " ".join(metadata_parts)
            
            # EXTINF line format: #EXTINF:-1 <metadata>,<channel_name>
            m3u_lines.append(f'#EXTINF:-1 {metadata_str},{channel["name"]}')
            # The stream URL line
            m3u_lines.append(channel["stream_url"])

        logger.info(f"Generated M3U playlist with {len(sorted_channels)} entries")
        return "\n".join(m3u_lines)

    def save_results(self, json_filename="distrotv_channels.json", m3u_filename="distrotv.m3u"):
        """Gets channels once and saves both JSON and M3U formats"""
        channels = self.get_channels()
        
        if not channels:
            logger.warning("No channel data retrieved, skipping save.")
            return

        # Save JSON
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(channels, f, indent=4)
        logger.info(f"Saved JSON data to {json_filename}")

        # Save M3U
        m3u_content = self.generate_m3u(channels)
        with open(m3u_filename, 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        logger.info(f"Saved M3U playlist to {m3u_filename}")

if __name__ == "__main__":
    scraper = DistroTVScraper()
    # Updated to save both files
    scraper.save_results()
