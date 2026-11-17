import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import subprocess

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from src.worker import get_ffmpeg_path, process_options


@pytest.fixture(scope='session')
def app():
    instance = QApplication.instance() or QApplication([])
    from src.theme import configure_theme
    configure_theme(instance)
    yield instance


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    from src import settings, ui_mainwindow
    monkeypatch.setattr(settings, 'get_settings_path', lambda: str(tmp_path / 'settings.ini'))
    monkeypatch.setattr(ui_mainwindow.MainWindow, 'check_and_prepare_ffmpeg', lambda self: True)
    monkeypatch.setattr(ui_mainwindow.MainWindow, 'check_for_updates', lambda self: None)
    monkeypatch.setattr(ui_mainwindow.MainWindow, 'confirm_exit', lambda self, busy: True)
    monkeypatch.setattr(ui_mainwindow, 'play_completion_sound', lambda: None)
    monkeypatch.setattr(ui_mainwindow.MainWindow, 'choose_estimate_action', lambda self, problems: 'continue')
    monkeypatch.setattr(ui_mainwindow.MainWindow, 'show_batch_warning', lambda self: None)
    monkeypatch.setattr('PyQt6.QtWidgets.QMessageBox.warning',
                        lambda parent, title, message: pytest.fail(f'Unexpected warning: {title}: {message}'))
    instance = ui_mainwindow.MainWindow()
    # Existing encode/stop tests exercise the full conversion directly; the
    # preflight decision/cancellation workflow has its own integration tests.
    instance.estimate_size_check.setChecked(False)
    monkeypatch.setattr('tempfile.tempdir', str(tmp_path))
    instance.show()
    app.processEvents()
    yield instance
    instance.time_preview.pause()
    if instance.time_preview.worker:
        instance.time_preview.worker.wait()
        app.processEvents()
    if instance.converting or instance.scanning or instance.preflighting:
        instance.stop_conversion()
        instance.thread_pool.waitForDone()
        if instance.scan_worker:
            instance.scan_worker.wait()
        if instance.estimate_worker:
            instance.estimate_worker.wait()
        app.processEvents()
    instance.close()
    app.processEvents()


@pytest.fixture(scope='session')
def sample_video(tmp_path_factory):
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        pytest.skip('Local FFmpeg binaries required for integration tests')
    folder = tmp_path_factory.mktemp('media')
    source = folder / '테스트 영상.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=96x64:rate=12', '-f', 'lavfi', '-i', 'sine=frequency=440',
                    '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)],
                   check=True, timeout=20, **process_options())
    return source
