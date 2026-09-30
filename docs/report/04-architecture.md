\# 04 — Architecture



\*\*Project:\*\* CyberRecon — QR-Code-Based C2 Framework

\*\*Document Version:\*\* 1.0

\*\*Date:\*\* 2026-09-30

\*\*Authors:\*\* Vekeshhari Rajasekar, R Jeevan



\---



\## 1. Architectural Overview



CyberRecon follows a \*\*client–server\*\* architecture with three core

deployment roles:



| Role | Component | Responsibility |

|------|-----------|----------------|

| \*\*Operator\*\* | Operator CLI / Dashboard | Issues commands, views exfiltrated data |

| \*\*C2 Server\*\* | Flask app | Registers victims, encodes commands to QR, stores exfil |

| \*\*Victim\*\* | RAT Client | Fetches QR commands, executes them, exfiltrates results |



Optional components:



\- \*\*AWS Relay\*\* — proxies C2 traffic to hide the origin IP

\- \*\*AI Agent\*\* — parses natural-language commands into structured C2 commands



\---



\## 2. High-Level Architecture



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

&#x20;                            │                              │

&#x20;                            ▼ HTTPS                        ▼

&#x20;                   ┌──────────────────┐             (relay)

&#x20;                   │ Browser Isolation │

&#x20;                   │ (visual channel)  │

&#x20;                   └─────────┬─────────┘

&#x20;                             │

&#x20;                             ▼ QR PNG

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



\---



\## 3. Component Descriptions



\### 3.1 C2 Server (`c2\_server.py`)



\*\*Technology:\*\* Flask + Werkzeug + qrcode



\*\*Responsibilities:\*\*



\- Register victims and assign cryptographically-random IDs

\- Queue commands and serve them as QR-encoded PNGs

\- Store exfiltrated data (screenshots, keystrokes, GPS, files)

\- Serve a live dashboard with real-time updates

\- Enforce operator token auth on protected endpoints



\*\*Key endpoints:\*\* `/register`, `/qr/<id>`, `/command/<id>`, `/exfil/<id>`, `/download-all/<id>`, `/dashboard`



\*\*Dependencies:\*\* `flask`, `qrcode\[pil]`, `requests` (in tests)



\### 3.2 RAT Client (`rat\_client.py`)



\*\*Technology:\*\* Python 3.10+, Selenium, OpenCV, `requests`



\*\*Responsibilities:\*\*



\- Register with C2 on startup

\- Fetch the QR PNG using Selenium + headless Chrome

\- Decode QR payload via OpenCV `QRCodeDetector`

\- Dispatch commands to feature handlers

\- Exfiltrate results via HTTP POST



\*\*Key classes:\*\*



\- `KeyloggerModule` — background keystroke capture with buffered flush

\- `QRDecoder` — main client orchestrator



\*\*Fallback chain:\*\* TCP → HTTP → QR (visual channel is the reliable path)



\### 3.3 Operator CLI (`operator\_cli.py`)



\*\*Technology:\*\* Python `argparse` + `requests`



\*\*Responsibilities:\*\*



\- List active victims

\- Select a target

\- Send commands to selected victim

\- Display command results (sourced from `/exfil-data/<id>`)



\*\*Auth:\*\* `X-Operator-Token` header validated against `CYBERRECON\_OPERATOR\_TOKEN` env var



\### 3.4 AWS Relay (`aws\_relay.py`)



\*\*Technology:\*\* Python `socket` + `requests`



\*\*Responsibilities:\*\*



\- Accept incoming TCP connections on port 443

\- Parse minimal HTTP

\- Proxy requests to the C2 backend

\- Return responses to the client

\- Track relay statistics



\*\*Use case:\*\* Hides the C2 origin IP behind an AWS-hosted relay (domain fronting).



\### 3.5 AI Agent (`ai\_agent.py`)



\*\*Technology:\*\* Pure Python (no external LLM dependency)



\*\*Responsibilities:\*\*



\- Parse natural-language commands ("take a screenshot") into structured C2 commands

\- Map commands to the `COMMAND\_TEMPLATES` dictionary

\- Provide confidence scores for fallback cases



\*\*Example:\*\*

```

Input:  "start monitoring keyboard"

Output: {"command": "keylog\_start", "confidence": 0.95}

```



\---



\## 4. Data Flow



\### 4.1 Command Flow (Operator → Victim)



```

Operator

&#x20;  │

&#x20;  │  POST /command/<victim\_id>

&#x20;  │  Header: X-Operator-Token: <token>

&#x20;  │  Body: {"command": "screenshot"}

&#x20;  ▼

C2 Server

&#x20;  │

&#x20;  │  Validates token

&#x20;  │  Looks up COMMAND\_TEMPLATES\["screenshot"]

&#x20;  │  Appends to victim.command\_queue

&#x20;  ▼

Victim Client

&#x20;  │

&#x20;  │  GET /qr/<victim\_id>  (Selenium fetch)

&#x20;  │  Renders QR PNG in headless Chrome

&#x20;  │  Screenshots the rendered page

&#x20;  │  Decodes QR via OpenCV

&#x20;  ▼

Command Handler

&#x20;  │

&#x20;  │  Executes: screenshot capture

&#x20;  ▼

Exfiltration

&#x20;  │

&#x20;  │  POST /exfil/<victim\_id>

&#x20;  │  Body: {"type": "screenshot", "data": "<base64>"}

&#x20;  ▼

C2 Server

&#x20;  │

&#x20;  │  Stores in victim.screenshots\[]

&#x20;  ▼

Dashboard

&#x20;  │

&#x20;  │  Polls /exfil-data/<victim\_id> every 2s

&#x20;  │  Renders latest screenshot

&#x20;  ▼

Operator

```



\### 4.2 Data Volume



| Data Type | Typical Size | Frequency |

|-----------|--------------|-----------|

| Heartbeat | < 100 bytes | Every 5s |

| Screenshot | 50–200 KB | On demand |

| Webcam frame | 30–100 KB | On demand |

| Keystrokes | 500–5000 bytes | Every 15s |

| GPS | \~300 bytes | On demand |

| System info | \~500 bytes | On demand |



\---



\## 5. Module Dependency Graph



```

&#x20;                   ┌──────────────┐

&#x20;                   │   main.py    │

&#x20;                   │  (launcher)  │

&#x20;                   └──────┬───────┘

&#x20;                          │

&#x20;       ┌──────────────────┼──────────────────┐

&#x20;       ▼                  ▼                  ▼

&#x20; ┌───────────┐      ┌───────────┐      ┌───────────┐

&#x20; │c2\_server  │      │rat\_client │      │operator\_  │

&#x20; │  .py      │◀─────│  .py      │─────▶│ cli.py    │

&#x20; └─────┬─────┘      └─────┬─────┘      └───────────┘

&#x20;       │                  │

&#x20;       │                  ▼

&#x20;       │           ┌──────────────────┐

&#x20;       │           │ modules/         │

&#x20;       │           │ ├─ screenshot.py │

&#x20;       │           │ ├─ webcam.py     │

&#x20;       │           │ ├─ keylogger.py  │

&#x20;       │           │ ├─ gps.py        │

&#x20;       │           │ ├─ persistence.py│

&#x20;       │           │ └─ stealth.py    │

&#x20;       │           └──────────────────┘

&#x20;       │

&#x20;       ▼

&#x20; ┌───────────┐

&#x20; │config.py  │  (leaf — imported by all)

&#x20; └───────────┘

```



\*\*Key metrics:\*\*



\- \*\*Independent modules (fan-in = 0):\*\* `config.py`, `ai\_agent.py`

\- \*\*Hub modules (high fan-in):\*\* `c2\_server.py`, `rat\_client.py`

\- \*\*Leaf modules:\*\* `config.py`, `modules/\*`



\---



\## 6. Deployment Architecture



\### 6.1 Lab Deployment (Demo)



```

┌──────────────────┐        ┌──────────────────┐

│  Attack VM       │        │  Victim VM       │

│  ────────────    │        │  ────────────    │

│  C2 Server       │◀─HTTPS─│  RAT Client      │

│  Operator CLI    │        │  Chrome (Selenium)│

│  Dashboard       │        │  Webcam          │

│                  │        │                  │

│  10.0.0.10       │        │  10.0.0.20       │

└──────────────────┘        └──────────────────┘

&#x20;       │

&#x20;  isolated

&#x20;  network

```



\### 6.2 Docker Deployment (Production-like)



```

┌──────────────────────────────────────┐

│  Docker Host (Linux)                 │

│                                      │

│  ┌────────────────────────────────┐ │

│  │  cyberrecon-c2                 │ │

│  │  Port 8443                     │ │

│  │  Non-root user                 │ │

│  │  Healthcheck                   │ │

│  └────────────┬───────────────────┘ │

│               │                      │

│  ┌────────────▼───────────────────┐ │

│  │  cyberrecon-relay (optional)   │ │

│  │  Port 443                      │ │

│  └────────────────────────────────┘ │

└──────────────────────────────────────┘

```



\### 6.3 Kubernetes (future work)



CyberRecon could be containerized further with:



\- Deployment: C2 server (3 replicas)

\- Service: LoadBalancer on 8443

\- Ingress: HTTPS termination

\- Secrets: `CYBERRECON\_OPERATOR\_TOKEN`, CA bundle

\- ConfigMap: environment configuration



\---



\## 7. Design Decisions



\### 7.1 Why QR-encoded base64 JSON?



\*\*Rationale:\*\*



\- QR codes carry binary-safe data via base64

\- JSON payloads fit within Level-H error correction capacity

\- Mandiant's technique uses exactly this approach

\- Base64 encoding avoids Unicode issues in image rendering



\### 7.2 Why Selenium + headless Chrome?



\*\*Rationale:\*\*



\- Browser isolation strips dynamic content but not rendered pixels

\- Real Chrome fingerprint defeats basic bot detection

\- Chrome flags auto-grant media permissions

\- Graceful fallback if Chrome unavailable



\### 7.3 Why `secrets` over `uuid`?



\*\*Rationale:\*\*



\- `uuid.uuid4()\[:8]` truncates to 32 bits (brute-forceable)

\- `secrets.token\_hex(8)` provides 64 bits of CSPRNG entropy

\- Prevents victim-ID enumeration attacks



\### 7.4 Why in-memory storage (dict)?



\*\*Rationale:\*\*



\- Simplicity for lab demonstration

\- No database dependency

\- Fast lookups via Python dict

\- \*\*Future work:\*\* Redis or SQLite for persistence across restarts



\### 7.5 Why operator token auth over sessions?



\*\*Rationale:\*\*



\- Simple shared secret (env var)

\- No session state to manage

\- Suitable for single-operator scenario

\- Backed by `X-Operator-Token` header comparison



\---



\## 8. Quality Attributes



| Attribute | How Addressed |

|-----------|---------------|

| \*\*Performance\*\* | QR decode \~650ms; dashboard polls at 2s intervals |

| \*\*Security\*\* | 6 CWEs fixed; SAST clean; token auth; TLS verify |

| \*\*Reliability\*\* | Graceful fallback if Chrome missing; try/except guards |

| \*\*Maintainability\*\* | Modular structure; Ruff-clean; pytest-ready |

| \*\*Portability\*\* | Docker + non-root; runs on Linux server + Windows client |

| \*\*Observability\*\* | Print-based logs; `/check` health endpoint |



\---



\## 9. Architectural Risks



| Risk | Mitigation |

|------|------------|

| Selenium dependency on Chrome | Graceful fallback to `requests.get` |

| In-memory storage loss on restart | Documented limitation; Redis is future work |

| Slow QR channel (\~438 bytes/sec) | Accepted — matches Mandiant baseline |

| Port 8443 blocked by firewall | AWS relay fallback |

| Camera permission prompt in some browsers | Auto-grant flags configured |



\---



\## 10. References



\- `docs/report/03-requirements.md` — requirements

\- `docs/report/06-threat-model.md` — STRIDE analysis

\- `docs/report/07-security-features.md` — feature rationale

\- Mandiant (2024) — QR-C2 technique

\- `docs/diagrams/` — visual diagrams (Mermaid sources)

