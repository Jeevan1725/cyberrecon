# 04 — Architecture

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Authors:** Vekeshhari Rajasekar, R Jeevan

---

## 1. Architectural Overview

CyberRecon follows a client–server architecture with three core deployment roles:

| Role | Component | Responsibility |
|------|-----------|----------------|
| **Operator** | Operator CLI / Dashboard | Issues commands, views exfiltrated data |
| **C2 Server** | Flask app | Registers victims, encodes commands to QR, stores exfil |
| **Victim** | RAT Client | Fetches QR commands, executes them, exfiltrates results |

Optional components:

- **AWS Relay** — proxies C2 traffic to hide the origin IP
- **AI Agent** — parses natural-language commands into structured C2 commands

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        OPERATOR SIDE                              │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │ Operator CLI │─────▶│  C2 Server   │─────▶│  AWS Relay   │   │
│  │  (Python)    │      │  (Flask)     │      │  (optional)  │   │
│  └──────────────┘      └───────┬──────┘      └──────┬───────┘   │
│         ▲                       │                     │          │
│         │                       ▼                     │          │
│  ┌──────────────┐      ┌──────────────┐               │          │
│  │  Dashboard   │◀─────│  QR Encoder  │               │          │
│  │  (Parrot)    │      │  (qrcode)    │               │          │
│  └──────────────┘      └──────────────┘               │          │
└────────────────────────────┬──────────────────────────────┬───────┘
                             │                              │
                             ▼ HTTPS                        ▼
                    ┌──────────────────┐             (relay)
                    │ Browser Isolation │
                    │ (visual channel)  │
                    └─────────┬─────────┘
                              │
                              ▼ QR PNG
┌──────────────────────────────────────────────────────────────────┐
│                         VICTIM SIDE                               │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │ Headless     │─────▶│   QR Client  │─────▶│    RAT       │   │
│  │ Chrome       │      │  (OpenCV)    │      │   Modules    │   │
│  │ (Selenium)   │      │              │      │              │   │
│  └──────────────┘      └──────┬───────┘      └──────┬───────┘   │
│                                │                      │          │
│                                ▼                      ▼          │
│                        ┌──────────────┐      ┌──────────────┐   │
│                        │  Command     │      │  Feature     │   │
│                        │  Dispatch    │      │  Modules     │   │
│                        └──────────────┘      └──────┬───────┘   │
│                                                       │          │
│                                                       ▼          │
│                                              ┌──────────────┐   │
│                                              │ HTTP POST    │   │
│                                              │ /exfil/<id>  │   │
│                                              └──────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Descriptions

### 3.1 C2 Server (`c2_server.py`)

**Technology:** Flask + Werkzeug + qrcode

**Responsibilities:**

- Register victims and assign cryptographically-random IDs
- Queue commands and serve them as QR-encoded PNGs
- Store exfiltrated data (screenshots, keystrokes, GPS, files)
- Serve a live dashboard with real-time updates
- Enforce operator token auth on protected endpoints

**Key endpoints:** `/register`, `/qr/<id>`, `/command/<id>`, `/exfil/<id>`, `/download-all/<id>`, `/dashboard`

**Dependencies:** `flask`, `qrcode[pil]`, `requests` (in tests)

### 3.2 RAT Client (`rat_client.py`)

**Technology:** Python 3.10+, Selenium, OpenCV, `requests`

**Responsibilities:**

- Register with C2 on startup
- Fetch the QR PNG using Selenium + headless Chrome
- Decode QR payload via OpenCV `QRCodeDetector`
- Dispatch commands to feature handlers
- Exfiltrate results via HTTP POST

**Key classes:**

- `KeyloggerModule` — background keystroke capture with buffered flush
- `QRDecoder` — main client orchestrator

**Fallback chain:** TCP → HTTP → QR (visual channel is the reliable path)

### 3.3 Operator CLI (`operator_cli.py`)

**Technology:** Python `argparse` + `requests`

**Responsibilities:** List victims, select target, send commands, display results.

**Auth:** `X-Operator-Token` header validated against `CYBERRECON_OPERATOR_TOKEN`.

### 3.4 AWS Relay (`aws_relay.py`)

**Technology:** Python `socket` + `requests`

**Responsibilities:** Accept TCP on port 443, parse minimal HTTP, proxy to C2 backend, return responses, track stats.

**Use case:** Hides the C2 origin IP behind an AWS-hosted relay.

### 3.5 AI Agent (`ai_agent.py`)

**Technology:** Pure Python

**Responsibilities:** Parse natural-language commands into structured C2 commands with confidence scores.

---

## 4. Data Flow

### 4.1 Command Flow (Operator → Victim)

```
Operator
   │  POST /command/<victim_id>  (X-Operator-Token)
   ▼
C2 Server
   │  Validate token → Look up template → Append to queue
   ▼
Victim Client
   │  GET /qr/<victim_id>  (Selenium fetch)
   │  Render QR PNG in headless Chrome
   │  Screenshot page → Decode QR via OpenCV
   ▼
Command Handler
   │  Execute (e.g., screenshot capture)
   ▼
Exfiltration
   │  POST /exfil/<victim_id>  (base64 payload)
   ▼
C2 Server
   │  Store by type
   ▼
Dashboard
   │  Poll /exfil-data/<victim_id> every 2s
   ▼
Operator
```

### 4.2 Data Volume

| Data Type | Typical Size | Frequency |
|-----------|--------------|-----------|
| Heartbeat | < 100 bytes | Every 5s |
| Screenshot | 50–200 KB | On demand |
| Webcam frame | 30–100 KB | On demand |
| Keystrokes | 500–5000 bytes | Every 15s |
| GPS | ~300 bytes | On demand |
| System info | ~500 bytes | On demand |

---

## 5. Module Dependency Graph

```
                    ┌──────────────┐
                    │   main.py    │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  ┌───────────┐      ┌───────────┐      ┌───────────┐
  │c2_server  │      │rat_client │      │operator_  │
  │  .py      │◀─────│  .py      │─────▶│ cli.py    │
  └─────┬─────┘      └─────┬─────┘      └───────────┘
        │                  │
        │                  ▼
        │           ┌──────────────────┐
        │           │ modules/         │
        │           │ ├─ screenshot.py │
        │           │ ├─ webcam.py     │
        │           │ ├─ keylogger.py  │
        │           │ ├─ gps.py        │
        │           │ ├─ persistence.py│
        │           │ └─ stealth.py    │
        │           └──────────────────┘
        │
        ▼
  ┌───────────┐
  │config.py  │  (leaf — imported by all)
  └───────────┘
```

**Key metrics:**

- **Independent modules (fan-in = 0):** `config.py`, `ai_agent.py`
- **Hub modules (high fan-in):** `c2_server.py`, `rat_client.py`
- **Leaf modules:** `config.py`, `modules/*`

---

## 6. Deployment Architecture

### 6.1 Lab Deployment (Demo)

```
┌──────────────────┐        ┌──────────────────┐
│  Attack VM       │        │  Victim VM       │
│  C2 Server       │◀─HTTPS─│  RAT Client      │
│  Operator CLI    │        │  Chrome (Selenium)│
│  Dashboard       │        │  Webcam          │
│  10.0.0.10       │        │  10.0.0.20       │
└──────────────────┘        └──────────────────┘
        │
   isolated network
```

### 6.2 Docker Deployment

```
┌──────────────────────────────────────┐
│  Docker Host (Linux)                 │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  cyberrecon-c2                 │ │
│  │  Port 8443 (127.0.0.1 only)    │ │
│  │  Non-root user (UID 1000)      │ │
│  │  Read-only root FS             │ │
│  │  Healthcheck every 30s         │ │
│  └────────────────────────────────┘ │
└──────────────────────────────────────┘
```

---

## 7. Design Decisions

### 7.1 Why QR-encoded base64 JSON?

QR codes carry binary-safe data via base64. JSON payloads fit within Level-H error-correction capacity. Mandiant's technique uses exactly this approach. Base64 encoding avoids Unicode issues in image rendering.

### 7.2 Why Selenium + headless Chrome?

Browser isolation strips dynamic content but not rendered pixels. A real Chrome fingerprint defeats basic bot detection. Chrome flags auto-grant media permissions. Graceful fallback if Chrome unavailable.

### 7.3 Why `secrets` over `uuid`?

`uuid.uuid4()[:8]` truncates to 32 bits (brute-forceable). `secrets.token_hex(8)` provides 64 bits of CSPRNG entropy. Prevents victim-ID enumeration attacks.

### 7.4 Why in-memory storage (dict)?

Simplicity for lab demonstration. No database dependency. Fast lookups. Future work: Redis or SQLite for persistence.

### 7.5 Why operator token auth over sessions?

Simple shared secret (env var). No session state to manage. Suitable for single-operator scenario. Backed by `X-Operator-Token` header comparison.

---

## 8. Quality Attributes

| Attribute | How Addressed |
|-----------|---------------|
| Performance | QR decode ~650ms; dashboard polls at 2s intervals |
| Security | 6 CWEs fixed; SAST clean; token auth; TLS verify |
| Reliability | Graceful fallback if Chrome missing |
| Maintainability | Modular structure; Ruff-clean; pytest-ready |
| Portability | Docker + non-root; runs on Linux server + Windows client |
| Observability | Print-based logs; `/check` health endpoint |

---

## 9. Architectural Risks

| Risk | Mitigation |
|------|------------|
| Selenium dependency on Chrome | Graceful fallback to `requests.get` |
| In-memory storage loss on restart | Documented limitation; Redis is future work |
| Slow QR channel (~438 bytes/sec) | Accepted — matches Mandiant baseline |
| Port 8443 blocked by firewall | AWS relay fallback |
| Camera permission prompt | Auto-grant flags configured |

---

## 10. References

- `docs/report/03-requirements.md`
- `docs/report/06-threat-model.md`
- `docs/report/07-security-features.md`
- Mandiant (2024) — QR-C2 technique
- `docs/diagrams/` — visual diagrams