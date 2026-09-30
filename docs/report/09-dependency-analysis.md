# 09 — Dependency Analysis

**Project:** CyberRecon — QR-Code-Based C2 Framework
**Document Version:** 1.0
**Date:** 2026-09-30
**Authors:** Vekeshhari Rajasekar, R Jeevan

---

## 1. Purpose

This document analyzes CyberRecon's:

1. **Internal module dependencies** — which Python files depend on each other (fan-in / fan-out)
2. **External dependencies** — third-party libraries and why each is needed
3. **Dependency reduction** — how the footprint went from 20+ to 11 direct dependencies
4. **Targeted improvements** — what we would further consolidate in future work

The goal is to demonstrate understanding of coupling, cohesion, and supply-chain risk reduction.

---

## 2. Internal Module Dependency Graph

### 2.1 Dependency Hierarchy

```
                     ┌──────────────────┐
                     │     main.py      │  (entry — depends on all)
                     └────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  ┌───────────┐         ┌───────────┐         ┌───────────┐
  │ c2_server │         │rat_client │         │operator_  │
  │   .py     │◀────────│   .py     │────────▶│  cli.py   │
  └─────┬─────┘         └─────┬─────┘         └───────────┘
        │                     │
        │                     ▼
        │              ┌──────────────────┐
        │              │    modules/      │
        │              │  (6 feature      │
        │              │   modules)       │
        │              └────────┬─────────┘
        │                       │
        ▼                       ▼
  ┌──────────────┐      ┌──────────────┐
  │  config.py   │      │ ai_agent.py  │
  │  (leaf)      │      │  (leaf)      │
  └──────────────┘      └──────────────┘
```

### 2.2 Fan-In / Fan-Out Table

| Module | Fan-In | Fan-Out | Type |
|--------|--------|---------|------|
| `config.py` | 10 | 0 | **Independent / Leaf** |
| `ai_agent.py` | 1 (main) | 0 | **Independent** |
| `modules/*` (6 files) | 2 each | 1 (config) | Semi-independent |
| `c2_server.py` | 2 (main, rat_client) | 2 | **Hub** |
| `rat_client.py` | 1 (main) | 12 | **God module** ⚠️ |
| `operator_cli.py` | 1 (main) | 1 | Leaf |
| `aws_relay.py` | 1 (main) | 1 | Leaf |
| `main.py` | 0 | 6 | Entry point |

**Observations:**

- **1 truly independent module:** `config.py` (fan-in = 10, fan-out = 0)
- **1 orphan module:** `ai_agent.py` (imported only by `main.py`)
- **2 hub modules:** `c2_server.py`, `rat_client.py`
- **1 god module:** `rat_client.py` (fan-out = 12) ⚠️
- **No circular dependencies** ✓

### 2.3 God Module Analysis — `rat_client.py`

`rat_client.py` has fan-out = 12 and ~550 LOC, making it a classic god module anti-pattern.

**Current structure:**

```python
class QRDecoder:
    def __init__(self, c2_url, victim_id): ...
    def register_with_c2(self): ...
    def init_headless_browser(self): ...
    def capture_qr_screenshot(self): ...
    def decode_qr_image(self): ...
    def listen_for_commands(self): ...
    def execute_command(self): ...
    def _handle_whoami(self): ...
    def _handle_screenshot(self): ...
    def _handle_webcam(self): ...
    def _handle_keylogger(self): ...
    def _handle_clipboard(self): ...
    def _handle_download(self): ...
    def _handle_gps(self): ...
    def _handle_process_list(self): ...
    def _handle_system_info(self): ...
    def _handle_list_files(self): ...
    def _handle_shell(self): ...
    def _handle_persist(self): ...
    def _handle_self_destruct(self): ...
    def _handle_unknown(self): ...
    def _exfil(self): ...
    def cleanup(self): ...
```

**Recommended refactor for future work:**

```python
rat_client/
├── __init__.py
├── qr_decoder.py         # Selenium + OpenCV logic only
├── dispatcher.py         # command routing
├── exfil_client.py       # HTTP POST
├── browser_channel.py    # Selenium wrapper with fallback
└── handlers/
    ├── __init__.py
    ├── system.py         # whoami, system_info, process_list
    ├── capture.py        # screenshot, webcam
    ├── spy.py            # keylogger, clipboard
    ├── location.py       # gps
    ├── files.py          # download, list_files
    └── control.py        # persist, self_destruct, shell
```

**Benefits:** Smaller modules, single responsibility, easier to test.

**Why we didn't refactor now:** Time-boxed for the final demo; documented as future work.

---

## 3. External Dependency Analysis

### 3.1 Current Runtime Dependencies (11)

| # | Package | Version | Purpose | Category |
|---|---------|---------|---------|----------|
| 1 | `flask` | ≥2.3.0 | C2 HTTP server + dashboard | Server |
| 2 | `requests` | ≥2.34.2 | HTTP client | HTTP |
| 3 | `pillow` | ≥12.3.0 | Image encoding/decoding | Image |
| 4 | `qrcode[pil]` | ≥8.2 | QR PNG generation | QR |
| 5 | `opencv-python` | ≥4.8.0 | QR decode + webcam | QR / Video |
| 6 | `numpy` | ≥1.24.0 | Array ops | Numeric |
| 7 | `selenium` | ≥4.15.0 | Headless Chrome automation | Browser |
| 8 | `webdriver-manager` | ≥4.1.2 | Auto-manage ChromeDriver | Browser |
| 9 | `pynput` | ≥1.7.6 | Keyboard event capture | Input |
| 10 | `pyperclip` | ≥1.11.0 | Clipboard access | Input |
| 11 | `psutil` | ≥7.2.2 | Process / system info | System |

### 3.2 Development Dependencies (7)

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥7.4.0 | Test runner |
| `pytest-cov` | ≥7.1.0 | Coverage reporting |
| `bandit` | ≥1.9.4 | Python SAST |
| `pip-audit` | ≥2.6.0 | Dependency CVE scan |
| `pyinstaller` | ≥6.22.3 | EXE build (optional) |
| `ruff` | ≥0.16.8 | Linter |
| `semgrep` | (not pinned) | Pattern SAST |

---

## 4. Dependency Reduction Journey

### 4.1 Original Footprint (20+ deps)

The pre-refactor project pulled in: flask, flask-socketio, python-socketio, eventlet, qrcode[pil], pyzbar, opencv-python, pillow, selenium, webdriver-manager, requests, urllib3, pyautogui, pynput, pyperclip, psutil, geocoder, cryptography, boto3, python-dotenv, numpy.

### 4.2 Removed Dependencies

| Removed | Replacement | Savings |
|---------|-------------|---------|
| `pyzbar` | `opencv-python` (self-contained wheel) | ~2 MB |
| `flask-socketio` + `python-socketio` + `eventlet` | Polling via `/exfil-data` | ~15 MB |
| `pyautogui` | `PIL.ImageGrab` (native) | ~5 MB |
| `geocoder` | Direct `urllib` to ip-api.com | ~3 MB |
| `cryptography` | Not needed (no client-side crypto) | ~25 MB |
| `boto3` | AWS relay uses plain sockets | ~50 MB |
| `python-dotenv` | `os.getenv` (stdlib) | < 1 MB |
| `urllib3` | Transitive via `requests` | n/a |

**Total reduction: ~150 MB of install footprint**

### 4.3 Why We Kept Selenium

Initial analysis suggested replacing Selenium with `requests.get()` (which would have removed ~90 MB). We rejected this because:

1. **Fidelity to Mandiant's technique** — the browser-isolation bypass relies on a real browser rendering the QR PNG as pixels.
2. **Chrome fingerprint** — Selenium gives real `navigator.webdriver` override + camera permission auto-grant.
3. **Camera/mic permission flow** — some RBI products block dynamic media access; only a real browser context can trigger the prompt.

See `README.md` "Why Selenium" section.

---

## 5. Before / After Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Direct runtime deps | 20+ | **11** | **−45%** |
| Dev deps | 5+ | **7** | +2 (SAST tools) |
| Total install size | ~700 MB | ~550 MB | −21% |
| Python files | 22 | **15** | −32% |
| LOC (approx) | 4500 | **3000** | −33% |
| God modules | 2 | 1 | −50% |
| Duplicate files | 1 pair | 0 | eliminated |

---

## 6. Circular Dependency Check

Using a custom AST walker to detect import cycles:

```python
python - <<'PY'
import ast, pathlib
graph = {}
for p in pathlib.Path(".").rglob("*.py"):
    if "venv" in str(p) or "__pycache__" in str(p):
        continue
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                deps.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                deps.add(node.module.split(".")[0])
    graph[p.stem] = deps

def has_cycle(g):
    visited, stack = set(), set()
    def visit(n):
        if n in stack: return True
        if n in visited: return False
        visited.add(n); stack.add(n)
        for m in g.get(n, ()):
            if m in g and visit(m): return True
        stack.discard(n); return False
    return any(visit(n) for n in g)

print("Cycle detected:", has_cycle(graph))
PY
```

**Result:** `Cycle detected: False` ✓ — clean DAG.

---

## 7. Supply Chain Security

### 7.1 Controls

| Control | Implementation |
|---------|----------------|
| Version pinning | `>=` minimum with `pip-audit` validation in CI |
| Vulnerability scanning | `pip-audit -r requirements.txt` in CI |
| Auto-updates | Dependabot with 7-day cooldown |
| Malware alerts | Dependabot malware alerts enabled |
| Secret scanning | GitHub push protection enabled |
| Minimal footprint | Only 11 direct deps |

### 7.2 Cooldown Rationale

Dependabot's `cooldown: default-days: 7` ensures newly-published versions wait 7 days before being proposed. Defends against typosquatting, compromised releases, and malicious maintainer uploads.

Reference: `.github/dependabot.yml`

### 7.3 Transitive Dependency Snapshot

`pip-audit` reported 0 known CVEs across all direct and transitive dependencies as of 2026-09-30. Full report: `reports/pipaudit.json`.

---

## 8. Future Work

### 8.1 Refactor `rat_client.py`

Split the 550-line god module into a `rat_client/` package (structure in §2.3). Target: max fan-out = 6.

### 8.2 Optional Dependency for Selenium

Make Selenium lazy-imported:

```python
def init_browser_if_available():
    try:
        from selenium import webdriver
        return webdriver.Chrome(...)
    except ImportError:
        return None
```

### 8.3 Remove `numpy` Direct Dependency

`numpy` is only used indirectly via `opencv-python`. Removing the direct pin would reduce visible surface.

### 8.4 Consider `segno` over `qrcode[pil]`

`segno` is a pure-Python QR generator with zero dependencies. Would eliminate the `Pillow` chain for the server side. Deferred.

### 8.5 Drop `webdriver-manager`

Modern Selenium 4.6+ has built-in Selenium Manager that auto-downloads drivers. `webdriver-manager` may become redundant.

---

## 9. Comparison With Original Project

| Aspect | Original | Refactored |
|--------|----------|------------|
| Duplicate files | `qr_decoder.py` + `rat_client.py` | Merged |
| Hardcoded IPs | 2 | 0 (env var) |
| God modules | 2 | 1 (documented) |
| External deps | 20+ | 11 |
| Cyclic dependencies | (not measured) | 0 |
| SAST clean | (not measured) | ✅ 0 HIGH, 0 CVEs, 0 Semgrep, 0 Ruff |

---

## 10. References

- `docs/report/04-architecture.md`
- `docs/report/06-threat-model.md`
- `reports/pipaudit.json`
- `requirements.txt`
- `requirements-dev.txt`

---

## 11. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-30 | Initial dependency analysis | R Jeevan |