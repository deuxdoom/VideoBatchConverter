"""One short, non-blocking completion notification per finished batch."""

import logging
import sys

from .paths import ASSETS


def play_completion_sound():
    path = ASSETS / 'audio/complete.wav'
    if not path.is_file():
        logging.warning('Completion sound missing: %s', path)
        return
    try:
        if sys.platform == 'win32':
            import winsound
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except (OSError, RuntimeError):
        logging.exception('Could not play completion sound')
