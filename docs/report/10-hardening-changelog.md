# CyberRecon v3.5 Hardening Changelog

## Overview

Between v3.0 and v3.5, five security layers were added on top of the
existing operator-token auth and sandbox model.

## New Security Controls

| # | Control | Threat mitigated |
|---|---|---|
| 1 | AES-256-GCM QR payload encryption | Passive QR interception reveals ciphertext only |
| 2 | Victim shared-key auth (`X-Victim-Key`) | Prevents unauthorized victim registration/exfil spoofing |
| 3 | Dashboard login (session cookie) | Prevents unauthenticated dashboard/API access |
| 4 | Server-side wipe endpoint | Purges victim record on self-destruct |
| 5 | Anti-forensic self-destruct (userland) | Removes registry/temp/binary artifacts |

## Residual Forensic Artifacts (Limitations)

- NTFS `$MFT` timestamps
- Windows Prefetch (`C:\Windows\Prefetch\CYBERRECON*.pf`)
- Sysmon / EDR telemetry (kernel-side)
- Windows Security event log (4688)
- Volatile memory after process exit

Documented in `docs/report/06-threat-model.md`.
