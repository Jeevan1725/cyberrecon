\# 09 — Dependency Analysis



\*\*Project:\*\* CyberRecon — QR-Code-Based C2 Framework

\*\*Document Version:\*\* 1.0

\*\*Date:\*\* 2026-09-30

\*\*Authors:\*\* Vekeshhari Rajasekar, R Jeevan



\---



\## 1. Purpose



This document analyzes CyberRecon's:



1\. \*\*Internal module dependencies\*\* — which Python files depend on each other (fan-in / fan-out)

2\. \*\*External dependencies\*\* — third-party libraries and why each is needed

3\. \*\*Dependency reduction\*\* — how the footprint went from 20+ to 11 direct dependencies

4\. \*\*Targeted improvements\*\* — what we would further consolidate in future work



The goal is to demonstrate understanding of coupling, cohesion, and

supply-chain risk reduction.



\---



\## 2. Internal Module Dependency Graph



\### 2.1 Dependency Hierarchy



```

&#x20;                    ┌──────────────────┐

&#x20;                    │     main.py      │  (entry — depends on all)

&#x20;                    └────────┬─────────┘

&#x20;                             │

&#x20;       ┌─────────────────────┼─────────────────────┐

&#x20;       ▼                     ▼                     ▼

&#x20; ┌───────────┐         ┌───────────┐         ┌───────────┐

&#x20; │ c2\_server │         │rat\_client │         │operator\_  │

&#x20; │   .py     │◀────────│   .py     │────────▶│  cli.py   │

&#x20; └─────┬─────┘         └─────┬─────┘         └───────────┘

&#x20;       │                     │

&#x20;       │                     ▼

&#x20;       │              ┌──────────────────┐

&#x20;       │              │    modules/      │

&#x20;       │              │  (6 feature      │

&#x20;       │              │   modules)       │

&#x20;       │              └────────┬─────────┘

&#x20;       │                       │

&#x20;       ▼                       ▼

&#x20; ┌──────────────┐      ┌──────────────┐

&#x20; │  config.py   │      │ ai\_agent.py  │

&#x20; │  (leaf)      │      │  (leaf)      │

&#x20; └──────────────┘      └──────────────┘

```



\### 2.2 Fan-In / Fan-Out Table



| Module | Fan-In (depended by) | Fan-Out (depends on) | Type |

|--------|----------------------|----------------------|------|

| `config.py` | 10 | 0 | \*\*Independent / Leaf\*\* |

| `ai\_agent.py` | 1 (main) | 0 | \*\*Independent\*\* |

| `modules/\*` (6 files) | 2 each | 1 (config) | Semi-independent |

| `c2\_server.py` | 2 (main, rat\_client) | 2 (config, qrcode) | \*\*Hub\*\* |

| `rat\_client.py` | 1 (main) | 12 (6 modules + selenium + cv2 + requests + PIL + numpy + json) | \*\*God module\*\* ⚠️ |

| `operator\_cli.py` | 1 (main) | 1 (requests) | Leaf |

| `aws\_relay.py` | 1 (main) | 1 (requests) | Leaf |

| `main.py` | 0 | 6 | Entry point |



\*\*Observations:\*\*



\- \*\*1 truly independent module:\*\* `config.py` (fan-in = 10, fan-out = 0)

\- \*\*1 orphan module:\*\* `ai\_agent.py` (imported only by `main.py`)

\- \*\*2 hub modules:\*\* `c2\_server.py`, `rat\_client.py`

\- \*\*1 god module:\*\* `rat\_client.py` (fan-out = 12) ⚠️

\- \*\*No circular dependencies\*\* ✓



\### 2.3 God Module Analysis — `rat\_client.py`



`rat\_client.py` has \*\*fan-out = 12\*\* and \~550 lines of code, making it

a classic \*\*god module\*\* anti-pattern.



\*\*Current structure:\*\*



```python

class QRDecoder:

&#x20;   def \_\_init\_\_(self, c2\_url, victim\_id):

&#x20;       # 6 attribute assignments

&#x20;   def register\_with\_c2(self): ...

&#x20;   def init\_headless\_browser(self): ...

&#x20;   def capture\_qr\_screenshot(self): ...

&#x20;   def decode\_qr\_image(self): ...

&#x20;   def listen\_for\_commands(self): ...

&#x20;   def execute\_command(self): ...

&#x20;   def \_handle\_whoami(self): ...

&#x20;   def \_handle\_screenshot(self): ...

&#x20;   def \_handle\_webcam(self): ...

&#x20;   def \_handle\_keylogger(self): ...

&#x20;   def \_handle\_clipboard(self): ...

&#x20;   def \_handle\_download(self): ...

&#x20;   def \_handle\_gps(self): ...

&#x20;   def \_handle\_process\_list(self): ...

&#x20;   def \_handle\_system\_info(self): ...

&#x20;   def \_handle\_list\_files(self): ...

&#x20;   def \_handle\_shell(self): ...

&#x20;   def \_handle\_persist(self): ...

&#x20;   def \_handle\_self\_destruct(self): ...

&#x20;   def \_handle\_unknown(self): ...

&#x20;   def \_exfil(self): ...

&#x20;   def cleanup(self): ...

```



\*\*Recommended refactor for future work:\*\*



```python

\# Proposed structure

rat\_client/

├── \_\_init\_\_.py

├── qr\_decoder.py         # Selenium + OpenCV logic only

├── dispatcher.py         # command routing

├── exfil\_client.py       # HTTP POST

├── browser\_channel.py    # Selenium wrapper with fallback

└── handlers/

&#x20;   ├── \_\_init\_\_.py

&#x20;   ├── system.py         # whoami, system\_info, process\_list

&#x20;   ├── capture.py        # screenshot, webcam

&#x20;   ├── spy.py            # keylogger, clipboard

&#x20;   ├── location.py       # gps

&#x20;   ├── files.py          # download, list\_files

&#x20;   └── control.py        # persist, self\_destruct, shell

```



\*\*Benefits:\*\* Smaller modules, single responsibility, easier to test.



\*\*Why we didn't refactor now:\*\* Time-boxed for the final demo; documented as future work.



\---



\## 3. External Dependency Analysis



\### 3.1 Current Runtime Dependencies (11)



| # | Package | Version | Purpose | Category |

|---|---------|---------|---------|----------|

| 1 | `flask` | ≥2.3.0 | C2 HTTP server + dashboard | Server |

| 2 | `requests` | ≥2.34.2 | HTTP client (exfil, C2 comms) | HTTP |

| 3 | `pillow` | ≥12.3.0 | Image encoding/decoding | Image |

| 4 | `qrcode\[pil]` | ≥8.2 | QR PNG generation | QR |

| 5 | `opencv-python` | ≥4.8.0 | QR decode + webcam capture | QR / Video |

| 6 | `numpy` | ≥1.24.0 | Array ops (OpenCV dependency) | Numeric |

| 7 | `selenium` | ≥4.15.0 | Headless Chrome automation | Browser |

| 8 | `webdriver-manager` | ≥4.1.2 | Auto-manage ChromeDriver | Browser |

| 9 | `pynput` | ≥1.7.6 | Keyboard event capture | Input |

| 10 | `pyperclip` | ≥1.11.0 | Clipboard access | Input |

| 11 | `psutil` | ≥7.2.2 | Process / system info | System |



\### 3.2 Development Dependencies (7)



| Package | Version | Purpose |

|---------|---------|---------|

| `pytest` | ≥7.4.0 | Test runner |

| `pytest-cov` | ≥7.1.0 | Coverage reporting |

| `bandit` | ≥1.9.4 | Python SAST |

| `pip-audit` | ≥2.6.0 | Dependency CVE scan |

| `pyinstaller` | ≥6.22.3 | EXE build (optional) |

| `ruff` | ≥0.16.8 | Linter |

| `semgrep` | (not pinned) | Pattern SAST |



\---



\## 4. Dependency Reduction Journey



\### 4.1 Original Footprint (20+ deps)



The pre-refactor project pulled in:



```

flask

flask-socketio

python-socketio

eventlet

qrcode\[pil]

pyzbar

opencv-python

pillow

selenium

webdriver-manager

requests

urllib3

pyautogui

pynput

pyperclip

psutil

geocoder

cryptography

boto3

python-dotenv

numpy

```



\### 4.2 Removed Dependencies



| Removed | Replacement | Savings |

|---------|-------------|---------|

| `selenium` (for QR fetch only) | Kept! Required for browser-isolation bypass | — |

| `pyzbar` | `opencv-python` (self-contained wheel on Windows) | \~2 MB |

| `flask-socketio` + `python-socketio` + `eventlet` | Polling via `/exfil-data` endpoint | \~15 MB |

| `pyautogui` | `PIL.ImageGrab` (native) | \~5 MB |

| `geocoder` | Direct `urllib` to ip-api.com | \~3 MB |

| `cryptography` | Not needed (no client-side crypto) | \~25 MB |

| `boto3` | AWS relay uses plain sockets | \~50 MB |

| `python-dotenv` | `os.getenv` (stdlib) | < 1 MB |

| `urllib3` | Transitive via `requests` | n/a |



\*\*Total reduction: \~150 MB of install footprint\*\*



\### 4.3 Why We Kept Selenium



Initial analysis suggested replacing Selenium with `requests.get()`

(which would have removed \~90 MB). We \*\*rejected this\*\* because:



1\. \*\*Fidelity to Mandiant's technique\*\* — the browser-isolation bypass

&#x20;  relies on a \*real browser rendering the QR PNG as pixels\*. A plain

&#x20;  HTTP fetch does NOT reproduce the technique.

2\. \*\*Chrome fingerprint\*\* — Selenium gives a real `navigator.webdriver`

&#x20;  override + camera permission auto-grant flags that `requests` can't.

3\. \*\*Camera / mic permission flow\*\* — some RBI products block dynamic

&#x20;  media access; only a real browser context can trigger the prompt.



See `README.md` "Why Selenium" section for the full rationale.



\---



\## 5. Before / After Metrics



| Metric | Before | After | Change |

|--------|--------|-------|--------|

| Direct runtime deps | 20+ | \*\*11\*\* | \*\*−45%\*\* |

| Dev deps | 5+ | \*\*7\*\* | +2 (added SAST tools) |

| Total install size | \~700 MB | \~550 MB | −21% |

| Vendored / bundled | none | none | — |

| Python files | 22 | \*\*15\*\* | −32% |

| LOC (approx) | 4500 | \*\*3000\*\* | −33% |

| God modules | 2 (`rat\_client`, `qr\_decoder` duplicated) | \*\*1\*\* (`rat\_client`) | −50% |

| Duplicate files | 1 pair (`qr\_decoder` ≈ `rat\_client`) | 0 | eliminated |



\---



\## 6. Circular Dependency Check



Using a custom AST walker to detect import cycles:



```bash

python - <<'PY'

import ast, pathlib

graph = {}

for p in pathlib.Path(".").rglob("\*.py"):

&#x20;   if "venv" in str(p) or "\_\_pycache\_\_" in str(p):

&#x20;       continue

&#x20;   try:

&#x20;       tree = ast.parse(p.read\_text(encoding="utf-8"))

&#x20;   except Exception:

&#x20;       continue

&#x20;   deps = set()

&#x20;   for node in ast.walk(tree):

&#x20;       if isinstance(node, ast.Import):

&#x20;           for n in node.names:

&#x20;               deps.add(n.name.split(".")\[0])

&#x20;       elif isinstance(node, ast.ImportFrom):

&#x20;           if node.module:

&#x20;               deps.add(node.module.split(".")\[0])

&#x20;   graph\[p.stem] = deps



def has\_cycle(g):

&#x20;   visited, stack = set(), set()

&#x20;   def visit(n):

&#x20;       if n in stack: return True

&#x20;       if n in visited: return False

&#x20;       visited.add(n); stack.add(n)

&#x20;       for m in g.get(n, ()):

&#x20;           if m in g and visit(m): return True

&#x20;       stack.discard(n); return False

&#x20;   return any(visit(n) for n in g)



print("Cycle detected:", has\_cycle(graph))

PY

```



\*\*Result:\*\* `Cycle detected: False` ✓



No circular dependencies — a clean DAG.



\---



\## 7. Supply Chain Security



\### 7.1 Controls



| Control | Implementation |

|---------|----------------|

| Version pinning | `>=` minimum with `pip-audit` validation in CI |

| Vulnerability scanning | `pip-audit -r requirements.txt` in CI |

| Auto-updates | Dependabot with 7-day cooldown |

| Malware alerts | Dependabot malware alerts enabled |

| Secret scanning | GitHub push protection enabled |

| Minimal footprint | Only 11 direct deps |



\### 7.2 Cooldown Rationale



Dependabot's `cooldown: default-days: 7` block ensures that

newly-published package versions wait 7 days before being proposed as

updates. This defends against:



\- \*\*Typosquatting\*\* — malicious look-alike packages

\- \*\*Compromised releases\*\* — the `event-stream` attack pattern

\- \*\*Malicious maintainer uploads\*\* — supply chain poisoning



Reference: `.github/dependabot.yml`



\### 7.3 Transitive Dependency Snapshot



`pip-audit` reported \*\*0 known CVEs\*\* across all direct and transitive

dependencies as of 2026-09-30. Full report: `reports/pipaudit.json`.



\---



\## 8. Future Work



\### 8.1 Refactor `rat\_client.py`



Split the 550-line god module into a `rat\_client/` package (structure

proposed in §2.3). Target: max fan-out = 6.



\### 8.2 Optional Dependency for Selenium



Make Selenium lazy-imported so the client can start without it if

the operator only needs the HTTP fallback:



```python

def init\_browser\_if\_available():

&#x20;   try:

&#x20;       from selenium import webdriver

&#x20;       return webdriver.Chrome(...)

&#x20;   except ImportError:

&#x20;       return None

```



\### 8.3 Remove `numpy` Direct Dependency



`numpy` is only used indirectly via `opencv-python`. Removing the

direct pin would reduce visible surface. Preserved for explicitness.



\### 8.4 Consider `segno` over `qrcode\[pil]`



`segno` is a pure-Python QR generator with zero dependencies. Would

eliminate the `Pillow` chain for the server side. Deferred — the

current QR library is stable and well-tested.



\### 8.5 Drop `webdriver-manager`



Modern Selenium 4.6+ has built-in Selenium Manager that auto-downloads

drivers. `webdriver-manager` may become redundant in future releases.



\---



\## 9. Comparison With Original Project



| Aspect | Original | Refactored |

|--------|----------|------------|

| Duplicate files | `qr\_decoder.py` + `rat\_client.py` (95% identical) | Merged — 1 file |

| Hardcoded IPs | 2 (`18.61.36.73`, `11.12.25.98`) | 0 (env var) |

| God modules | 2 | 1 (documented) |

| External deps | 20+ | 11 |

| Cyclic dependencies | (not measured) | 0 |

| SAST clean | (not measured) | ✅ 0 HIGH, 0 CVEs, 0 Semgrep, 0 Ruff |



\---



\## 10. References



\- `docs/report/04-architecture.md` — module graph context

\- `docs/report/06-threat-model.md` — supply chain threats

\- `reports/pipaudit.json` — dependency CVE evidence

\- `requirements.txt` — current direct deps

\- `requirements-dev.txt` — dev deps



\---



\## 11. Change Log



| Date | Change | Author |

|------|--------|--------|

| 2026-09-30 | Initial dependency analysis | R Jeevan |

