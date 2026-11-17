"""Normal work creates no diagnostic file; actual errors retain their traceback."""

import logging
from pathlib import Path
import subprocess
import sys

import pytest

from src import logger_setup
from src.profiles import PRESETS
from src.size_estimator import SizeEstimateWorker
from src.worker import FileConversionTask, WorkerSignals, get_media_info, process_options


@pytest.fixture
def error_log(tmp_path, monkeypatch):
    root = logging.getLogger()
    previous_level = root.level
    path = tmp_path / 'error.log'
    monkeypatch.setattr(logger_setup, 'error_log_path', lambda: path)
    logger_setup.setup_logging()
    yield path
    for handler in list(root.handlers):
        if handler.name == 'vbc.errors':
            root.removeHandler(handler)
            handler.close()
    root.setLevel(previous_level)


def cpu_settings(**changes):
    values = dict(PRESETS['1080p'], codec='AVC (H.264) - CPU', rate_control='CRF',
                  adaptive_quality=False, quality_value='25', suffix='_logging', keep_smaller=False)
    values.update(changes)
    return values


@pytest.mark.parametrize('packaged', [False, True])
def test_error_log_location_uses_source_or_executable_directory(tmp_path, monkeypatch, packaged):
    monkeypatch.setattr(sys, 'frozen', packaged, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'VideoBatchConverter.exe'))
    expected = tmp_path if packaged else Path(logger_setup.__file__).resolve().parent.parent
    assert logger_setup.error_log_path() == expected / 'error.log'


def test_startup_info_and_warnings_do_not_create_log(error_log):
    for level in (logging.DEBUG, logging.INFO, logging.WARNING):
        logging.log(level, 'Normal startup / progress / recoverable warning')
    assert not error_log.exists()
    assert not error_log.with_suffix('.log.1').exists()


def test_first_error_creates_file_with_traceback_and_only_errors(error_log):
    logging.info('Normal startup')
    try:
        raise ValueError('인코딩 진단')
    except ValueError:
        logging.exception('Actual failure')
    text = error_log.read_text(encoding='utf-8')
    assert '[ERROR]' in text and 'Actual failure' in text and 'Traceback' in text and 'ValueError: 인코딩 진단' in text
    logging.info('Normal finish')
    logging.warning('Recoverable warning')
    assert error_log.read_text(encoding='utf-8') == text


def test_repeated_setup_keeps_history_without_duplicate_records(error_log):
    error_log.write_text('Earlier error\n', encoding='utf-8')
    logger_setup.setup_logging()
    assert error_log.read_text(encoding='utf-8') == 'Earlier error\n'
    logging.error('One error')
    assert error_log.read_text(encoding='utf-8').count('One error') == 1
    assert error_log.read_text(encoding='utf-8').startswith('Earlier error\n')


@pytest.mark.parametrize('outcome', ['done', 'skipped', 'stopped', 'kept'])
def test_success_skip_cancel_and_larger_result_are_not_errors(error_log, sample_video, outcome):
    settings = cpu_settings(quality_value='0' if outcome == 'kept' else '25', keep_smaller=outcome == 'kept',
                            suffix='_logging_' + outcome)
    signals = WorkerSignals()
    finished = []
    signals.finished.connect(lambda task, result: finished.append(result))
    task = FileConversionTask(sample_video, settings, signals)
    if outcome == 'skipped':
        task.output_file.write_bytes(b'Existing output')
    elif outcome == 'stopped':
        task.stop()
    task.run()
    assert finished == [outcome]
    assert not error_log.exists()


def test_encoding_failure_writes_error_and_traceback(error_log, sample_video):
    settings = cpu_settings(codec='invalid', suffix='_logging_failed')
    task = FileConversionTask(sample_video, settings, WorkerSignals())
    task.run()
    text = error_log.read_text(encoding='utf-8')
    assert '변환 실패' in text and sample_video.name in text and 'KeyError' in text


def test_sample_failure_is_logged_but_cancellation_is_not(error_log, sample_video, monkeypatch):
    worker = SizeEstimateWorker([(str(sample_video), get_media_info(sample_video))], cpu_settings(), temp_root=error_log.parent)
    worker.cancel()
    worker.run()
    assert not error_log.exists()
    raced = SizeEstimateWorker([(str(sample_video), get_media_info(sample_video))], cpu_settings(), temp_root=error_log.parent)
    def cancel_then_fail(*args, **kwargs):
        raced.cancel()
        raise RuntimeError('Process exited during cancellation')
    monkeypatch.setattr(raced, 'capture', cancel_then_fail)
    raced.run()
    assert not error_log.exists()
    worker = SizeEstimateWorker([(str(sample_video), get_media_info(sample_video))], cpu_settings(), temp_root=error_log.parent)
    monkeypatch.setattr(worker, 'capture', lambda *args, **kwargs: (1, 'Sample encoder failure'))
    worker.run()
    text = error_log.read_text(encoding='utf-8')
    assert '샘플 예측 실패' in text and 'Sample encoder failure' in text and 'Traceback' in text


def test_installer_failure_writes_error(error_log, tmp_path, monkeypatch):
    from src import ffmpeg_downloader
    def fail(*args, **kwargs):
        raise RuntimeError('Download failed')
    monkeypatch.setattr(ffmpeg_downloader.requests, 'get', fail)
    ffmpeg_downloader.DownloadWorker(tmp_path / 'ffmpeg').run()
    assert 'FFmpeg 설치 실패' in error_log.read_text(encoding='utf-8')


def test_qt_warnings_do_not_create_file_but_critical_errors_do(error_log):
    from PyQt6.QtCore import qInstallMessageHandler, qWarning, qCritical
    previous = qInstallMessageHandler(logger_setup.handle_qt_message)
    try:
        qWarning('Non-fatal Qt warning')
        assert not error_log.exists()
        qCritical('Actual Qt error')
        assert 'Actual Qt error' in error_log.read_text(encoding='utf-8')
    finally:
        qInstallMessageHandler(previous)


@pytest.mark.parametrize('kind', ['normal', 'main', 'thread', 'unraisable'])
def test_uncaught_exceptions_create_crash_log_in_isolated_process(tmp_path, kind):
    code = '''
from pathlib import Path
import sys
import threading
from src import logger_setup
logger_setup.error_log_path = lambda: Path(sys.argv[1]) / 'error.log'
logger_setup.setup_logging()
kind = sys.argv[2]
if kind == 'normal':
    from unittest.mock import patch
    from PyQt6.QtWidgets import QApplication
    from src import settings
    from src.theme import configure_theme
    from src.ui_mainwindow import MainWindow
    app = QApplication([])
    configure_theme(app)
    with patch.object(settings, 'get_settings_path', lambda: str(Path(sys.argv[1]) / 'settings.ini')), \\
         patch.object(MainWindow, 'check_for_updates', lambda self: None), \\
         patch.object(MainWindow, 'confirm_exit', lambda self, busy: True):
        window = MainWindow()
        window.show()
        app.processEvents()
        window.close()
        app.processEvents()
elif kind == 'main':
    from main import handle_exception
    sys.excepthook = handle_exception
    raise RuntimeError('Main crash')
elif kind == 'thread':
    threading.excepthook = logger_setup.handle_thread_exception
    def fail():
        raise RuntimeError('Thread crash')
    worker = threading.Thread(target=fail, name='Crash test')
    worker.start()
    worker.join()
else:
    sys.unraisablehook = logger_setup.handle_unraisable_exception
    class Broken:
        def __del__(self):
            raise RuntimeError('Destructor crash')
    item = Broken()
    del item
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), kind],
                            cwd=Path(__file__).resolve().parent.parent, capture_output=True,
                            text=True, timeout=20, **process_options())
    assert result.returncode == (1 if kind == 'main' else 0), result.stderr
    if kind == 'normal':
        assert not (tmp_path / 'error.log').exists()
        return
    text = (tmp_path / 'error.log').read_text(encoding='utf-8')
    assert 'RuntimeError' in text and 'Traceback' in text
