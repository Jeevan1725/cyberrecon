\# 06 — Threat Model



\*\*Project:\*\* CyberRecon — QR-Code-Based C2 Framework

\*\*Document Version:\*\* 1.0

\*\*Date:\*\* 2026-09-30

\*\*Methodology:\*\* STRIDE + MITRE ATT\&CK + Attack Trees



\---



\## 1. Purpose \& Scope



This document models threats against CyberRecon \*\*from two perspectives\*\*:



1\. \*\*As a system under test\*\* — what could go wrong within the framework itself (vulnerabilities we need to fix)

2\. \*\*As a defensive exercise\*\* — what signals would defenders see if CyberRecon were deployed maliciously (detection engineering)



The purpose is dual:



\- Harden the framework against misuse or compromise (blue-team view)

\- Publish IOCs to aid defenders (research contribution)



\---



\## 2. System Assets



| Asset | Type | Impact if Compromised |

|-------|------|----------------------|

| Operator token (`CYBERRECON\_OPERATOR\_TOKEN`) | Secret | Full control over victims |

| Victim list (in-memory dict) | Data | Reconnaissance of targets |

| Exfiltrated data (screenshots, keystrokes, files) | Data | Privacy breach, forensic evidence |

| Command queue | State | Unauthorized command injection |

| C2 server | Service | Denial of service, hijack |

| Victim host | Endpoint | Full RAT compromise |



\---



\## 3. Trust Boundaries



```

&#x20; ┌────────────────────────┐   Untrusted  ┌────────────────────────┐

&#x20; │  Operator Network      │◀───Internet──│  Victim Network        │

&#x20; │  (trusted for this     │              │  (untrusted)           │

&#x20; │  research context)     │              │                        │

&#x20; └────────────┬───────────┘              └────────────┬───────────┘

&#x20;              │                                       │

&#x20;              ▼                                       ▼

&#x20; ┌────────────────────────────────────────────────────────────┐

&#x20; │                  Trust Boundary 1: HTTP                    │

&#x20; │                  Trust Boundary 2: Operator Token          │

&#x20; └────────────────────────────────────────────────────────────┘

&#x20;              │

&#x20;              ▼

&#x20; ┌────────────────────────┐

&#x20; │  C2 Server Process     │

&#x20; │  (trusted after token) │

&#x20; └────────────────────────┘

```



\*\*Trust boundaries:\*\*



1\. \*\*HTTP layer\*\* — no encryption by default (TLS is an optional enhancement)

2\. \*\*Operator token\*\* — separates authenticated operators from anonymous callers

3\. \*\*Command dispatch\*\* — separates operator intent from victim execution



\---



\## 4. STRIDE Analysis



\### 4.1 Spoofing (Identity)



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| An attacker impersonates a victim during `/register` | C2 API | Medium | Medium | Victim IDs are CSPRNG (64-bit); anomalies detectable via IP / hostname |

| An attacker forges `X-Operator-Token` | C2 API | Low | High | Token is 128-bit random (recommended); fail-closed on missing token |

| MITM spoofs C2 server identity | Victim client | Medium | High | \*\*Fixed in PR #9\*\* — TLS verification enforced |

| DNS spoofing of C2 hostname | Victim client | Low | High | Future: certificate pinning |



\### 4.2 Tampering (Integrity)



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| MITM modifies QR payload in transit | QR channel | Low | High | QR is a visual channel — no transit modification possible |

| Attacker modifies exfil data in transit | POST /exfil | Low | Medium | HMAC on payload is future work |

| Tampering with the victim's Chrome process | Victim host | Low | High | Out of scope — assumes trusted victim OS |



\### 4.3 Repudiation



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| Operator denies sending a command | C2 logs | Medium | Low | Print-based logging; signed audit log is future work |

| Victim denies exfiltration occurred | Victim host | Low | Low | Server-side timestamp + IP stored |



\### 4.4 Information Disclosure



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| Victim IDs enumerated via `/victim/<id>` | C2 API | High | Medium | \*\*Fixed in PR #12\*\* — 64-bit CSPRNG IDs |

| Screenshot / keystroke data intercepted on C2 | Server | Low | High | Future: encrypt at rest |

| Token leaked via process listing | C2 server | Low | High | Token from env var; not in command line |

| Hardcoded C2 IP leaked via source inspection | Source | High | Medium | \*\*Fixed in PR #13\*\* — env var driven |



\### 4.5 Denial of Service



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| Flood `/exfil` to exhaust memory | C2 server | Medium | Medium | Rate limiting + max exfil size (future) |

| Many fake `/register` calls | C2 server | High | Low | In-memory dict — no persistent growth across restarts |

| Malformed QR causing OpenCV crash | Victim | Low | Low | try/except around decode |



\### 4.6 Elevation of Privilege



| Threat | Target | Likelihood | Impact | Mitigation |

|--------|--------|------------|--------|------------|

| `shell=True` allows command injection | Victim | Medium | Critical | \*\*Fixed in PR #10\*\* — `shlex.split` + blocklist |

| Path traversal in launcher | Victim | Medium | High | \*\*Fixed in PR #11\*\* — realpath comparison |

| Unauthenticated `/command` endpoint | C2 API | High | Critical | \*\*Fixed in PR #8\*\* — operator token required |



\---



\## 5. MITRE ATT\&CK Mapping



The technique CyberRecon reproduces maps to the following ATT\&CK techniques:



\### 5.1 Tactics \& Techniques



| Tactic | Technique | ID | Relevance |

|--------|-----------|-----|-----------|

| \*\*Command and Control\*\* | Application Layer Protocol: Web Protocols | T1071.001 | HTTP-based C2 |

| \*\*Command and Control\*\* | Data Encoding: Standard Encoding | T1132.001 | Base64 QR payloads |

| \*\*Command and Control\*\* | Non-Application Layer Protocol | T1095 | TCP/HTTP fallback |

| \*\*Command and Control\*\* | Proxy: Domain Fronting | T1090.004 | AWS relay |

| \*\*Collection\*\* | Screen Capture | T1113 | Screenshot module |

| \*\*Collection\*\* | Video Capture | T1125 | Webcam module |

| \*\*Collection\*\* | Input Capture: Keylogging | T1056.001 | Keylogger module |

| \*\*Collection\*\* | Clipboard Data | T1115 | Clipboard steal |

| \*\*Discovery\*\* | System Information Discovery | T1082 | system\_info |

| \*\*Discovery\*\* | Process Discovery | T1057 | process\_list |

| \*\*Discovery\*\* | System Location Discovery | T1614 | gps\_location |

| \*\*Persistence\*\* | Registry Run Keys | T1547.001 | persistence.py |

| \*\*Persistence\*\* | Scheduled Task/Job | T1053.005 | persistence.py |

| \*\*Persistence\*\* | Boot or Logon Autostart | T1547 | startup folder |

| \*\*Defense Evasion\*\* | Indicator Removal: Clear Windows Event Logs | T1070.001 | stealth.py |

| \*\*Defense Evasion\*\* | Virtualization/Sandbox Evasion | T1497 | anti-VM checks |

| \*\*Exfiltration\*\* | Exfiltration Over C2 Channel | T1041 | `/exfil` POST |



\### 5.2 Defensive Value



By mapping to ATT\&CK, defenders can:



1\. Build detections for each technique (e.g., Sysmon Event ID 1 for Chrome spawn)

2\. Correlate CyberRecon IOCs with existing threat intel

3\. Test their SOC's coverage against this specific threat profile



\---



\## 6. Attack Tree (Defensive Detection Perspective)



\*\*Root:\*\* Detect CyberRecon deployment



```

Root: Detect CyberRecon Deployment

├── Network-layer signals

│   ├── Repeated POST to /exfil/\* every 15s → beaconing

│   ├── HTTP (not HTTPS) to unknown IP on 8443 → weak signal

│   └── Headless Chrome spawning from non-browser parent → strong signal

│

├── Host-layer signals (Windows)

│   ├── Registry Run key: HKCU\\...\\Run\\WindowsSecurityUpdate → persistence IOC

│   ├── Scheduled task: WindowsUpdateTask → persistence IOC

│   ├── Startup folder: update.exe → persistence IOC

│   ├── wevtutil cl Security / System → log tampering (Sysmon Event 1)

│   └── svchost.exe in %TEMP%\\WindowsUpdate\_\* → masquerade IOC

│

├── Application-layer signals

│   ├── Chrome with --headless=new + --disable-blink-features → CLI flags

│   ├── Chrome launched with --use-fake-ui-for-media-stream → auto-grant IOC

│   └── OpenCV QRCodeDetector library load in Python process → behavioural

│

└── Data-layer signals

&#x20;   ├── Large base64-encoded POSTs (screenshots) → DLP signature

&#x20;   ├── Repeated clipboard reads without user action → unusual

&#x20;   └── Webcam / screenshot access without user interaction → privacy violation

```



\---



\## 7. Assumptions \& Out-of-Scope



\### 7.1 Assumptions



\- Victim host is trusted enough to run the RAT (i.e., it's already compromised by the operator)

\- C2 server is not exposed publicly in the demo environment

\- Operator token is strong (≥ 128 bits) and rotated between sessions

\- Users have explicit authorization to test the system



\### 7.2 Out of Scope



\- Zero-day exploitation of the victim OS

\- Bypassing EDR / kernel-level protections

\- Cryptographic attacks against TLS (assumed strong)

\- Physical attacks on the C2 server

\- Social engineering beyond the SFX stage (which was removed)



\---



\## 8. Residual Risk



After the six CWE patches in Phase 1, the following residual risks remain:



| Residual Risk | Severity | Rationale |

|---------------|----------|-----------|

| HTTP (no TLS) in default deployment | Medium | Lab-only; HTTPS is a Phase-5 enhancement |

| No rate limiting on `/exfil` | Medium | Acceptable for single-operator demo |

| In-memory state loss on restart | Low | Documented limitation |

| No HMAC on QR payloads | Low | Visual channel is out-of-band; tampering requires physical access |

| Stealth module uses `except Exception: pass` | Low | By design — swallowing errors is the intent |



\---



\## 9. Defensive Recommendations



For defenders who suspect CyberRecon (or a similar QR-C2 technique):



\### 9.1 Network



\- Alert on `POST /exfil/\*` patterns with base64-encoded bodies

\- Alert on repeated connections to unusual ports (8443)

\- Monitor for Chrome headless traffic to non-standard endpoints



\### 9.2 Endpoint



\- Monitor registry `Run` keys for unfamiliar entries

\- Watch for scheduled task creation with suspicious command-lines

\- Detect `wevtutil cl` invocations (log clearing)

\- Flag `svchost.exe` running from `%TEMP%` or non-System32 paths

\- Monitor Chrome spawns by Python / non-browser processes



\### 9.3 Data



\- DLP signatures for base64-encoded image data in HTTP POST bodies

\- Alert on outbound POST > 100 KB from non-browser processes

\- Monitor for camera / microphone device access without user action



\### 9.4 Process



\- Audit Python interpreter spawning Chrome subprocess

\- Baseline normal Chrome CLI flags; alert on `--use-fake-ui-for-media-stream`



\---



\## 10. References



\- STRIDE (Microsoft) — threat modeling methodology

\- MITRE ATT\&CK (v14) — adversarial tactics and techniques

\- OWASP Threat Modeling Cheat Sheet

\- Mandiant (2024) — "(QR) Coding My Way Out of Here"

\- NIST SP 800-154 (Guide to Data-Centric System Threat Modeling)



\---



\## 11. Change Log



| Date | Change | Author |

|------|--------|--------|

| 2026-09-30 | Initial threat model | R Jeevan |

