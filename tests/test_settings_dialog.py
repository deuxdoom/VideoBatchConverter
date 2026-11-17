"""Preferences stay synchronized, persist, and respect active batch locks."""

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.i18n import language_manager, tr
from src.profiles import HELP_DETAILS, HELP_TEXTS
from src.queue_widgets import DETAIL_ROLE
from src.settings import SettingsManager


def test_settings_button_categories_help_links_and_reopen(window, app):
    QTest.mouseClick(window.title_bar.settings_button, Qt.MouseButton.LeftButton)
    dialog = window.settings_dialog
    assert dialog.isVisible() and not dialog.isModal()
    assert set(dialog.categories) == {'general', 'advanced', 'folders', 'help', 'about'}
    assert dialog.navigation.currentItem().data(Qt.ItemDataRole.UserRole) == 'general'
    dialog.accept()
    button = next(button for button in window.quality_field.findChildren(type(window.title_bar.settings_button))
                  if button.toolTip() == HELP_TEXTS['quality_value'])
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert window.settings_dialog is dialog and dialog.isVisible()
    assert dialog.navigation.currentItem().data(Qt.ItemDataRole.UserRole) == 'help'
    heading = dialog.help_sections['quality_value']
    scroll = dialog.categories['help'][2]
    assert 0 <= heading.mapTo(scroll.viewport(), heading.rect().topLeft()).y() < scroll.viewport().height()
    assert len(HELP_TEXTS['quality_value']) < len(HELP_DETAILS['quality_value']) / 2


def test_preferences_persist_and_lock_during_preflight(window, app):
    window.show_settings_dialog()
    dialog = window.settings_dialog
    dialog.completion_sound_check.setChecked(False)
    assert not window.completion_sound_check.isChecked()
    assert not SettingsManager().load_settings()['completion_sound']
    dialog.estimate_size_check.setChecked(True)
    assert window.estimate_size_check.isChecked()
    assert SettingsManager().load_settings()['estimate_size']
    window.preflighting = True
    window.refresh_controls()
    assert not dialog.estimate_size_check.isEnabled()
    assert not dialog.gpu_processing_check.isEnabled()
    assert not dialog.folder_browse.isEnabled()
    assert dialog.completion_sound_check.isEnabled()
    dialog.completion_sound_check.setChecked(True)
    assert SettingsManager().load_settings()['completion_sound']
    try:
        dialog.language_switch.buttons['en'].click()
        app.processEvents()
        assert dialog.navigation.item(0).text() == 'General'
        assert dialog.windowTitle() == 'Settings'
        assert SettingsManager().load_settings()['language'] == 'en'
    finally:
        window.preflighting = False
        language_manager().set_language('ko')
        window.refresh_controls()
    assert dialog.estimate_size_check.isEnabled() and dialog.folder_browse.isEnabled()


def test_folder_choice_is_saved_without_scanning(window, app, tmp_path, monkeypatch):
    from src import settings_dialog
    window.show_settings_dialog(category='folders')
    dialog = window.settings_dialog
    class Picker:
        Option = settings_dialog.SourceFileDialog.Option
        FileMode = settings_dialog.SourceFileDialog.FileMode
        DialogCode = settings_dialog.SourceFileDialog.DialogCode
        def __init__(self, *args): pass
        def setOption(self, *args): pass
        def setFileMode(self, *args): pass
        def exec(self): return self.DialogCode.Accepted
        def selectedFiles(self): return [str(tmp_path)]
        def deleteLater(self): pass
    monkeypatch.setattr(settings_dialog, 'SourceFileDialog', Picker)
    dialog.folder_browse.click()
    assert window.input_path_edit.text() == dialog.folder_path.text() == str(tmp_path)
    assert SettingsManager().load_settings()['input_folder'] == str(tmp_path)
    assert not window.scanning and window.file_list_widget.count() == 0


def test_stream_metadata_and_results_translate_without_losing_details(window, app):
    info = {'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 1920, 'height': 1080},
                        {'codec_type': 'audio', 'codec_name': 'opus', 'bit_rate': '128000'},
                        {'codec_type': 'audio', 'codec_name': 'aac', 'bit_rate': '256000'}],
            'format': {'duration': '65', 'size': '10485760', 'bit_rate': '2000000'}}
    window.add_scanned_file('F:/Temp/VideoBatchConverter/언어.mp4', info)
    item = window.file_list_widget.item(0)
    window.file_list_widget.setCurrentRow(0)
    original = item.data(DETAIL_ROLE)
    window.set_item_state(item.data(Qt.ItemDataRole.UserRole), '용량 주의')
    try:
        language_manager().set_language('en')
        assert 'Video H.264 · —  |  Audio OPUS · 128 kb/s' in item.text()
        assert 'Overall 2000 kb/s' in item.text()
        assert '비디오' not in item.text() and '전체' not in item.text()
        assert 'Audio OPUS' in window.info_summary_label.text()
        assert item.data(DETAIL_ROLE) == original
        completed = original.rsplit(' · ', 1)[0] + ' · 원본 10.0 MB → 결과 7.0 MB · 30.0% 감소'
        translated = tr(completed)
        assert 'Video H.264' in translated and 'Overall 2000 kb/s' in translated
        assert 'Source 10.0 MB → Output 7.0 MB · 30.0% smaller' in translated
    finally:
        language_manager().set_language('ko')
