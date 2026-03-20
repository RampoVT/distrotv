import requests
import time
import json
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("distrotv_scraper")

class DistroTVScraper:
    def __init__(self):
        self.feed_url = "https://tv.jsrdn.com/tv_v5/getfeed.php"
        self.epg_url = "https://tv.jsrdn.com/epg/query.php"
        self.headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'
        }

    def fetch_channels(self) -> List[Dict[str, Any]]:
        """Scrapes the live channel list. URLs are kept in full for playback."""
        try:
            logger.info("Fetching live channel feed...")
            response = requests.get(self.feed_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            shows = data.get("shows", {})
            channels = []
            
            for ch_key, ch_data in shows.items():
                if ch_data.get("type") != "live":
                    continue
                    
                try:
                    seasons = ch_data.get("seasons", [])
                    if not seasons: continue
                    episodes = seasons[0].get("episodes", [])
                    if not episodes: continue
                    content = episodes[0].get("content", {})
                    
                    # IMPORTANT: We do NOT split the URL anymore. 
                    # We keep the tokens so the stream plays.
                    stream_url = content.get("url", "")
                    if not stream_url: continue
                    
                    channel_name = ch_data.get("name", "")
                    title = ch_data.get("title", "").strip()
                    
                    channels.append({
                        'id': f"distrotv-{channel_name}",
                        'raw_id': channel_name, 
                        'name': title,
                        'stream_url': stream_url,
                        'logo': ch_data.get("img_logo", ""),
                        'group': ch_data.get("genre", "DistroTV"),
                        'description': ch_data.get("description", "").strip()
                    })
                except Exception:
                    continue
            
            logger.info(f"Found {len(channels)} live channels.")
            return channels
        except Exception as e:
            logger.error(f"Failed to fetch feed: {e}")
            return []

    def generate_m3u(self, channels: List[Dict[str, Any]]):
        m3u = ["#EXTM3U"]
        for ch in sorted(channels, key=lambda x: x['name'].lower()):
            metadata = f'tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}"'
            m3u.append(f'#EXTINF:-1 {metadata},{ch["name"]}')
            m3u.append(ch["stream_url"])
        return "\n".join(m3u)

    def generate_epg_xml(self, channels: List[Dict[str, Any]]):
        root = ET.Element("tv", {"generator-info-name": "DistroTV-Scraper"})

        for ch in channels:
            c_node = ET.SubElement(root, "channel", id=ch['id'])
            ET.SubElement(c_node, "display-name").text = ch['name']
            ET.SubElement(c_node, "icon", src=ch['logo'])

        logger.info("Fetching EPG listings and descriptions...")
        for ch in channels:
            try:
                # Query using the raw ID for the EPG API
                params = {'ch': ch['raw_id']}
                resp = requests.get(self.epg_url, params=params, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    listings = resp.json().get('listings', [])
                    for prog in listings:
                        start = datetime.fromtimestamp(int(prog['start'])).strftime("%Y%m%d%H%M%S +0000")
                        stop = datetime.fromtimestamp(int(prog['end'])).strftime("%Y%m%d%H%M%S +0000")
                        
                        p_node = ET.SubElement(root, "programme", {
                            "start": start,
                            "stop": stop,
                            "channel": ch['id']
                        })
                        ET.SubElement(p_node, "title", lang="en").text = prog.get('title', 'No Title')
                        # Descriptions are now pulled and mapped correctly
                        desc_text = prog.get('description', 'No description available.')
                        ET.SubElement(p_node, "desc", lang="en").text = desc_text
                time.sleep(0.05) # Prevent rate limiting
            except Exception:
                continue

        return minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

if __name__ == "__main__":
    scraper = DistroTVScraper()
    channels = scraper.fetch_channels()
    
    if channels:
        # Save JSON for backup
        with open("distrotv_channels.json", "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=4)
        # Save M3U Playlist
        with open("distrotv.m3u", "w", encoding="utf-8") as f:
            f.write(scraper.generate_m3u(channels))
        # Save XMLTV Guide
        with open("distrotv_epg.xml", "w", encoding="utf-8") as f:
            f.write(scraper.generate_epg_xml(channels))
        logger.info("Update Complete.")
