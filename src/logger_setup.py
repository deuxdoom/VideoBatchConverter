"""Create the rotating diagnostic file only when an actual error is recorded."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def error_log_path():
    folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    return folder / 'error.log'


def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s')
    file_handler = RotatingFileHandler(error_log_path(), maxBytes=5 * 1024 * 1024, backupCount=1,
                                       encoding='utf-8', delay=True)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.ERROR)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    for previous in list(root_logger.handlers):
        if previous.name == 'vbc.errors':
            root_logger.removeHandler(previous)
            previous.close()
    file_handler.set_name('vbc.errors')
    root_logger.addHandler(file_handler)
    return file_handler


def handle_thread_exception(args):
    if issubclass(args.exc_type, SystemExit):
        return
    logging.critical('작업 스레드의 처리되지 않은 예외: %s', getattr(args.thread, 'name', 'unknown'),
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def handle_unraisable_exception(args):
    logging.error('전달할 수 없는 예외: %s · %r', args.err_msg or 'Unraisable exception', args.object,
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def handle_qt_message(message_type, context, message):
    from PyQt6.QtCore import QtMsgType
    if message_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        logging.log(logging.CRITICAL if message_type == QtMsgType.QtFatalMsg else logging.ERROR,
                    'Qt 오류: %s (%s:%s)', message, context.file or '', context.line)
