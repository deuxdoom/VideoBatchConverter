from pathlib import Path
import subprocess
import threading
import time

import pytest

from src.profiles import PRESETS, validate_settings
from src.worker import FileConversionTask, QueueScanWorker, WorkerSignals, get_media_info, get_ffmpeg_path


def options(**changes):
    values = dict(PRESETS[next(iter(PRESETS))], rate_control='CQP', quality_value='21', suffix='_test', adaptive_quality=False, keep_smaller=False)
    values.update(changes)
    return values


@pytest.mark.parametrize('codec', ['AVC (H.264) - CPU', 'H.265 (HEVC) - CPU', 'AV1 - CPU', 'VP9 - CPU'])
def test_real_cpu_conversions(sample_video, codec):
    settings = options()
    settings.update(codec=codec, rate_control='CRF', quality_value='32', resolution='1080p',
                    suffix='_' + codec.split()[0].replace('.', '').replace('(', ''), output_format='mkv')
    signals = WorkerSignals()
    results = []
    signals.finished.connect(lambda task, outcome: results.append(outcome))
    task = FileConversionTask(sample_video, settings, signals)
    task.run()
    assert results == ['done']
    assert task.output_file.suffix == '.mkv'
    info = get_media_info(task.output_file)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    assert (video['width'], video['height']) == (96, 64), 'Small inputs must not be upscaled'
    assert not task.partial_file.exists()
    assert sample_video.exists()


def test_existing_output_unchanged_and_partial_output_removed(sample_video):
    settings = options()
    settings.update(codec='AVC (H.264) - CPU', rate_control='CRF', suffix='_existing')
    task = FileConversionTask(sample_video, settings, WorkerSignals())
    task.output_file.write_bytes(b'existing result')
    task.run()
    assert task.output_file.read_bytes() == b'existing result'
    failed = FileConversionTask(sample_video, settings, WorkerSignals())
    failed.settings['codec'] = 'invalid codec'
    failed.output_file = sample_video.with_name('failed.mkv')
    failed.partial_file = sample_video.with_name('failed.partial.mkv')
    failed.partial_file.write_bytes(b'partial')
    failed.run()
    assert not failed.partial_file.exists()
    assert not failed.output_file.exists()


def test_scan_deduplicates_recursively(sample_video):
    worker = QueueScanWorker([sample_video.parent, sample_video, sample_video.parent])
    found = []
    worker.found.connect(lambda path, info: found.append(path))
    worker.run()
    assert str(sample_video.resolve()) in found
    assert len(found) == len(set(found))
    existing = QueueScanWorker([sample_video], found)
    again = []
    existing.found.connect(lambda *args: again.append(args))
    existing.run()
    assert not again


def test_invalid_settings_are_rejected():
    base = options()
    assert validate_settings(base) is None
    for suffix in ('', ' ', '../bad', 'bad\\name', 'bad:', 'bad.'):
        assert validate_settings(dict(base, suffix=suffix))
    for quality in ('-1', '52', '2.5', '6M'):
        assert validate_settings(dict(base, quality_value=quality))
    for quality in ('0', '-1M', 'M', 'nan'):
        assert validate_settings(dict(base, rate_control='VBR', quality_value=quality))
    assert validate_settings(dict(base, rate_control='VBR', quality_value='6000')) is None


def test_nvenc_and_vp9_rate_control_commands(tmp_path):
    settings = options()
    command = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals()).build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mkv')
    assert command[command.index('-rc') + 1] == 'vbr'
    assert command[command.index('-b:v') + 1] == '0'
    settings.update(codec='VP9 - CPU', rate_control='CRF')
    command = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals()).build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mkv')
    assert command[command.index('-b:v') + 1] == '0'
    assert command[command.index('-map') + 1] == '0:v:0'
    assert '-n' in command and '-y' not in command
