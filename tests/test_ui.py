from pathlib import Path
import time

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from src.profiles import PRESETS
from src.ui_mainwindow import INFO_ROLE, PATH_ROLE


def wait_until(app, condition, timeout=10):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert condition(), 'Timed out waiting for Qt worker'


@pytest.mark.parametrize('name', PRESETS)
def test_presets_are_applied_exactly(window, name):
    window.preset_combo.setCurrentIndex(window.preset_combo.findData('builtin:' + name))
    actual = window.get_current_settings()
    for key, value in PRESETS[name].items():
        assert actual[key] == value, (name, key, actual[key], value)
    assert window.preset_combo.currentData() == 'builtin:' + name
    assert window.preset_option_combo.isEnabled() == ('GPU' in actual['codec'])


def test_custom_quality_and_mode_survive_restore(window):
    values = dict(PRESETS['720p'], suffix='_custom', quality_value='7.5M', rate_control='VBR', adaptive_quality=False, keep_smaller=False)
    window.restore_options(values)
    window.update_quality_label()
    window.update_encoder_options()
    assert window.rate_control_combo.currentText() == 'VBR'
    assert window.quality_edit.text() == '7500'
    assert window.preset_label.text() == '사용자 정의'
    window.save_app_settings()
    window.apply_preset(next(iter(PRESETS)))
    window.load_app_settings()
    assert window.rate_control_combo.currentText() == 'VBR'
    assert window.quality_edit.text() == '7500'
    assert window.suffix_edit.text() == '_custom'


def test_codec_and_rate_changes_keep_valid_values(window):
    window.apply_preset('아카이빙')
    window.codec_combo.setCurrentText('AV1 - CPU')
    assert window.rate_control_combo.currentText() == 'VBR'
    assert window.quality_edit.text() == '8000'
    assert not window.preset_option_combo.isEnabled()
    window.rate_control_combo.setCurrentText('VBR')
    assert window.quality_edit.text() == '8000'
    window.quality_edit.setText('6000000')
    window.codec_combo.setCurrentText('H.265 (HEVC) - CPU')
    assert window.quality_edit.text() == '6000000'
    window.rate_control_combo.setCurrentText('CRF')
    assert window.quality_edit.text() == '23'


def test_queue_selection_is_explicit_and_remove_works(window):
    for name in ('one.mp4', 'two.mp4'):
        window.add_scanned_file('F:/Temp/VideoBatchConverter/' + name, {'streams': [], 'format': {}})
    window.file_list_widget.setCurrentRow(0)
    assert len(window.target_items()) == 2
    window.selection_only_check.setChecked(True)
    assert len(window.target_items()) == 1
    window.remove_selected_files()
    assert len(window.queue_items) == 1
    assert window.file_list_widget.count() == 1
    window.clear_queue()
    assert window.empty_state.isVisible()
    assert not window.start_button.isEnabled()


def test_background_scan_and_conversion_workflow(window, app, sample_video):
    window.add_paths_to_queue([str(sample_video)])
    assert window.scanning and not window.start_button.isEnabled()
    wait_until(app, lambda: not window.scanning)
    assert window.file_list_widget.count() == 1
    assert window.file_list_widget.item(0).data(INFO_ROLE)['streams']
    window.restore_options(dict(PRESETS[next(iter(PRESETS))], codec='AVC (H.264) - CPU',
                                rate_control='CRF', quality_value='28', adaptive_quality=False, keep_smaller=False, suffix='_ui', output_format='mkv'))
    window.start_conversion()
    assert window.converting and not window.clear_btn.isEnabled()
    window.add_paths_to_queue([str(sample_video)])
    window.clear_queue()
    assert window.file_list_widget.count() == 1
    wait_until(app, lambda: not window.converting, timeout=20)
    assert window.results['done'] == 1
    assert sample_video.with_name(sample_video.stem + '_ui.mkv').exists()
    assert window.overall_progress_bar.value() == 100
    assert window.start_button.isEnabled()
    # Existing output is a separate skipped result, never falsely counted as encoded.
    window.start_conversion()
    wait_until(app, lambda: not (window.converting or window.preflighting))
    assert window.results['skipped'] == 1
    assert window.results['done'] == 0


def test_failed_job_is_not_reported_as_success(window, app):
    window.add_scanned_file('F:/Temp/VideoBatchConverter/does-not-exist.mp4', {'streams': [], 'format': {}})
    window.restore_options(dict(PRESETS[next(iter(PRESETS))], codec='AVC (H.264) - CPU', rate_control='CRF', quality_value='20'))
    window.start_conversion()
    wait_until(app, lambda: not (window.converting or window.preflighting))
    assert window.results['failed'] == 1
    assert window.results['done'] == 0
    assert window.state_badge.text() == '확인 필요'
    assert window.log_edit.isVisible()


def test_stop_drains_jobs_before_unlocking(window, app, sample_video):
    for index in range(5):
        path = sample_video.parent / f'queued-{index}.mp4'
        path.write_bytes(sample_video.read_bytes())
        window.add_scanned_file(str(path), {'streams': [], 'format': {}})
    window.restore_options(dict(PRESETS[next(iter(PRESETS))], codec='AV1 - CPU', rate_control='CRF', quality_value='20', keep_smaller=False, parallel_jobs=1))
    window.start_conversion()
    window.stop_conversion()
    assert window.converting
    assert not window.start_button.isEnabled()
    wait_until(app, lambda: not window.converting, timeout=25)
    assert window.results['stopped'] == 5
    assert window.start_button.isEnabled()
    assert not list(sample_video.parent.glob('*.partial*'))


def test_chrome_resize_hit_regions_and_maximize(window, app):
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.resize_edges(QPoint(1, 1)) == (Qt.Edge.LeftEdge | Qt.Edge.TopEdge)
    assert window.resize_edges(QPoint(window.width() - 1, window.height() - 1)) == (Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
    assert not window.resize_edges(QPoint(50, 50))
    window.title_bar.toggle_maximized()
    app.processEvents()
    assert window.isMaximized()
    assert not window.resize_edges(QPoint(1, 1))
    window.title_bar.toggle_maximized()
    app.processEvents()
    assert not window.isMaximized()


def test_small_layout_and_advanced_controls_remain_reachable(window, app):
    window.resize(1000, 680)
    app.processEvents()
    assert window.empty_state.isVisible()
    assert window.empty_hint.isVisible()
    assert window.start_button.geometry().right() <= window.start_button.parentWidget().width()
    window.show_settings_dialog(category='advanced')
    assert window.advanced_panel.isVisible()
    window.log_toggle.setChecked(True)
    assert window.log_edit.isVisible()


def test_missing_metadata_and_update_notice_are_safe(window):
    window.add_scanned_file('F:/Temp/VideoBatchConverter/metadata.mp4',
                            {'streams': [], 'format': {'duration': 'N/A', 'size': 'N/A'}})
    window.file_list_widget.setCurrentRow(0)
    assert '비디오 — · —  |  오디오 없음\n— · — × — · —' == window.info_summary_label.text()
    window.on_update_check_finished({'update': True, 'version': 'v3.1.0'})
    assert window.update_button.isVisible()
    assert '3.1.0' in window.update_button.text()


def test_duplicate_output_is_rejected_before_any_job(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for name in ('same.mp4', 'same.mkv'):
        window.add_scanned_file('F:/Temp/VideoBatchConverter/' + name, {'streams': [], 'format': {}})
    notices = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: notices.append(args[2]))
    window.start_conversion()
    assert notices
    assert not window.converting
    assert not window.active_tasks


def test_close_waits_for_cancellation(window, app, sample_video, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    window.add_scanned_file(str(sample_video), {'streams': [], 'format': {}})
    window.restore_options(dict(PRESETS[next(iter(PRESETS))], codec='AV1 - CPU', rate_control='CRF', quality_value='20', keep_smaller=False, suffix='_close'))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window.start_conversion()
    window.close()
    assert window._close_pending
    assert not window.start_button.isEnabled()
    wait_until(app, lambda: not window.isVisible(), timeout=25)
    assert not window.active_tasks
    assert window.results['stopped'] == 1
