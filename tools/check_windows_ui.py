"""Native Windows QA for dark-system palettes, popups and no-hinting fonts."""

import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--scale', choices=('1', '1.25', '1.5'), default='1.5')
    args = parser.parse_args()
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ.pop('QT_SCREEN_SCALE_FACTORS', None)
    # QT_SCALE_FACTOR multiplies native Windows scaling. Discover the native
    # factor first so the requested 100/125/150% is the actual tested DPR.
    native_scale = float(subprocess.check_output([sys.executable, '-c',
        'from PyQt6.QtWidgets import QApplication; a=QApplication([]); print(a.primaryScreen().devicePixelRatio())'],
        text=True).strip())
    os.environ['QT_SCALE_FACTOR'] = str(float(args.scale) / native_scale)
    from PyQt6.QtCore import QItemSelectionModel, QPoint, Qt
    from PyQt6.QtGui import QFont, QFontInfo, QPalette
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QAbstractItemView, QFileDialog, QScrollArea, QTreeView
    from src import settings
    from src.about_dialog import AboutDialog
    from src.brand_dialog import ConfirmExitDialog
    from src.estimate_dialog import EstimateDialog
    from src.fonts import PRIMARY_FONT
    from src.i18n import language_manager
    from src.source_picker import SourcePickerDialog
    from src.theme import configure_theme
    from src.ui_mainwindow import MainWindow

    args.artifacts.mkdir(parents=True, exist_ok=True)
    folder = args.artifacts / 'Example folder'
    folder.mkdir(exist_ok=True)
    video = args.artifacts / 'Example video.mp4'
    video.write_bytes(b'Chooser fixture; not an encoded video.')
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([])
    assert abs(app.primaryScreen().devicePixelRatio() - float(args.scale)) < .01
    system_scheme = app.styleHints().colorScheme().name
    configure_theme(app)
    report = {'platform': app.platformName(), 'scale': args.scale, 'system_scheme': system_scheme,
              'app_scheme': app.styleHints().colorScheme().name, 'popups': [], 'layouts': [], 'pickers': [], 'settings': []}

    def smooth(widget):
        font = widget.font()
        assert font.hintingPreference() == QFont.HintingPreference.PreferNoHinting, (type(widget).__name__, font.hintingPreference())
        assert QFontInfo(font).family() == PRIMARY_FONT

    def capture(widget, name):
        widget.grab().save(str(args.artifacts / (name + '.png')))

    with patch.object(settings, 'get_settings_path', lambda: str(args.artifacts / 'settings.ini')), \
         patch.object(MainWindow, 'check_for_updates', lambda self: None), \
         patch.object(MainWindow, 'confirm_exit', lambda self, busy: True):
        window = MainWindow()
        window.move(app.primaryScreen().availableGeometry().topLeft() + QPoint(20, 20))
        window.show()
        window.add_scanned_file(str(video), {'streams': [{'codec_type': 'video', 'codec_name': 'h264',
            'width': 1920, 'height': 1080, 'bit_rate': '8000000'},
            {'codec_type': 'audio', 'codec_name': 'aac', 'profile': 'LC', 'bit_rate': '192000', 'max_bit_rate': 256000}],
            'format': {'duration': '120', 'size': video.stat().st_size}})
        window.time_preview.pause()  # Chooser fixture bytes are not an encoded video.
        QTest.qWait(40)
        smooth(window.file_list_widget)
        for language in ('ko', 'en'):
            language_manager().set_language(language)
            for width, height in ((1240, 850), (1000, 680)):
                window.resize(width, height)
                for opened in (False, True):
                    window.log_toggle.setChecked(opened)
                    window.progress_summary.setText('분석 완료 · 17개 추가 / 0개 제외 (읽기 실패·기존 변환 결과 등)')
                    QTest.qWait(40)
                    summary = window.progress_summary
                    assert summary.height() >= summary.heightForWidth(summary.width())
                    assert summary.mapTo(window, QPoint()).y() + summary.height() <= window.overall_progress_bar.mapTo(window, QPoint()).y()
                    smooth(summary)
                    report['layouts'].append({'language': language, 'size': [width, height], 'log': opened, 'overlap': False})
            window.resize(1240, 850)
            window.log_toggle.setChecked(False)
            app.processEvents()
            capture(window, language + '-workspace')
            window.show_settings_dialog()
            dialog = window.settings_dialog
            for category in dialog.categories:
                dialog.select_category(category)
                QTest.qWait(40)
                smooth(dialog.navigation)
                page = dialog.categories[category][2]
                assert page.widget().width() <= page.viewport().width()
                for label in page.findChildren(type(window.info_summary_label)):
                    if label.isVisible() and label.wordWrap():
                        assert label.height() >= label.heightForWidth(label.width())
                capture(dialog, language + '-settings-' + category)
                report['settings'].append({'language': language, 'category': category,
                                           'light': dialog.palette().color(QPalette.ColorRole.Base).lightness() > 220})
            window.show_settings_dialog(category='help', help_key='quality_value')
            QTest.qWait(40)
            capture(dialog, language + '-settings-help-quality')
            dialog.accept()
            for name, combo in [('preset', window.preset_combo), ('codec', window.codec_combo), ('resolution', window.resolution_combo)]:
                parent = combo.parentWidget()
                while parent and not isinstance(parent, QScrollArea):
                    parent = parent.parentWidget()
                if parent:
                    parent.ensureWidgetVisible(combo)
                app.processEvents()
                combo.showPopup()
                QTest.qWait(60)
                view = combo.view()
                smooth(view)
                image = view.window().grab().toImage()
                assert image.pixelColor(image.width() // 2, 2).lightness() > 170
                rect = view.visualRect(view.currentIndex())
                scale = view.devicePixelRatioF()
                selected = view.viewport().grab().toImage().pixelColor(int((rect.right() - 5) * scale), int(rect.center().y() * scale))
                assert selected.lightness() > 200
                capture(view.window(), language + '-' + name + '-popup')
                report['popups'].append({'language': language, 'name': name, 'light': True, 'hinting': 'PreferNoHinting'})
                combo.hidePopup()
            picker = SourcePickerDialog(str(args.artifacts), window)
            picker.show()
            QTest.qWait(50)
            tree = picker.findChild(QTreeView, 'treeView')
            deadline = 50
            while not tree.model().index(str(video)).isValid() and deadline:
                QTest.qWait(20)
                deadline -= 1
            assert deadline
            for view in picker.findChildren(QAbstractItemView):
                if view.isVisible():
                    smooth(view)
                assert view.palette().color(QPalette.ColorRole.Base).lightness() > 220
            image = tree.viewport().grab().toImage()
            assert image.pixelColor(image.width() // 2, image.height() - 10).lightness() > 230
            capture(picker, language + '-picker')
            picker.setViewMode(QFileDialog.ViewMode.List)
            QTest.qWait(30)
            for view in picker.findChildren(QAbstractItemView):
                if view.isVisible():
                    smooth(view)
            capture(picker, language + '-picker-list')
            picker.setViewMode(QFileDialog.ViewMode.Detail)
            app.processEvents()
            for path in (folder, video):
                tree.selectionModel().select(tree.model().index(str(path)), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            picker.accept()
            assert set(picker.paths) == {str(folder.resolve()), str(video.resolve())}
            report['pickers'].append({'language': language, 'light': True, 'mixed_selection': True})
            about = AboutDialog('3.0.0', window)
            about.show()
            QTest.qWait(30)
            capture(about, language + '-about')
            about.close()
            for busy in (False, True):
                confirmation = ConfirmExitDialog(busy, window)
                confirmation.show()
                QTest.qWait(30)
                capture(confirmation, language + '-exit-' + ('busy' if busy else 'idle'))
                confirmation.reject()
            estimate = EstimateDialog([{'path': str(video), 'source_bytes': 100 * 1048576,
                                         'estimated_bytes': 125 * 1048576, 'state': 'risk'}], window)
            estimate.show()
            QTest.qWait(40)
            for view in estimate.findChildren(QAbstractItemView):
                if view.isVisible():
                    smooth(view)
            capture(estimate, language + '-estimate-warning')
            estimate.reject()
        window.close()
    (args.artifacts / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Windows {args.scale}: 8 layouts, 6 popups, 2 mixed choosers passed; {system_scheme} system → {report["app_scheme"]} app.')


if __name__ == '__main__':
    main()
