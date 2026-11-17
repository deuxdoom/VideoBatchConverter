"""Create truthful UI captures with generated example media, never user videos."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_SCALE_FACTOR', '1')
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from src import settings
from src.profiles import PRESETS, PRESET_KEYS
from src.brand_dialog import ConfirmExitDialog
from src.theme import configure_theme
from src.i18n import language_manager
from src.ui_mainwindow import MainWindow
from src.worker import get_ffmpeg_path, process_options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'assets/screenshots')
    parser.add_argument('--language', choices=('ko', 'en'), default='ko')
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(args.work_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = args.work_dir / '예제_주말여행.mp4'
    if not source.exists():
        subprocess.run([get_ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=640x360:rate=24', '-f', 'lavfi', '-i', 'sine=frequency=440',
                        '-t', '2', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16', '-c:a', 'aac', str(source)],
                       check=True, **process_options())
    examples = [source]
    for name in ('예제_가족영상.mp4', '예제_작업기록.mp4', *(f'예제_보관영상_{index:02d}.mp4' for index in range(1, 15))):
        target = args.work_dir / name
        if not target.exists():
            target.write_bytes(source.read_bytes())
        examples.append(target)
    app = QApplication([])
    configure_theme(app)
    with patch.object(settings, 'get_settings_path', lambda: str(args.work_dir / 'settings.ini')), \
         patch.object(MainWindow, 'check_for_updates', lambda self: None), \
         patch.object(MainWindow, 'confirm_exit', lambda self, busy: True), \
         patch.object(MainWindow, 'choose_estimate_action', lambda self, problems: 'continue'), \
         patch('src.ui_mainwindow.play_completion_sound', lambda: None):
        window = MainWindow()
        language_manager().set_language(args.language)
        window.resize(1240, 850)
        window.apply_preset(next(iter(PRESETS)))
        window.show()
        app.processEvents()
        def capture(name, target=None):
            suffix = '-en' if args.language == 'en' else ''
            if app.focusWidget():
                app.focusWidget().clearFocus()
            (target or window).grab().save(str(args.output_dir / (name + suffix + '.png')))
        capture('empty')
        confirmation = ConfirmExitDialog(False, window)
        confirmation.show()
        app.processEvents()
        capture('exit-confirmation', confirmation)
        confirmation.reject()
        window.add_paths_to_queue([str(path) for path in examples])
        deadline = time.monotonic() + 30
        while window.scanning and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if window.scanning:
            raise RuntimeError('Screenshot scan timed out')
        deadline = time.monotonic() + 120
        while (window.time_preview.timer.isActive() or window.time_preview.worker is not None) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if window.time_preview.timer.isActive() or window.time_preview.worker is not None:
            raise RuntimeError('Screenshot time preview timed out')
        window.file_list_widget.setCurrentRow(0)
        app.processEvents()
        capture('workspace')
        if args.language == 'ko':
            window.grab().save(str(ROOT / 'screenshot.png'))
        window.resize(1000, 680)
        app.processEvents()
        capture('compact')
        window.resize(1240, 850)
        window.show_settings_dialog(category='advanced')
        app.processEvents()
        capture('advanced', window.settings_dialog)
        window.show_settings_dialog()
        for category in window.settings_dialog.categories:
            window.settings_dialog.select_category(category)
            app.processEvents()
            capture('settings-' + category, window.settings_dialog)
        window.show_settings_dialog(category='help', help_key='quality_value')
        app.processEvents()
        capture('settings-help-quality', window.settings_dialog)
        window.settings_dialog.accept()
        window.restore_options(dict(PRESETS['아카이빙'], codec='H.265 (HEVC) - CPU', quality_value='8000', suffix='_preview'))
        saved = {key: window.get_current_settings()[key] for key in PRESET_KEYS}
        window.user_presets['내 보관 설정'] = saved
        window.settings_manager.save_user_presets(window.user_presets)
        window.rebuild_preset_combo('user:내 보관 설정')
        window.on_setting_changed()
        for source_path in examples:
            preview_file = source_path.with_name(source_path.stem + '_preview.' + saved['output_format'])
            if preview_file.exists() and preview_file.parent.resolve() == args.work_dir.resolve():
                preview_file.unlink()
        window.start_conversion()
        deadline = time.monotonic() + 90
        progress_captured = False
        estimate_captured = False
        while (window.preflighting or window.converting) and time.monotonic() < deadline:
            app.processEvents()
            if window.preflighting and not estimate_captured:
                capture('estimating')
                estimate_captured = True
            if not progress_captured and 0 < window.completed_files_count < window.total_files_count:
                capture('encoding')
                progress_captured = True
            time.sleep(.01)
        if window.converting or window.preflighting:
            window.stop_conversion()
            raise RuntimeError('Screenshot conversion timed out')
        settle = time.monotonic() + .35
        while time.monotonic() < settle:
            app.processEvents()
            time.sleep(.01)
        capture('completed')
        window.close()
    print('Saved empty, workspace, compact, advanced, completed and screenshot.png')


if __name__ == '__main__':
    main()
