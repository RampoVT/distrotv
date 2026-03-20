import requests
import time
import json
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("distrotv_v4_scraper")

class DistroTVScraper:
    def __init__(self):
        # Using V4 API which often handles sessions better for Topic 70
        self.feed_url = "https://tv.jsrdn.com/tv_v4/getfeed.php"
        self.epg_url = "https://tv.jsrdn.com/epg/query.php"
        self.target_topic = 70 # US / International English
        self.headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; AFTT Build/STT9.221129.002) GTV/AFTT DistroTV/2.0.9'
        }

    def fetch_channels(self) -> List[Dict[str, Any]]:
        try:
            # Adding topic parameter directly to the request
            params = {'topic': self.target_topic}
            response = requests.get(self.feed_url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            shows = data.get("shows", {})
            channels = []
            
            for ch_key, ch_data in shows.items():
                # Filter for live content and ensure it belongs to our target topic
                if ch_data.get("type") != "live":
                    continue
                
                try:
                    # Capture the full stream URL with query tokens
                    stream_url = ch_data["seasons"][0]["episodes"][0]["content"]["url"]
                    
                    channels.append({
                        'id': f"distrotv-{ch_data['name']}",
                        'raw_id': ch_data['name'],
                        'name': ch_data.get("title", "").strip(),
                        'stream_url': stream_url, # DO NOT CLEAN/SPLIT
                        'logo': ch_data.get("img_logo", ""),
                        'group': ch_data.get("genre", "DistroTV English")
                    })
                except:
                    continue
            
            logger.info(f"Found {len(channels)} channels in Topic {self.target_topic}")
            return channels
        except Exception as e:
            logger.error(f"Feed error: {e}")
            return []

    def generate_m3u(self, channels: List[Dict[str, Any]]):
        m3u = ["#EXTM3U"]
        for ch in sorted(channels, key=lambda x: x['name'].lower()):
            # We add the tvg-id and group specifically for US English
            m3u.append(f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
            m3u.append(ch["stream_url"])
        return "\n".join(m3u)

    def generate_epg_xml(self, channels: List[Dict[str, Any]]):
        root = ET.Element("tv", {"generator-info-name": "DistroTV-Scraper-V4"})
        
        for ch in channels:
            c_node = ET.SubElement(root, "channel", id=ch['id'])
            ET.SubElement(c_node, "display-name").text = ch['name']
            ET.SubElement(c_node, "icon", src=ch['logo'])

        for ch in channels:
            try:
                resp = requests.get(self.epg_url, params={'ch': ch['raw_id']}, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    for prog in resp.json().get('listings', []):
                        start = datetime.fromtimestamp(int(prog['start'])).strftime("%Y%m%d%H%M%S +0000")
                        stop = datetime.fromtimestamp(int(prog['end'])).strftime("%Y%m%d%H%M%S +0000")
                        p_node = ET.SubElement(root, "programme", {"start": start, "stop": stop, "channel": ch['id']})
                        ET.SubElement(p_node, "title", lang="en").text = prog.get('title', 'No Title')
                        ET.SubElement(p_node, "desc", lang="en").text = prog.get('description', 'No description available.')
                time.sleep(0.05)
            except:
                continue

        return minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

if __name__ == "__main__":
    scraper = DistroTVScraper()
    channels = scraper.fetch_channels()
    if channels:
        with open("distrotv.m3u", "w", encoding="utf-8") as f:
            f.write(scraper.generate_m3u(channels))
        with open("distrotv_epg.xml", "w", encoding="utf-8") as f:
            f.write(scraper.generate_epg_xml(channels))
        logger.info("Files updated for Topic 70.")
