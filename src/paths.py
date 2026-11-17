"""Assets live in assets/ in source and a single bin/ directory when packaged."""

from pathlib import Path
import sys

ASSETS = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent / 'assets'


def ffmpeg_directory():
    return ASSETS / 'ffmpeg'
