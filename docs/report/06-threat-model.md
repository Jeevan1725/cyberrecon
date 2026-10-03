# 06 — Threat Model

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Methodology:** STRIDE + MITRE ATT&CK + Attack Trees

---
> **Update (v3.5) — 2026-10-03:** Five additional security controls were added on top of the v3.0 baseline. See [`10-hardening-changelog.md`](10-hardening-changelog.md) for the full catalog and threat mapping.
>
> **New controls (v3.5):**
> 1. **AES-256-GCM QR payload encryption** — commands encrypted before QR encoding (CWE-311 mitigation)
> 2. **Victim shared-key authentication** — `X-Victim-Key` header or `?vkey=` query on all victim-side routes
> 3. **Dashboard session login** — `require_dashboard_login` gate on read-only APIs and dashboard HTML; `HttpOnly` + `Secure` + `SameSite=Lax` cookies (CWE-384, 613, 539 mitigation)
> 4. **Server-side wipe endpoint** — `/self_destruct_notify/<id>` purges victim record on self-destruct
> 5. **Anti-forensic self-destruct** — userland cleanup of registry, temp, Chrome profiles, sandbox, and payload binary (see `self-destruct-sequence.puml`)

## 1. Purpose & Scope

This document models threats against CyberRecon from two perspectives:

1. **As a system under test** — what could go wrong within the framework itself (vulnerabilities we need to fix)
2. **As a defensive exercise** — what signals would defenders see if CyberRecon were deployed maliciously (detection engineering)

The purpose is dual: harden the framework against misuse or compromise, and publish IOCs to aid defenders.

---

## 2. System Assets

| Asset | Type | Impact if Compromised |
|-------|------|----------------------|
| Operator token (`CYBERRECON_OPERATOR_TOKEN`) | Secret | Full control over victims |
| Victim list (in-memory dict) | Data | Reconnaissance of targets |
| Exfiltrated data (screenshots, keystrokes, files) | Data | Privacy breach, forensic evidence |
| Command queue | State | Unauthorized command injection |
| C2 server | Service | Denial of service, hijack |
| Victim host | Endpoint | Full RAT compromise |

---

## 3. Trust Boundaries

```
  ┌────────────────────────┐   Untrusted  ┌────────────────────────┐
  │  Operator Network      │◀───Internet──│  Victim Network        │
  │  (trusted for this     │              │  (untrusted)           │
  │  research context)     │              │                        │
  └────────────┬───────────┘              └────────────┬───────────┘
               │                                       │
               ▼                                       ▼
  ┌────────────────────────────────────────────────────────────┐
  │                  Trust Boundary 1: HTTP                    │
  │                  Trust Boundary 2: Operator Token          │
  └────────────────────────────────────────────────────────────┘
```

**Trust boundaries:**

1. **HTTP layer** — no encryption by default (TLS is optional enhancement)
2. **Operator token** — separates authenticated operators from anonymous callers
3. **Command dispatch** — separates operator intent from victim execution

---

## 4. STRIDE Analysis

### 4.1 Spoofing (Identity)

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| Attacker impersonates victim during `/register` | C2 API | Medium | Medium | Victim IDs are CSPRNG (64-bit); anomalies detectable via IP/hostname |
| Attacker forges `X-Operator-Token` | C2 API | Low | High | Token is 128-bit random; fail-closed on missing token |
| MITM spoofs C2 server identity | Victim client | Medium | High | **Fixed in PR #9** — TLS verification enforced |
| DNS spoofing of C2 hostname | Victim client | Low | High | Future: certificate pinning |

### 4.2 Tampering (Integrity)

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| MITM modifies QR payload in transit | QR channel | Low | High | QR is visual — no transit modification possible |
| Attacker modifies exfil data in transit | POST /exfil | Low | Medium | HMAC on payload is future work |
| Tampering with victim's Chrome process | Victim host | Low | High | Out of scope — assumes trusted victim OS |

### 4.3 Repudiation

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| Operator denies sending a command | C2 logs | Medium | Low | Print-based logging; signed audit log is future work |
| Victim denies exfiltration occurred | Victim host | Low | Low | Server-side timestamp + IP stored |

### 4.4 Information Disclosure

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| Victim IDs enumerated via `/victim/<id>` | C2 API | High | Medium | **Fixed in PR #12** — 64-bit CSPRNG IDs |
| Screenshot/keystroke data intercepted on C2 | Server | Low | High | Future: encrypt at rest |
| Token leaked via process listing | C2 server | Low | High | Token from env var; not in command line |
| Hardcoded C2 IP leaked via source inspection | Source | High | Medium | **Fixed in PR #13** — env var driven |

### 4.5 Denial of Service

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| Flood `/exfil` to exhaust memory | C2 server | Medium | Medium | Rate limiting + max exfil size (future) |
| Many fake `/register` calls | C2 server | High | Low | In-memory dict — no persistent growth across restarts |
| Malformed QR causing OpenCV crash | Victim | Low | Low | try/except around decode |

### 4.6 Elevation of Privilege

| Threat | Target | Likelihood | Impact | Mitigation |
|--------|--------|------------|--------|------------|
| `shell=True` allows command injection | Victim | Medium | Critical | **Fixed in PR #10** — `shlex.split` + blocklist |
| Path traversal in launcher | Victim | Medium | High | **Fixed in PR #11** — realpath comparison |
| Unauthenticated `/command` endpoint | C2 API | High | Critical | **Fixed in PR #8** — operator token required |

---

## 5. MITRE ATT&CK Mapping

### 5.1 Tactics & Techniques

| Tactic | Technique | ID | Relevance |
|--------|-----------|-----|-----------|
| Command and Control | Application Layer Protocol: Web Protocols | T1071.001 | HTTP-based C2 |
| Command and Control | Data Encoding: Standard Encoding | T1132.001 | Base64 QR payloads |
| Command and Control | Non-Application Layer Protocol | T1095 | TCP/HTTP fallback |
| Command and Control | Proxy: Domain Fronting | T1090.004 | AWS relay |
| Collection | Screen Capture | T1113 | Screenshot module |
| Collection | Video Capture | T1125 | Webcam module |
| Collection | Input Capture: Keylogging | T1056.001 | Keylogger module |
| Collection | Clipboard Data | T1115 | Clipboard steal |
| Discovery | System Information Discovery | T1082 | system_info |
| Discovery | Process Discovery | T1057 | process_list |
| Discovery | System Location Discovery | T1614 | gps_location |
| Persistence | Registry Run Keys | T1547.001 | persistence.py |
| Persistence | Scheduled Task/Job | T1053.005 | persistence.py |
| Persistence | Boot or Logon Autostart | T1547 | startup folder |
| Defense Evasion | Indicator Removal: Clear Windows Event Logs | T1070.001 | stealth.py |
| Defense Evasion | Virtualization/Sandbox Evasion | T1497 | anti-VM checks |
| Exfiltration | Exfiltration Over C2 Channel | T1041 | `/exfil` POST |

### 5.2 Defensive Value

By mapping to ATT&CK, defenders can build detections for each technique (e.g., Sysmon Event ID 1 for Chrome spawn), correlate CyberRecon IOCs with existing threat intel, and test their SOC's coverage.

---

## 6. Attack Tree (Defensive Detection Perspective)

![Attack Tree](../diagrams/attack-tree.png)

The tree is organized into four detection layers:

| Layer | Signal Examples |
|-------|-----------------|
| **Network** | Repeated POST to `/exfil/*` (beaconing), HTTP to non-standard ports, headless Chrome traffic |
| **Host (Windows)** | Registry Run keys, scheduled tasks, `wevtutil cl`, `svchost.exe` in `%TEMP%` |
| **Application** | Chrome `--headless=new` + `--disable-blink-features`, `--use-fake-ui-for-media-stream`, OpenCV library loads |
| **Data** | Large base64 POSTs, unusual clipboard reads, webcam access without user action |

See **[docs/diagrams/attack-tree.md](../diagrams/attack-tree.md)** for the full-resolution diagram with IOC annotations.
---

## 7. Assumptions & Out-of-Scope

### 7.1 Assumptions

- Victim host is trusted enough to run the RAT (already compromised by operator)
- C2 server is not exposed publicly in the demo environment
- Operator token is strong (≥ 128 bits) and rotated between sessions
- Users have explicit authorization to test the system

### 7.2 Out of Scope

- Zero-day exploitation of victim OS
- Bypassing EDR / kernel-level protections
- Cryptographic attacks against TLS (assumed strong)
- Physical attacks on the C2 server
- Social engineering beyond the SFX stage (removed)

---

## 8. Residual Risk

| Residual Risk | Severity | Rationale |
|---------------|----------|-----------|
| HTTP (no TLS) in default deployment | Medium | Lab-only; HTTPS is a Phase-5 enhancement |
| No rate limiting on `/exfil` | Medium | Acceptable for single-operator demo |
| In-memory state loss on restart | Low | Documented limitation |
| No HMAC on QR payloads | Low | Visual channel is out-of-band |
| Stealth module uses `except Exception: pass` | Low | By design |

---

## 9. Defensive Recommendations

### 9.1 Network
- Alert on `POST /exfil/*` patterns with base64-encoded bodies
- Alert on repeated connections to unusual ports (8443)
- Monitor for Chrome headless traffic to non-standard endpoints

### 9.2 Endpoint
- Monitor registry `Run` keys for unfamiliar entries
- Watch for scheduled task creation with suspicious command-lines
- Detect `wevtutil cl` invocations (log clearing)
- Flag `svchost.exe` running from `%TEMP%` or non-System32 paths
- Monitor Chrome spawns by Python / non-browser processes

### 9.3 Data
- DLP signatures for base64-encoded image data in HTTP POST bodies
- Alert on outbound POST > 100 KB from non-browser processes
- Monitor for camera / microphone device access without user action

### 9.4 Process
- Audit Python interpreter spawning Chrome subprocess
- Baseline normal Chrome CLI flags; alert on `--use-fake-ui-for-media-stream`

---

## 10. References

- STRIDE (Microsoft)
- MITRE ATT&CK (v14)
- OWASP Threat Modeling Cheat Sheet
- Mandiant (2024) — "(QR) Coding My Way Out of Here"
- NIST SP 800-154

---

## 11. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-30 | Initial threat model | R Jeevan |
