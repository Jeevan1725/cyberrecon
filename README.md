> ⚠️ \*\*EDUCATIONAL SECURITY RESEARCH ONLY\*\*

>

> This project reproduces a technique published by Mandiant (2024) for

> academic study. It is intended \*\*solely for isolated lab environments\*\*

> with explicit authorization. Unauthorized use is illegal. See

> \[ETHICS.md](ETHICS.md) for full terms and published detection

> signatures.



\# CyberRecon: QR Code-Based C2 Framework



Reproduction \& defensive study of Mandiant's 2024 QR-C2 browser-isolation bypass.



\## Team



\- \*\*Vekeshhari Rajasekar\*\* (CH.SC.U4CYS23051)

\- \*\*R Jeevan\*\* (CH.SC.U4CYS23036)

\- \*\*Guide:\*\* Dr. S. Udhayakumar

\- \*\*Institution:\*\* Amrita School of Computing, Amrita Vishwa Vidyapeetham, Chennai



\## Overview



CyberRecon is a self-contained QR-Code-based Command \& Control (C2)

framework that demonstrates how visually rendered QR codes can pass

through browser isolation filters as pixel data.



\## Architecture

Operator CLI ──► C2 Server (Flask) ──► QR PNG ──► Victim Client

▲ │

└───── HTTP POST /exfil ◄──────────────┘





\## Features



\- QR-based C2 channel (base64-JSON payload, Level-H error correction)

\- 12 RAT feature commands (screenshot, webcam, keylogger, clipboard, GPS,

&#x20; process list, system info, file ops, persistence, self-destruct)

\- Live Flask dashboard (victims, screenshots, keystrokes, GPS)

\- Multi-layer fallback: TCP → HTTP → QR

\- Optional AWS relay (domain fronting)

\- AI agent (natural-language command parsing)



\## Installation



```bash

python -m venv venv

source venv/bin/activate     # Windows: .\\venv\\Scripts\\activate

pip install -r requirements.txt

