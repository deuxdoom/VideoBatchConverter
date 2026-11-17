from pathlib import Path
import wave

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from src.brand_dialog import ConfirmExitDialog
from src.media_summary import source_summary
from src.profiles import PRESETS
from src.queue_widgets import DETAIL_ROLE, STATE_ROLE
from src.settings import SettingsManager
from src.size_estimator import SizeEstimateWorker, estimate_key, sample_ranges
from src.worker import FileConversionTask, WorkerSignals, get_media_info
from tests.test_ui import wait_until


def test_archive_defaults_and_only_original_builtin_migrate(window):
    manager = window.settings_manager
    legacy = dict(PRESETS['아카이빙'], output_format='mkv', preset='아카이빙', preset_kind='builtin')
    manager.save_settings(legacy)
    assert manager.load_settings()['output_format'] == 'mp4'
    window.load_app_settings()
    assert window.preset_combo.currentData() == 'builtin:아카이빙'
    assert window.output_preview_label.text().endswith('_archive.mp4')
    manager.save_user_presets({'내 MKV': {key: value for key, value in legacy.items() if key in PRESETS['아카이빙']}})
    manager.save_settings(dict(legacy, preset_kind='user', preset='내 MKV'))
    assert manager.load_settings()['output_format'] == 'mkv'
    assert manager.load_user_presets()['내 MKV']['output_format'] == 'mkv'
    manager.save_settings(dict(legacy, quality_value='25'))
    assert manager.load_settings()['output_format'] == 'mkv'


def test_source_metadata_includes_codec_bitrate_duration_and_safe_fallbacks(window):
    info = {'streams': [{'codec_type': 'video', 'codec_name': 'mjpeg', 'disposition': {'attached_pic': 1}},
                        {'codec_type': 'video', 'codec_name': 'hevc', 'width': 3840, 'height': 2160, 'bit_rate': '8500000'},
                        {'codec_type': 'audio', 'codec_name': 'aac', 'bit_rate': '192000'}],
            'format': {'duration': '3723.5', 'size': '10000000', 'bit_rate': '9000000'}}
    text = source_summary(info)
    assert '비디오 HEVC · 8500 kb/s  |  오디오 AAC · 192 kb/s' in text
    assert '\n1:02:03 · 3840 × 2160' in text
    window.add_scanned_file('F:/Temp/VideoBatchConverter/source.mp4', info)
    item = window.file_list_widget.item(0)
    assert text == item.data(DETAIL_ROLE)
    assert text in item.toolTip()
    window.file_list_widget.setCurrentRow(0)
    assert window.info_summary_label.text() == text
    info['streams'][1]['bit_rate'] = 'N/A'
    assert '전체 9000 kb/s' in source_summary(info)
    info['format']['bit_rate'] = '3276000'
    assert '전체 3276 kb/s' in source_summary(info)
    assert '비디오 HEVC · —' in source_summary(info)
    assert '—' in source_summary({'streams': [{'codec_type': 'video', 'bit_rate': 'nan'}], 'format': {'duration': 'inf'}})


def test_sample_plan_and_cache_fingerprint(sample_video):
    assert sample_ranges(0) == []
    assert sample_ranges(2) == [(0.0, 2)]
    ranges = sample_ranges(7200)
    assert len(ranges) == 3
    assert sum(length for _, length in ranges) == 12
    assert all(0 <= start < start + length <= 7200 for start, length in ranges)
    settings = dict(PRESETS['아카이빙'])
    assert estimate_key(sample_video, settings) != estimate_key(sample_video, dict(settings, quality_value='26'))
    assert estimate_key(sample_video, settings) == estimate_key(sample_video, dict(settings, suffix='_renamed', parallel_jobs=8, keep_smaller=False))
    assert estimate_key(sample_video, settings) != estimate_key(sample_video, dict(settings, gpu_processing=False))


def test_actual_estimate_warns_about_larger_output_and_reuses_cache(app, sample_video, tmp_path, monkeypatch):
    settings = dict(PRESETS['아카이빙'], codec='AVC (H.264) - CPU', rate_control='CRF',
                    quality_value='0', adaptive_quality=False, suffix='_sample_risk')
    worker = SizeEstimateWorker([(str(sample_video), get_media_info(sample_video))], settings, temp_root=tmp_path)
    worker.run()
    result = worker.results[0]
    assert result['state'] == 'risk', result
    assert result['estimated_bytes'] > result['source_bytes']
    assert not list(tmp_path.glob('VideoBatchConverter-estimate-*'))
    assert not sample_video.with_name(sample_video.stem + '_sample_risk.mp4').exists()
    cached = SizeEstimateWorker([(str(sample_video), {})], settings, {result['key']: result}, temp_root=tmp_path)
    monkeypatch.setattr(cached, 'capture', lambda *args, **kwargs: pytest.fail('Cached estimate must not encode again'))
    cached.run()
    assert cached.results[0]['estimated_bytes'] == result['estimated_bytes']
    assert cached.results[0]['cached']


def test_stop_and_restart_preflight_reuses_finished_estimate_only(window, app, sample_video, monkeypatch):
    first = str(sample_video.resolve())
    second_path = sample_video.with_name('restart-estimate.mp4')
    second_path.write_bytes(sample_video.read_bytes())
    second = str(second_path.resolve())
    for path in (first, second):
        window.add_scanned_file(path, get_media_info(path))
    window.restore_options(dict(PRESETS['1080p'], codec='AVC (H.264) - CPU', rate_control='CRF', quality_value='19', suffix='_resume_estimate'))
    window.estimate_size_check.setChecked(True)
    captures, resumed, waiting = [], [], []
    original = SizeEstimateWorker.capture
    def capture(worker, command, timeout=90):
        if '-i' in command:
            path = command[command.index('-i') + 1]
            if path == second and not resumed:
                waiting.append(True)
                while not worker.is_cancelled():
                    worker.msleep(10)
                raise InterruptedError()
            captures.append(path)
        return original(worker, command, timeout)
    monkeypatch.setattr(SizeEstimateWorker, 'capture', capture)
    started = []
    monkeypatch.setattr(window, 'begin_conversion', lambda *args: started.append(True))
    window.start_conversion()
    wait_until(app, lambda: bool(waiting))
    window.stop_button.click()
    wait_until(app, lambda: not window.preflighting)
    assert len(window.estimate_cache) == 1 and not started
    assert captures == [first]
    resumed.append(True)
    window.start_conversion()
    wait_until(app, lambda: not window.preflighting)
    assert started == [True]
    assert captures == [first, second]
    assert len(window.estimate_cache) == 2
    assert any(message.startswith('예측 재사용 · ' + sample_video.name) for message in window.log_entries)


@pytest.mark.parametrize('action', ['adjust', 'skip', 'continue'])
def test_warning_decision_precedes_full_encoding(window, app, sample_video, monkeypatch, action):
    from src import ui_mainwindow
    path = str(sample_video.resolve())
    window.add_scanned_file(path, get_media_info(path))
    window.estimate_size_check.setChecked(True)
    class Estimator(SizeEstimateWorker):
        def run(self):
            record = {'path': path, 'state': 'risk', 'source_bytes': 100, 'estimated_bytes': 150}
            self.results = [record]
            self.progress.emit(path, record, 1, 1)
    monkeypatch.setattr(ui_mainwindow, 'SizeEstimateWorker', Estimator)
    decisions, started = [], []
    monkeypatch.setattr(window, 'choose_estimate_action', lambda problems: decisions.append(problems) or action)
    monkeypatch.setattr(window, 'begin_conversion', lambda items, settings: started.append(items))
    window.start_conversion()
    assert window.preflighting and not started
    wait_until(app, lambda: not window.preflighting)
    assert len(decisions) == 1
    assert len(started) == (1 if action == 'continue' else 0)
    if action == 'skip':
        assert window.file_list_widget.item(0).data(STATE_ROLE) == '예측 제외'
        assert window.state_badge.text() == '변환 대상 없음'
    elif action == 'adjust':
        assert window.state_badge.text() == '설정 확인'


def test_cancel_estimate_does_not_start_encoding(window, app, sample_video, monkeypatch):
    from src import ui_mainwindow
    class Estimator(SizeEstimateWorker):
        def run(self):
            while not self.is_cancelled():
                self.msleep(10)
    monkeypatch.setattr(ui_mainwindow, 'SizeEstimateWorker', Estimator)
    window.add_scanned_file(str(sample_video), get_media_info(sample_video))
    window.estimate_size_check.setChecked(True)
    started = []
    monkeypatch.setattr(window, 'begin_conversion', lambda *args: started.append(True))
    window.start_conversion()
    window.stop_conversion()
    wait_until(app, lambda: not window.preflighting)
    assert not started and not window.active_tasks
    assert window.state_badge.text() == '중지됨'


def test_first_risk_pauses_before_sampling_the_rest(window, app, sample_video, monkeypatch):
    second = sample_video.with_name('second-risk.mp4')
    second.write_bytes(sample_video.read_bytes())
    for path in (sample_video, second):
        window.add_scanned_file(str(path), get_media_info(path))
    window.restore_options(dict(PRESETS['아카이빙'], codec='AVC (H.264) - CPU', rate_control='CRF',
                                quality_value='0', adaptive_quality=False, suffix='_early_risk'))
    window.estimate_size_check.setChecked(True)
    questions = []
    monkeypatch.setattr(window, 'choose_estimate_action', lambda problems: questions.append(problems) or 'adjust')
    window.start_conversion()
    wait_until(app, lambda: not window.preflighting)
    assert len(questions) == 1 and len(questions[0]) == 1
    assert len(window.estimate_cache) == 1
    assert window.queue_items[str(second.resolve())].data(STATE_ROLE) == '대기'
    assert not window.active_tasks and window.state_badge.text() == '설정 확인'


def test_all_discarded_outputs_are_visible_warn_and_sound_once(window, app, sample_video, monkeypatch):
    from src import ui_mainwindow
    window.add_scanned_file(str(sample_video), get_media_info(sample_video))
    window.estimate_size_check.setChecked(True)
    window.restore_options(dict(PRESETS['아카이빙'], codec='AVC (H.264) - CPU', rate_control='CRF',
                                quality_value='0', adaptive_quality=False, suffix='_discard_notice'))
    warnings, sounds, estimates = [], [], []
    monkeypatch.setattr(window, 'choose_estimate_action', lambda problems: estimates.append(problems) or 'continue')
    monkeypatch.setattr(window, 'show_batch_warning', lambda: warnings.append(True))
    monkeypatch.setattr(ui_mainwindow, 'play_completion_sound', lambda: sounds.append(True))
    window.start_conversion()
    wait_until(app, lambda: not (window.preflighting or window.converting), timeout=20)
    assert estimates and window.results['kept'] == 1
    assert window.state_badge.text() == '확인 필요'
    assert window.file_list_widget.item(0).data(STATE_ROLE) == '결과 제외'
    assert '원본' in window.file_list_widget.item(0).data(DETAIL_ROLE)
    assert '결과 제외 1개' in window.encoding_status_label.text()
    assert warnings == [True] and sounds == [True]


def test_compact_actions_settings_height_and_log_do_not_shrink_queue(window, app):
    window.resize(1240, 850)
    app.processEvents()
    actions = window.findChild(type(window.sidebar), 'conversionActions')
    assert actions is not None and actions.height() < 65
    assert window.preset_combo.mapTo(window, window.preset_combo.rect().topLeft()).y() < 240
    before = window.queue_panel.height()
    window.log_toggle.setChecked(True)
    app.processEvents()
    assert window.queue_panel.height() == before
    assert window.log_dialog.isVisible()
    assert window.encoding_footer.height() < 120


@pytest.mark.parametrize('busy', [False, True])
def test_simple_branded_exit_dialog(busy, window, app):
    dialog = ConfirmExitDialog(busy, window)
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.cancel_button.isDefault()
    QTimer.singleShot(0, dialog.cancel_button.click)
    assert dialog.exec() == QDialog.DialogCode.Rejected
    QTimer.singleShot(0, dialog.exit_button.click)
    assert dialog.exec() == QDialog.DialogCode.Accepted


def test_main_close_can_be_cancelled(window, app, monkeypatch):
    monkeypatch.setattr(window, 'confirm_exit', lambda busy: False)
    window.close()
    assert window.isVisible() and not window._close_pending
    monkeypatch.setattr(window, 'confirm_exit', lambda busy: True)
    window.close()
    assert not window.isVisible()


def test_completion_asset_is_short_pcm():
    path = Path(__file__).resolve().parent.parent / 'assets/audio/complete.wav'
    with wave.open(str(path)) as sound:
        assert sound.getsampwidth() == 2
        assert .05 < sound.getnframes() / sound.getframerate() < 3
