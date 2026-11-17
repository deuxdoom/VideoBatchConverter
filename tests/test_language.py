"""Language changes preserve canonical settings, queue state and running jobs."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLabel

from src.about_dialog import AboutDialog
from src.i18n import get_language, language_manager, tr
from src.profiles import PRESETS, PRESET_KEYS
from src.queue_widgets import DETAIL_ROLE, PATH_ROLE, STATE_ROLE
from src.settings import SettingsManager
from src.source_picker import SourcePickerDialog
from tests.test_ui import wait_until


@pytest.fixture(autouse=True)
def reset_language(app):
    language_manager().set_language('ko')
    yield
    language_manager().set_language('ko')


def switch(window, language, app):
    button = window.title_bar.language_switch.buttons[language]
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert get_language() == language
    assert button.isChecked()


def test_live_language_preserves_custom_preset_files_and_values(window, app, tmp_path):
    values = dict(PRESETS['아카이빙'], preset_option='p7 (느림, 고품질)', suffix='_한글', quality_value='20')
    window.user_presets['작업 완료'] = values.copy()  # A name that also appears in the UI catalog.
    window.settings_manager.save_user_presets(window.user_presets)
    window.rebuild_preset_combo('user:작업 완료')
    window.restore_options(values)
    path = str(tmp_path / '작업 완료.mp4')
    window.add_scanned_file(path, {'streams': [], 'format': {}})
    window.file_list_widget.setCurrentRow(0)
    before = window.get_current_settings()
    window.set_item_state(path, '완료')
    window.queue_items[path].setData(DETAIL_ROLE, '원본 10.0 MB → 결과 7.0 MB · 30.0% 감소')
    window.append_log('완료 · 작업 완료.mp4 · 원본 대비 30.0% 감소')
    switch(window, 'en', app)
    after = window.get_current_settings()
    assert {key: value for key, value in after.items() if key != 'language'} == {key: value for key, value in before.items() if key != 'language'}
    assert window.preset_combo.currentText() == '작업 완료'
    assert window.preset_label.text() == '작업 완료'
    assert window.preset_option_combo.currentText() == 'p7 (slow, higher quality)'
    assert window.file_list_widget.currentItem().data(PATH_ROLE) == path
    assert window.queue_items[path].data(STATE_ROLE) == '완료'
    assert '작업 완료.mp4' in window.queue_items[path].text()
    assert '30.0% smaller' in window.queue_items[path].text()
    assert window.log_edit.toPlainText().startswith('Done · 작업 완료.mp4')
    assert window.start_button.text() == 'Convert 1 file'
    assert SettingsManager().load_settings()['language'] == 'en'
    assert SettingsManager().load_user_presets()['작업 완료'] == values
    switch(window, 'ko', app)
    assert window.preset_option_combo.currentText() == 'p7 (느림, 고품질)'
    assert window.log_edit.toPlainText().startswith('완료 · 작업 완료.mp4')


@pytest.mark.parametrize('name', PRESETS)
def test_presets_in_english_keep_worker_values(window, app, name):
    switch(window, 'en', app)
    window.apply_preset(name)
    actual = window.get_current_settings()
    assert {key: actual[key] for key in PRESET_KEYS} == PRESETS[name]
    assert 'language' not in PRESET_KEYS
    window.save_app_settings()
    window.apply_preset('720p' if name != '720p' else '아카이빙')
    window.load_app_settings()
    assert {key: window.get_current_settings()[key] for key in PRESET_KEYS} == PRESETS[name]


def test_switch_during_actual_encoding_keeps_tasks_and_selection(window, app, sample_video):
    window.add_scanned_file(str(sample_video), {'streams': [], 'format': {}})
    window.file_list_widget.setCurrentRow(0)
    window.restore_options(dict(PRESETS['아카이빙'], codec='AVC (H.264) - CPU', rate_control='CRF',
                                quality_value='20', suffix='_language', keep_smaller=False, parallel_jobs=1))
    window.start_conversion()
    tasks = window.active_tasks.copy()
    switch(window, 'en', app)
    assert tasks and (window.active_tasks == tasks or not window.converting)
    wait_until(app, lambda: not window.converting)
    assert window.results['done'] == 1
    assert window.state_badge.text() == 'Finished'
    assert window.progress_title.text() == 'Finished'
    assert 'Done 1' in window.queue_summary_label.text()
    assert window.file_list_widget.currentItem().data(PATH_ROLE) == str(sample_video.resolve())
    switch(window, 'ko', app)
    assert window.progress_title.text() == '작업 완료'
    assert window.log_edit.toPlainText().rstrip().endswith('완료 1 · 건너뜀 0 · 결과 제외 0 · 실패 0 · 중지 0')


@pytest.mark.parametrize('size', [(1240, 850), (1000, 680)])
def test_english_summary_and_buttons_do_not_overlap(window, app, size):
    switch(window, 'en', app)
    window.resize(*size)
    window.progress_summary.setText('분석 완료 · 123개 추가 / 12개 제외 (읽기 실패·기존 변환 결과 등)')
    for opened in (False, True):
        window.log_toggle.setChecked(opened)
        app.processEvents()
        summary = window.progress_summary
        assert summary.height() >= summary.heightForWidth(summary.width())
        assert summary.mapTo(window, QPoint()).y() + summary.height() <= window.overall_progress_bar.mapTo(window, QPoint()).y()
        assert window.title_bar.language_switch.geometry().right() < window.title_bar.settings_button.geometry().left()
        assert window.progress_title.geometry().right() < window.log_toggle.geometry().left()


def test_english_dialogs_and_keyboard_switch(window, app, tmp_path):
    button = window.title_bar.language_switch.buttons['en']
    button.setFocus()
    QTest.keyClick(button, Qt.Key.Key_Space)
    app.processEvents()
    assert get_language() == 'en'
    about = AboutDialog('3.0.0', window)
    assert about.windowTitle() == 'About VideoBatchConverter'
    assert any('3.0.0' in label.text() and 'Clear videos.' in label.text() for label in about.findChildren(QLabel))
    assert not any('배포 예정' in label.text() for label in about.findChildren(QLabel))
    picker = SourcePickerDialog(str(tmp_path), window)
    assert picker.windowTitle() == 'Add files or folders'
    assert picker.add_button.text() == 'Add selection'
    picker.close()
    about.close()
    assert tr('설정을 확인해 주세요') == 'Check your settings'
    assert tr('선택 2개 · 변환 대상 2개') == '2 selected · 2 to convert'
    assert tr('03  확인 필요') == '03  Needs attention'


def test_saved_language_is_used_on_next_launch(window, app):
    from src.ui_mainwindow import MainWindow
    switch(window, 'en', app)
    window.apply_preset('1080p')
    window.save_app_settings()
    reopened = MainWindow()
    try:
        assert reopened.state_badge.text() == 'Ready'
        assert reopened.title_bar.language_switch.buttons['en'].isChecked()
        assert reopened.preset_combo.currentData() == 'builtin:1080p'
        assert reopened.get_current_settings()['resolution'] == '1080p'
    finally:
        reopened.close()
