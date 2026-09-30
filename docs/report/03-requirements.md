# 03 — Software Requirements Specification (SRS)

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Authors:** Vekeshhari Rajasekar, R Jeevan
**Guide:** Dr. S. Udhayakumar

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for CyberRecon, a self-contained QR-Code-based Command & Control (C2) framework that reproduces Mandiant's 2024 browser-isolation bypass technique for academic research and defensive analysis.

### 1.2 Scope

CyberRecon comprises a Flask-based C2 server with QR encoder and operator dashboard, a victim-side RAT client (Python) that decodes QR commands, an operator CLI for issuing commands, an optional AWS relay for traffic obfuscation, a local AI agent for natural-language command parsing, and SAST/CI infrastructure for security validation.

**Out of scope:** production deployment, distribution to unauthorized parties, use against non-authorized systems.

### 1.3 Intended Audience

- Academic evaluators (project guide, panel)
- Security researchers studying browser-isolation bypasses
- Defenders building detections for QR-based C2

### 1.4 Definitions

| Term | Meaning |
|------|---------|
| **C2** | Command & Control — the channel through which an operator sends commands to a victim |
| **RAT** | Remote Access Trojan — the client that executes commands on the victim |
| **QR channel** | The visual-pixel C2 channel using encoded QR PNG images |
| **Browser Isolation** | Technology that executes web content in a remote sandbox and streams only rendered pixels to the user |
| **SFX** | Self-Extracting archive (removed from scope in Phase 1) |
| **SAST** | Static Application Security Testing |

---

## 2. Overall Description

### 2.1 Product Perspective

CyberRecon reproduces the C2-in-browser-isolation technique published by Mandiant in 2024. Unlike the reference implementation (which requires Cobalt Strike), CyberRecon is fully self-contained.

### 2.2 Architecture Overview
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Operator CLI │───▶│ C2 Server │───▶│ QR Channel │
│ │◀───│ (Flask) │ │ (visual) │
└───────────────┘ └───────┬───────┘ └───────┬───────┘
│ │
▼ ▼
┌───────────────┐ ┌───────────────┐
│ AWS Relay │ │ Victim Client │
│ (optional) │ │ (Python RAT) │
└───────────────┘ └───────┬───────┘
│
▼
┌───────────────┐
│ Exfil (HTTP) │
└───────────────┘


### 2.3 User Classes

| Class | Description | Interaction |
|-------|-------------|-------------|
| **Operator** | Authorized researcher | Issues commands via CLI or dashboard |
| **Victim** | Target host (lab VM) | Runs RAT client; executes commands; exfiltrates data |
| **Defender** | Blue team analyst | Consumes published IOCs from ETHICS.md |

### 2.4 Constraints

- Python 3.10+ required on both server and client
- Google Chrome required for Selenium-based QR fetch
- Only tested on Windows 10/11 (client) and Linux (server)
- Network access required for C2 ↔ victim communication

### 2.5 Assumptions

- Victim hosts are on the same isolated network as the C2 server
- Users have explicit authorization from the system owner
- The technique is used for research or defensive purposes only

---

## 3. Functional Requirements

### 3.1 C2 Server (Flask)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-01** | The C2 server shall register victims via `POST /register` and assign a unique 64-bit hex ID | High | Integration test |
| **FR-02** | The C2 server shall encode queued commands as base64-JSON and serve them as QR PNGs via `GET /qr/<victim_id>` | High | Unit test |
| **FR-03** | The C2 server shall protect `POST /command/<victim_id>` and `GET /download-all/<victim_id>` with operator token auth (`X-Operator-Token` header) | High | Security test |
| **FR-04** | The C2 server shall receive exfiltrated data via `POST /exfil/<victim_id>` and store it by type | High | Integration test |
| **FR-05** | The C2 server shall serve a live dashboard at `/dashboard` | Medium | Manual test |
| **FR-06** | The C2 server shall serve the latest screenshot / webcam frame per victim | Medium | Manual test |
| **FR-07** | The C2 server shall bundle all exfiltrated data per victim as a downloadable ZIP | Medium | Manual test |

### 3.2 Victim Client (RAT)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-08** | The client shall register with the C2 server on startup | High | Integration test |
| **FR-09** | The client shall fetch the QR PNG using Selenium + headless Chrome and decode it via OpenCV | High | Unit test |
| **FR-10** | The client shall execute the following commands: `whoami`, `screenshot`, `webcam_capture`, `keylogger`, `clipboard_steal`, `gps_location`, `process_list`, `system_info`, `list_files`, `shell`, `persist`, `self_destruct` | High | Command-by-command test |
| **FR-11** | The client shall exfiltrate results via HTTP POST to `/exfil/<victim_id>` | High | Integration test |
| **FR-12** | The client shall support a TCP → HTTP → QR fallback chain | Medium | Manual test |
| **FR-13** | The client shall attempt persistence via 5 methods (registry, task, startup, WMI, service) | Medium | Manual test |

### 3.3 Operator CLI

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-14** | The CLI shall list active victims via `victims` command | High | Manual test |
| **FR-15** | The CLI shall send commands via `select <id>` then `<command>` | High | Manual test |
| **FR-16** | The CLI shall require an operator token (env var or `--token` flag) | High | Security test |

### 3.4 AWS Relay (Optional)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-17** | The relay shall proxy HTTP requests to the C2 backend | Low | Manual test |
| **FR-18** | The relay shall support domain-fronting configuration | Low | Manual test |

### 3.5 AI Agent (Optional)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-19** | The AI agent shall parse natural-language commands into structured C2 commands | Low | Unit test |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| **NFR-01** | QR decode latency | ≤ 1s | Stopwatch / log |
| **NFR-02** | QR channel throughput | ~438 bytes/sec (Mandiant baseline) | Simulated test |
| **NFR-03** | C2 server response time | < 200ms (local) | curl -w |

### 4.2 Security

| ID | Requirement | Priority |
|----|-------------|----------|
| **NFR-04** | All operator endpoints shall require authenticated token | High |
| **NFR-05** | TLS verification shall be enforced by default | High |
| **NFR-06** | Command execution shall use `shell=False` (no `shell=True`) | High |
| **NFR-07** | File paths shall be validated against the base directory | High |
| **NFR-08** | Victim IDs shall be generated with `secrets.token_hex` (CSPRNG) | High |
| **NFR-09** | No hardcoded credentials or IP addresses | High |
| **NFR-10** | Zero HIGH-severity SAST findings | High |

### 4.3 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-11** | C2 server uptime during demo | 100% |
| **NFR-12** | Client shall not crash on Chrome absence | Graceful fallback |

### 4.4 Maintainability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-13** | Code shall pass Ruff with 0 errors | Enforced via CI |
| **NFR-14** | All Python files shall parse cleanly (`ast.parse`) | Enforced via CI |
| **NFR-15** | External dependencies ≤ 12 | Measured |

### 4.5 Portability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-16** | C2 server shall run on Linux (Docker) | Verified |
| **NFR-17** | Client shall run on Windows 10/11 | Verified |
| **NFR-18** | Docker image builds reproducibly | Multi-stage build |

### 4.6 Compliance

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-19** | Only used in isolated lab environments with explicit authorization | ETHICS.md |
| **NFR-20** | Published IOCs to aid defenders | ETHICS.md |

---

## 5. External Interfaces

### 5.1 REST API

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/` | GET | None | Server status |
| `/register` | POST | None | Register victim |
| `/qr/<victim_id>` | GET | None | QR-encoded command |
| `/poll/<victim_id>` | GET | None | HTTP fallback |
| `/command/<victim_id>` | POST | **Operator token** | Queue command |
| `/exfil/<victim_id>` | POST | None | Receive exfil data |
| `/victims` | GET | None | List victims |
| `/victim/<victim_id>` | GET | None | Victim details |
| `/exfil-data/<victim_id>` | GET | None | Exfil summary |
| `/latest_screenshot/<victim_id>` | GET | None | Latest screenshot |
| `/latest_webcam/<victim_id>` | GET | None | Latest webcam frame |
| `/download-all/<victim_id>` | GET | **Operator token** | Bulk ZIP download |
| `/dashboard` | GET | None | Parrot Viewer UI |
| `/check` | GET | None | Health check |

### 5.2 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CYBERRECON_OPERATOR_TOKEN` | (required) | Auth token for protected endpoints |
| `CYBERRECON_REQUIRE_AUTH` | `true` | Toggle auth enforcement |
| `CYBERRECON_C2` | `http://127.0.0.1:8443` | C2 server URL (client) |
| `CYBERRECON_CA_BUNDLE` | (optional) | Custom CA bundle for TLS |
| `CYBERRECON_SFX_PASSWORD` | (auto-generated) | SFX encryption password |
| `C2_HOST` | `0.0.0.0` | C2 bind address |
| `C2_PORT` | `8443` | C2 bind port |

### 5.3 Command Line

- **Server:** `python c2_server.py`
- **Client:** `python rat_client.py --c2 <url> --auto-register`
- **Operator:** `python operator_cli.py --c2 <url> --token <token>`
- **Unified:** `python main.py --mode {c2|operator|decoder|rat|relay|test}`

---

## 6. Verification Matrix

| Requirement | Test Location | Status |
|-------------|---------------|--------|
| FR-01 to FR-07 | `tests/` (future) + manual demo | Partial |
| FR-08 to FR-13 | Manual + smoke tests | Verified |
| FR-14 to FR-16 | Manual + CI | Verified |
| NFR-04 to NFR-10 | `docs/report/08-security-testing.md` | Verified |
| NFR-13 to NFR-14 | GitHub Actions CI | Verified |

---

## 7. Traceability

Each requirement traces to a CWE (for security requirements), a CI check (where automatable), or a manual demo step (for the final presentation).

---

## 8. Refe# 03 — Software Requirements Specification (SRS)

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Authors:** Vekeshhari Rajasekar, R Jeevan
**Guide:** Dr. S. Udhayakumar

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for CyberRecon, a self-contained QR-Code-based Command & Control (C2) framework that reproduces Mandiant's 2024 browser-isolation bypass technique for academic research and defensive analysis.

### 1.2 Scope

CyberRecon comprises:

- A Flask-based C2 server with QR encoder and operator dashboard
- A victim-side RAT client (Python) that decodes QR commands
- An operator CLI for issuing commands
- An optional AWS relay for traffic obfuscation
- A local AI agent for natural-language command parsing
- SAST/CI infrastructure for security validation

**Out of scope:** production deployment, distribution to unauthorized parties, use against non-authorized systems.

### 1.3 Intended Audience

- Academic evaluators (project guide, panel)
- Security researchers studying browser-isolation bypasses
- Defenders building detections for QR-based C2

### 1.4 Definitions

| Term | Meaning |
|------|---------|
| **C2** | Command & Control — the channel through which an operator sends commands to a victim |
| **RAT** | Remote Access Trojan — the client that executes commands on the victim |
| **QR channel** | The visual-pixel C2 channel using encoded QR PNG images |
| **Browser Isolation** | Technology that executes web content in a remote sandbox and streams only rendered pixels to the user |
| **SFX** | Self-Extracting archive (removed from scope in Phase 1) |
| **SAST** | Static Application Security Testing |

---

## 2. Overall Description

### 2.1 Product Perspective

CyberRecon reproduces the C2-in-browser-isolation technique published by Mandiant in 2024. Unlike the reference implementation (which requires Cobalt Strike), CyberRecon is fully self-contained.

### 2.2 Architecture Overview

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

### 2.3 User Classes

| Class | Description | Interaction |
|-------|-------------|-------------|
| **Operator** | Authorized researcher | Issues commands via CLI or dashboard |
| **Victim** | Target host (lab VM) | Runs RAT client; executes commands; exfiltrates data |
| **Defender** | Blue team analyst | Consumes published IOCs from ETHICS.md |

### 2.4 Constraints

- Python 3.10+ required on both server and client
- Google Chrome required for Selenium-based QR fetch
- Only tested on Windows 10/11 (client) and Linux (server)
- Network access required for C2 ↔ victim communication

### 2.5 Assumptions

- Victim hosts are on the same isolated network as the C2 server
- Users have explicit authorization from the system owner
- The technique is used for research or defensive purposes only

---

## 3. Functional Requirements

### 3.1 C2 Server (Flask)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-01** | The C2 server shall register victims via `POST /register` and assign a unique 64-bit hex ID | High | Integration test |
| **FR-02** | The C2 server shall encode queued commands as base64-JSON and serve them as QR PNGs via `GET /qr/<victim_id>` | High | Unit test |
| **FR-03** | The C2 server shall protect `POST /command/<victim_id>` and `GET /download-all/<victim_id>` with operator token auth (`X-Operator-Token` header) | High | Security test |
| **FR-04** | The C2 server shall receive exfiltrated data via `POST /exfil/<victim_id>` and store it by type (screenshot, keystroke, GPS, etc.) | High | Integration test |
| **FR-05** | The C2 server shall serve a live dashboard at `/dashboard` | Medium | Manual test |
| **FR-06** | The C2 server shall serve the latest screenshot / webcam frame per victim | Medium | Manual test |
| **FR-07** | The C2 server shall bundle all exfiltrated data per victim as a downloadable ZIP | Medium | Manual test |

### 3.2 Victim Client (RAT)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-08** | The client shall register with the C2 server on startup | High | Integration test |
| **FR-09** | The client shall fetch the QR PNG using Selenium + headless Chrome and decode it via OpenCV | High | Unit test |
| **FR-10** | The client shall execute: whoami, screenshot, webcam_capture, keylogger, clipboard_steal, gps_location, process_list, system_info, list_files, shell, persist, self_destruct | High | Command-by-command test |
| **FR-11** | The client shall exfiltrate results via HTTP POST to `/exfil/<victim_id>` | High | Integration test |
| **FR-12** | The client shall support a TCP → HTTP → QR fallback chain | Medium | Manual test |
| **FR-13** | The client shall attempt persistence via 5 methods (registry, task, startup, WMI, service) | Medium | Manual test |

### 3.3 Operator CLI

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-14** | The CLI shall list active victims via `victims` command | High | Manual test |
| **FR-15** | The CLI shall send commands via `select <id>` then `<command>` | High | Manual test |
| **FR-16** | The CLI shall require an operator token (env var or `--token` flag) | High | Security test |

### 3.4 AWS Relay (Optional)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-17** | The relay shall proxy HTTP requests to the C2 backend | Low | Manual test |
| **FR-18** | The relay shall support domain-fronting configuration | Low | Manual test |

### 3.5 AI Agent (Optional)

| ID | Requirement | Priority | Verification |
|----|-------------|----------|--------------|
| **FR-19** | The AI agent shall parse natural-language commands ("take a screenshot") into structured C2 commands | Low | Unit test |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| **NFR-01** | QR decode latency | ≤ 1s | Stopwatch / log |
| **NFR-02** | QR channel throughput | ~438 bytes/sec (Mandiant baseline) | Simulated test |
| **NFR-03** | C2 server response time | < 200ms (local) | curl -w |

### 4.2 Security

| ID | Requirement | Priority |
|----|-------------|----------|
| **NFR-04** | All operator endpoints shall require authenticated token | High |
| **NFR-05** | TLS verification shall be enforced by default | High |
| **NFR-06** | Command execution shall use `shell=False` (no `shell=True`) | High |
| **NFR-07** | File paths shall be validated against the base directory | High |
| **NFR-08** | Victim IDs shall be generated with `secrets.token_hex` (CSPRNG) | High |
| **NFR-09** | No hardcoded credentials or IP addresses | High |
| **NFR-10** | Zero HIGH-severity SAST findings | High |

### 4.3 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-11** | C2 server uptime during demo | 100% |
| **NFR-12** | Client shall not crash on Chrome absence | Graceful fallback |

### 4.4 Maintainability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-13** | Code shall pass Ruff with 0 errors | Enforced via CI |
| **NFR-14** | All Python files shall parse cleanly (`ast.parse`) | Enforced via CI |
| **NFR-15** | External dependencies ≤ 12 | Measured |

### 4.5 Portability

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-16** | C2 server shall run on Linux (Docker) | Verified |
| **NFR-17** | Client shall run on Windows 10/11 | Verified |
| **NFR-18** | Docker image build without network access to PyPI at runtime | Multi-stage build |

### 4.6 Compliance

| ID | Requirement | Target |
|----|-------------|--------|
| **NFR-19** | Only used in isolated lab environments with explicit authorization | ETHICS.md |
| **NFR-20** | Published IOCs to aid defenders | ETHICS.md |

---

## 5. External Interfaces

### 5.1 REST API

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/` | GET | None | Server status |
| `/register` | POST | None | Register victim |
| `/qr/<victim_id>` | GET | None | QR-encoded command |
| `/poll/<victim_id>` | GET | None | HTTP fallback |
| `/command/<victim_id>` | POST | **Operator token** | Queue command |
| `/exfil/<victim_id>` | POST | None | Receive exfil data |
| `/victims` | GET | None | List victims |
| `/victim/<victim_id>` | GET | None | Victim details |
| `/exfil-data/<victim_id>` | GET | None | Exfil summary |
| `/latest_screenshot/<victim_id>` | GET | None | Latest screenshot |
| `/latest_webcam/<victim_id>` | GET | None | Latest webcam frame |
| `/download-all/<victim_id>` | GET | **Operator token** | Bulk ZIP download |
| `/dashboard` | GET | None | Parrot Viewer UI |
| `/check` | GET | None | Health check |

### 5.2 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CYBERRECON_OPERATOR_TOKEN` | (required) | Auth token for protected endpoints |
| `CYBERRECON_REQUIRE_AUTH` | `true` | Toggle auth enforcement |
| `CYBERRECON_C2` | `http://127.0.0.1:8443` | C2 server URL (client) |
| `CYBERRECON_CA_BUNDLE` | (optional) | Custom CA bundle for TLS |
| `CYBERRECON_SFX_PASSWORD` | (auto-generated) | SFX encryption password |
| `C2_HOST` | `0.0.0.0` | C2 bind address |
| `C2_PORT` | `8443` | C2 bind port |

### 5.3 Command Line

**Server:** `python c2_server.py`
**Client:** `python rat_client.py --c2 <url> --auto-register`
**Operator:** `python operator_cli.py --c2 <url> --token <token>`
**Unified:** `python main.py --mode {c2|operator|decoder|rat|relay|test}`

---

## 6. Verification Matrix

| Requirement | Test Location | Status |
|-------------|---------------|--------|
| FR-01 to FR-07 | `tests/` + manual demo | Partial |
| FR-08 to FR-13 | Manual + smoke tests | Verified |
| FR-14 to FR-16 | Manual + CI | Verified |
| NFR-04 to NFR-10 | `docs/report/08-security-testing.md` | Verified |
| NFR-13 to NFR-14 | GitHub Actions CI | Verified |

---

## 7. Traceability

Each requirement traces to a CWE (for security requirements), a CI check (where automatable), and a manual demo step (for the final presentation).

---

## 8. References

- IEEE 830-1998 (Software Requirements Specifications)
- Mandiant (2024) — "(QR) Coding My Way Out of Here"
- Project `ETHICS.md` for legal and ethical constraints
- `docs/report/06-threat-model.md` for STRIDE analysis
- `docs/report/07-security-features.md` for feature-level rationalerences

- IEEE 830-1998 (Software Requirements Specifications)
- Mandiant (2024) — "(QR) Coding My Way Out of Here"
- Project `ETHICS.md` for legal and ethical constraints
- `docs/report/06-threat-model.md` for STRIDE analysis
- `docs/report/07-security-features.md` for feature-level rationale