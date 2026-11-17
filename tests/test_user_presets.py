import json

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from src.profiles import PRESETS, PRESET_KEYS
from src.settings import SettingsManager


def save_named(window, monkeypatch, name):
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: (name, True))
    window.save_user_preset()


def test_named_preset_round_trip_and_reapply(window, monkeypatch):
    window.restore_options(dict(PRESETS['720p'], suffix='_mine', quality_value='7.5M', rate_control='VBR', adaptive_quality=False, keep_smaller=False))
    expected = {key: window.get_current_settings()[key] for key in PRESET_KEYS}
    save_named(window, monkeypatch, '내 보관 설정')
    assert window.preset_combo.currentData() == 'user:내 보관 설정'
    assert window.delete_preset_btn.isEnabled()
    # Read a new manager from disk, including Korean names and all encoding fields.
    assert SettingsManager().load_user_presets()['내 보관 설정'] == expected
    window.save_app_settings()
    window.apply_preset(next(iter(PRESETS)))
    window.load_app_settings()
    assert window.preset_combo.currentData() == 'user:내 보관 설정'
    for key, value in expected.items():
        assert window.get_current_settings()[key] == value
    window.apply_preset(next(iter(PRESETS)))
    window.preset_combo.setCurrentIndex(window.preset_combo.findData('user:내 보관 설정'))
    assert window.quality_edit.text() == '7500'
    assert window.suffix_edit.text() == '_mine'


def test_identical_builtin_values_keep_selected_user_name(window, monkeypatch):
    window.apply_preset(next(iter(PRESETS)))
    save_named(window, monkeypatch, '나의 기본값')
    assert window.preset_combo.currentData() == 'user:나의 기본값'
    window.quality_edit.setText('30')
    assert window.preset_combo.currentIndex() == -1
    window.preset_combo.setCurrentIndex(window.preset_combo.findData('user:나의 기본값'))
    assert window.preset_combo.currentData() == 'user:나의 기본값'
    assert window.quality_edit.text() == '8000'


def test_overwrite_confirmation_and_delete_keep_current_values(window, monkeypatch):
    window.quality_edit.setText('30')
    save_named(window, monkeypatch, '보관')
    window.quality_edit.setText('33')
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    save_named(window, monkeypatch, '보관')
    assert SettingsManager().load_user_presets()['보관']['quality_value'] == '30'
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    save_named(window, monkeypatch, '보관')
    assert SettingsManager().load_user_presets()['보관']['quality_value'] == '33'
    window.delete_user_preset()
    assert '보관' not in SettingsManager().load_user_presets()
    assert window.quality_edit.text() == '33'
    assert window.preset_combo.findData('user:보관') == -1


def test_cancel_invalid_name_and_save_error_leave_presets_unchanged(window, monkeypatch):
    notices = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: notices.append(args[2]))
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('취소', False))
    window.save_user_preset()
    assert window.user_presets == {}
    for name in ('', 'x' * 61, next(iter(PRESETS))):
        save_named(window, monkeypatch, name)
    assert len(notices) == 3
    def fail_save(values):
        raise OSError('write denied')
    monkeypatch.setattr(window.settings_manager, 'save_user_presets', fail_save)
    save_named(window, monkeypatch, '저장 실패')
    assert window.user_presets == {}
    assert notices[-1] == 'write denied'


def test_corrupt_preset_storage_and_malformed_entries(window):
    storage = window.settings_manager.settings
    storage.setValue('user_presets', 'broken json')
    assert window.settings_manager.load_user_presets() == {}
    good = dict(PRESETS[next(iter(PRESETS))], suffix='_saved')
    storage.setValue('user_presets', json.dumps({'정상': good, '오류': dict(good, preset_option=''),
                                               '타입': dict(good, parallel_jobs='2'), '잘못된 품질': dict(good, quality_value='²')}))
    assert list(window.settings_manager.load_user_presets()) == ['정상']


def test_retired_builtin_migrates_without_resetting_user_presets(window):
    manager = window.settings_manager
    manager.save_settings({'preset': 'YouTube 업로드 (720p)', 'preset_kind': 'builtin', 'rate_control': 'VBR',
                           'quality_value': '6M', 'input_folder': 'F:/Videos'})
    restored = manager.load_settings()
    assert restored['preset'] == '720p'
    assert restored['adaptive_quality'] is True
    assert restored['codec'] == 'AVC (H.264) - GPU'
    assert restored['input_folder'] == 'F:/Videos'
    manager.save_settings({'preset_kind': 'user'})
    assert manager.load_settings()['quality_value'] == '6000'
