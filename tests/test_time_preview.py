"""Sample timing, invalidation and ownership of the relocated advanced controls."""

import threading
import time

from src.i18n import language_manager
from src.media_summary import bitrate_text
from src.profiles import PRESETS
from src.queue_widgets import TIME_ESTIMATE_ROLE, PATH_ROLE, STATE_ROLE, DETAIL_ROLE, ESTIMATE_ROLE, queue_details, size_estimate_text
from src.settings import SettingsManager
from src.size_estimator import SizeEstimateWorker, estimate_key
from src.worker import get_media_info


def wait_until(app, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    app.processEvents()
    assert predicate()


def add_cpu_video(window, sample_video):
    window.restore_options(dict(PRESETS['1080p'], codec='AVC (H.264) - CPU', rate_control='CRF', quality_value='19'))
    window.add_scanned_file(str(sample_video), get_media_info(sample_video))
    return window.file_list_widget.item(0)


def test_all_advanced_controls_live_only_in_settings_and_persist(window, app):
    window.show_settings_dialog(category='advanced')
    dialog = window.settings_dialog
    assert not hasattr(window, 'advanced_toggle')
    for name in ('preset_option_combo', 'rate_control_combo', 'suffix_edit', 'parallel_jobs_spinbox',
                 'keep_smaller_check', 'estimate_size_check', 'gpu_processing_check'):
        control = getattr(window, name)
        assert getattr(dialog, name) is control
        assert dialog.isAncestorOf(control) and not window.sidebar.isAncestorOf(control)
    assert dialog.isAncestorOf(window.completion_sound_check)
    window.select_value(dialog.preset_option_combo, 'p7 (느림, 고품질)')
    dialog.suffix_edit.setText('_custom_time')
    dialog.parallel_jobs_spinbox.setValue(1)
    dialog.keep_smaller_check.setChecked(False)
    saved = SettingsManager().load_settings()
    assert saved['preset_option'] == 'p7 (느림, 고품질)'
    assert saved['suffix'] == '_custom_time' and saved['parallel_jobs'] == 1
    assert saved['keep_smaller'] is False
    window.preflighting = True
    window.refresh_controls()
    assert not dialog.rate_control_combo.isEnabled() and not dialog.suffix_edit.isEnabled()
    assert dialog.completion_sound_check.isEnabled()
    window.preflighting = False


def test_video_audio_and_total_bitrates_always_use_integer_kbps():
    assert bitrate_text(8_500_000) == '8500 kb/s'
    assert bitrate_text(1_000_000) == '1000 kb/s'
    assert bitrate_text(192_000) == '192 kb/s'
    assert bitrate_text('N/A') == bitrate_text('nan') == bitrate_text(0) == '—'


def test_automatic_time_preview_reuses_samples_and_preserves_selection(window, app, sample_video, monkeypatch):
    item = add_cpu_video(window, sample_video)
    window.file_list_widget.setCurrentItem(item)
    wait_until(app, lambda: item.data(TIME_ESTIMATE_ROLE).get('estimated_seconds') is not None
               and window.time_preview.worker is None)
    result = item.data(TIME_ESTIMATE_ROLE)
    assert result['estimated_seconds'] > 0 and result['sample_seconds'] == 1
    assert item.data(STATE_ROLE) == '대기'
    assert item.data(ESTIMATE_ROLE)['estimated_bytes'] == result['estimated_bytes']
    assert size_estimate_text(result) in item.text() and size_estimate_text(result) in queue_details(item)
    assert '예상 약' in item.text() and '예상 시간 합계 · 약' in window.time_summary_label.text()
    assert not list(sample_video.parent.glob('VideoBatchConverter-estimate-*'))
    monkeypatch.setattr(SizeEstimateWorker, 'capture', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Must reuse samples')))
    window.suffix_edit.setText('_renamed_time')
    window.parallel_jobs_spinbox.setValue(1)
    assert not window.time_preview.timer.isActive()
    assert item.data(TIME_ESTIMATE_ROLE)['estimated_seconds'] == result['estimated_seconds']
    try:
        language_manager().set_language('en')
        assert 'Approx.' in item.text() and 'Total estimated time' in window.time_summary_label.text()
        assert 'Estimated ' in item.text() and '예상 용량' not in item.text()
        assert window.file_list_widget.currentItem() is item
        assert window.time_preview.worker is None
    finally:
        language_manager().set_language('ko')
    window.estimate_size_check.setChecked(True)
    started = []
    monkeypatch.setattr(window, 'begin_conversion', lambda items, settings: started.append(items))
    window.start_conversion()
    wait_until(app, lambda: not window.preflighting)
    assert started and window.estimate_worker is None
    assert item.data(ESTIMATE_ROLE)['cached']


def test_changed_settings_hide_old_times_and_file_changes_invalidate_cache(window, app, sample_video):
    item = add_cpu_video(window, sample_video)
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(TIME_ESTIMATE_ROLE).get('estimated_seconds') is not None)
    first_key = item.data(TIME_ESTIMATE_ROLE)['key']
    window.adaptive_quality_check.setChecked(False)
    window.quality_edit.setText('24')
    assert item.data(TIME_ESTIMATE_ROLE)['state'] == 'pending'
    assert item.data(ESTIMATE_ROLE)['state'] == 'pending'
    assert 'estimated_bytes' not in item.data(ESTIMATE_ROLE)
    assert '예상 용량 계산 대기' in queue_details(item)
    assert 'estimated_seconds' not in item.data(TIME_ESTIMATE_ROLE)
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(TIME_ESTIMATE_ROLE).get('estimated_seconds') is not None)
    assert item.data(TIME_ESTIMATE_ROLE)['key'] != first_key
    sample_video.touch()
    window.time_preview.schedule()
    assert item.data(TIME_ESTIMATE_ROLE)['state'] == 'pending'


def test_time_sum_follows_target_selection_and_unknown_files_are_explicit(window, app, tmp_path):
    first = tmp_path / 'first.mp4'
    second = tmp_path / 'second.mp4'
    first.write_bytes(b'fixture')
    second.write_bytes(b'fixture')
    window.add_scanned_file(str(first), {})
    window.add_scanned_file(str(second), {})
    items = list(window.queue_items.values())
    for item, seconds in zip(items, (60, 120)):
        item.setData(TIME_ESTIMATE_ROLE, {'estimated_seconds': seconds})
    window.update_time_summary()
    assert '3:00 (2/2개)' in window.time_summary_label.text()
    window.file_list_widget.setCurrentItem(items[1])
    window.selection_only_check.setChecked(True)
    assert '2:00 (1/1개)' in window.time_summary_label.text()
    window.quality_edit.setText('invalid')
    assert items[1].data(TIME_ESTIMATE_ROLE)['state'] == 'unknown'
    assert items[1].data(ESTIMATE_ROLE)['state'] == 'unknown'
    assert '예상 용량 —' in items[1].text()
    assert '예상 시간 —' in items[1].text() and '계산 실패' in items[1].toolTip()
    assert not window.time_preview.timer.isActive()


def test_cancelled_old_preview_cannot_restore_stale_times(window, app, sample_video, monkeypatch):
    item = add_cpu_video(window, sample_video)
    entered = threading.Event()
    def delayed_run(worker):
        entered.set()
        while not worker.is_cancelled():
            time.sleep(.01)
        # Simulate a completion queued just as cancellation arrived.
        result = {'path': str(sample_video), 'state': 'safe', 'estimated_seconds': 9999,
                  'estimated_bytes': 1, 'key': estimate_key(sample_video, worker.settings)}
        worker.results.append(result)
        worker.progress.emit(str(sample_video), result, 1, 1)
    monkeypatch.setattr(SizeEstimateWorker, 'run', delayed_run)
    window.time_preview.timer.stop()
    window.time_preview.start()
    wait_until(app, entered.is_set)
    window.adaptive_quality_check.setChecked(False)
    window.quality_edit.setText('25')
    wait_until(app, lambda: window.time_preview.worker is None)
    assert item.data(TIME_ESTIMATE_ROLE)['state'] == 'pending'
    assert item.data(ESTIMATE_ROLE)['state'] == 'pending'
    assert 'estimated_bytes' not in item.data(ESTIMATE_ROLE)
    assert '9999' not in item.text()
    window.clear_queue()
    assert not window.estimate_cache and not window.time_preview.timer.isActive()


def test_start_waits_for_preview_cleanup_and_can_cancel_handoff(window, app, sample_video, monkeypatch):
    add_cpu_video(window, sample_video)
    entered, release = threading.Event(), threading.Event()
    def delayed_run(worker):
        entered.set()
        release.wait(5)
    monkeypatch.setattr(SizeEstimateWorker, 'run', delayed_run)
    window.time_preview.timer.stop()
    window.time_preview.start()
    wait_until(app, entered.is_set)
    started = []
    monkeypatch.setattr(window, 'begin_conversion', lambda items, settings: started.append(items))
    window.start_conversion()
    assert window.preflighting and not started
    window.stop_conversion()
    release.set()
    wait_until(app, lambda: window.time_preview.worker is None)
    assert not started and not window.preflighting


def test_closing_during_preview_waits_for_thread_and_discards_deferred_start(window, app, sample_video, monkeypatch):
    add_cpu_video(window, sample_video)
    entered = threading.Event()
    def delayed_run(worker):
        entered.set()
        while not worker.is_cancelled():
            time.sleep(.01)
    monkeypatch.setattr(SizeEstimateWorker, 'run', delayed_run)
    window.time_preview.timer.stop()
    window.time_preview.start()
    wait_until(app, entered.is_set)
    window.close()
    wait_until(app, lambda: not window.isVisible())
    assert window.time_preview.worker is None and window._close_pending


def test_changing_quality_updates_visible_size_and_restoring_settings_uses_correct_cache(window, app, sample_video):
    item = add_cpu_video(window, sample_video)
    window.adaptive_quality_check.setChecked(False)
    window.quality_edit.setText('12')
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('estimated_bytes') is not None)
    larger = item.data(ESTIMATE_ROLE)
    first_text = size_estimate_text(larger)
    assert first_text in item.text() and first_text in item.toolTip()
    window.quality_edit.setText('40')
    assert '예상 용량 계산 대기' in item.text() and first_text not in queue_details(item)
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('estimated_bytes') is not None)
    smaller = item.data(ESTIMATE_ROLE)
    assert smaller['key'] != larger['key']
    assert smaller['estimated_bytes'] < larger['estimated_bytes']
    assert size_estimate_text(smaller) != first_text
    assert size_estimate_text(smaller) in item.text() and size_estimate_text(smaller) in item.toolTip()
    window.quality_edit.setText('12')
    assert not window.time_preview.timer.isActive()
    assert item.data(ESTIMATE_ROLE)['estimated_bytes'] == larger['estimated_bytes']
    assert first_text in queue_details(item) and first_text in item.text()


def test_new_estimates_preserve_completed_results_and_do_not_duplicate_sizes(window, app, sample_video):
    item = add_cpu_video(window, sample_video)
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('estimated_bytes') is not None)
    window.set_item_state(item.data(PATH_ROLE), '완료')
    result_details = item.data(DETAIL_ROLE) + ' · 원본 10.0 MB → 결과 7.0 MB · 30.0% 감소'
    item.setData(DETAIL_ROLE, result_details)
    window.adaptive_quality_check.setChecked(False)
    window.quality_edit.setText('33')
    assert item.data(DETAIL_ROLE) == result_details
    assert item.data(STATE_ROLE) == '완료'
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('estimated_bytes') is not None)
    assert item.data(DETAIL_ROLE) == result_details
    assert queue_details(item).count(' · 예상 ') == 1
    assert '원본 10.0 MB → 결과 7.0 MB' in item.text()


def test_sample_failure_clears_previous_visible_size(window, app, sample_video, monkeypatch):
    item = add_cpu_video(window, sample_video)
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('estimated_bytes') is not None)
    previous = size_estimate_text(item.data(ESTIMATE_ROLE))
    monkeypatch.setattr(SizeEstimateWorker, 'capture', lambda *args, **kwargs: (1, 'Sample failed'))
    window.adaptive_quality_check.setChecked(False)
    window.quality_edit.setText('32')
    wait_until(app, lambda: window.time_preview.worker is None
               and item.data(ESTIMATE_ROLE).get('state') == 'unknown')
    assert '예상 용량 —' in item.text() and previous not in queue_details(item)
    assert 'Sample failed' in item.toolTip()
    try:
        language_manager().set_language('en')
        assert 'Est. size —' in item.text() and '예상 용량' not in item.text()
    finally:
        language_manager().set_language('ko')
