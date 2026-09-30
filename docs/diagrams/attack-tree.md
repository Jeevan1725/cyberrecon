\# CyberRecon — Attack Tree (Defensive Detection)



\*\*Format:\*\* PlantUML



\*\*Source file:\*\* \[attack-tree.puml](attack-tree.puml)



\## Rendered Diagram



!\[Attack Tree](attack-tree.png)



\## Description



This attack tree maps the \*\*defensive detection perspective\*\* — what signals

would a blue team observe if CyberRecon (or a similar QR-C2 technique) were

deployed maliciously?



The tree is organized into four layers:



1\. \*\*Network-layer signals\*\* — beaconing, non-standard ports, headless Chrome traffic

2\. \*\*Host-layer signals (Windows)\*\* — persistence IOCs, log tampering, masquerading

3\. \*\*Application-layer signals\*\* — Chrome CLI flags, library loads

4\. \*\*Data-layer signals\*\* — DLP signatures, unusual access patterns



Each leaf is annotated with an \*\*indicator\*\* or \*\*IOC\*\* for detection engineers

to build a coverage map against their existing SIEM/EDR rules.



\## PlantUML Source



```plantuml

@startwbs

skinparam monochrome true

title CyberRecon - Attack Tree (Defensive Detection Perspective)



\* Detect CyberRecon Deployment

\*\* Network-Layer Signals

\*\*\* Repeated POST to /exfil/\* every 15s

\*\*\*\* Indicator: beaconing pattern

\*\*\* HTTP (not HTTPS) to unknown IP on 8443

\*\*\*\* Indicator: weak signal (lab-only)

\*\*\* Headless Chrome spawning from non-browser parent

\*\*\*\* Indicator: STRONG signal

\*\* Host-Layer Signals (Windows)

\*\*\* Registry Run key: HKCU\\\\...\\\\Run\\\\WindowsSecurityUpdate

\*\*\*\* IOC: persistence technique

\*\*\* Scheduled task: WindowsUpdateTask

\*\*\*\* IOC: persistence technique

\*\*\* Startup folder: update.exe

\*\*\*\* IOC: persistence technique

\*\*\* wevtutil cl Security / System

\*\*\*\* Indicator: log tampering (Sysmon Event 1)

\*\*\* svchost.exe in %TEMP%\\\\WindowsUpdate\_\*

\*\*\*\* IOC: masquerade technique

\*\* Application-Layer Signals

\*\*\* Chrome with --headless=new + --disable-blink-features

\*\*\*\* IOC: non-default CLI flags

\*\*\* Chrome with --use-fake-ui-for-media-stream

\*\*\*\* IOC: media auto-grant

\*\*\* OpenCV QRCodeDetector load in Python process

\*\*\*\* Indicator: behavioural anomaly

\*\* Data-Layer Signals

\*\*\* Large base64-encoded POSTs

\*\*\*\* Indicator: DLP signature for exfil

\*\*\* Repeated clipboard reads without user action

\*\*\*\* Indicator: unusual

\*\*\* Webcam/screenshot access without user interaction

\*\*\*\* Indicator: privacy violation



@endwbs

```



\## References



\- `docs/report/06-threat-model.md` — full STRIDE analysis

\- `docs/report/07-security-features.md` — mitigations per finding

\- MITRE ATT\&CK — https://attack.mitre.org/

