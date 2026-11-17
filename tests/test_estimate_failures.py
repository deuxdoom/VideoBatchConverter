"""Actionable container compatibility and machine-readable probe output."""

import json
import sys

import pytest

from src.estimate_dialog import EstimateDialog
from src.profiles import PRESETS, validate_media_settings
from src.size_estimator import SizeEstimateWorker
from src.worker import get_media_info
from src.media_summary import source_summary


def test_probe_json_is_not_contaminated_by_stderr(app, tmp_path):
    estimator = SizeEstimateWorker([], PRESETS['아카이빙'], temp_root=tmp_path)
    code, output = estimator.capture([sys.executable, '-c',
        'import sys; print(\'{"packets":[{"size":"100"}]}\'); sys.stderr.write("[aac] diagnostic warning\\n")'])
    assert code == 0 and json.loads(output)['packets'][0]['size'] == '100'
    assert '[aac]' in estimator.last_stderr and '[aac]' not in output


def test_probe_failure_retains_stderr_diagnostic(app, tmp_path):
    estimator = SizeEstimateWorker([], PRESETS['아카이빙'], temp_root=tmp_path)
    code, output = estimator.capture([sys.executable, '-c', 'import sys; sys.stderr.write("Real probe error"); sys.exit(1)'])
    assert code == 1 and 'Real probe error' in output


def test_truehd_mp4_copy_is_blocked_before_sampling_with_recoverable_choices(app, sample_video, tmp_path, monkeypatch):
    info = get_media_info(sample_video)
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    audio['codec_name'] = 'truehd'
    values = dict(PRESETS['아카이빙'], suffix='_truehd')
    worker = SizeEstimateWorker([(str(sample_video), info)], values, temp_root=tmp_path)
    monkeypatch.setattr(worker, 'capture', lambda *args, **kwargs: pytest.fail('Incompatible audio must be detected before encoding'))
    worker.run()
    assert worker.results[0]['state'] == 'blocked'
    assert 'AAC' in worker.results[0]['error'] and 'MKV' in worker.results[0]['error']
    assert validate_media_settings(dict(values, output_format='mkv'), info) is None
    assert validate_media_settings(dict(values, audio_option='AAC 192kbps'), info) is None
    dialog = EstimateDialog(worker.results)
    assert not dialog.continue_button.isEnabled()
    assert dialog.adjust_button.isEnabled() and dialog.skip_button.isEnabled()


def test_mkv_stream_statistics_are_displayed_as_stream_bitrates():
    info = {'streams': [{'codec_type': 'video', 'codec_name': 'hevc', 'tags': {'BPS': '27139467'}},
                        {'codec_type': 'audio', 'codec_name': 'truehd', 'tags': {'BPS': '2780031'}}]}
    summary = source_summary(info)
    assert 'HEVC · 27139 kb/s' in summary and 'TRUEHD · 2780 kb/s' in summary
