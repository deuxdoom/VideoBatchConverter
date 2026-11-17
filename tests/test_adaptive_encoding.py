from pathlib import Path
import subprocess

import pytest
from PyQt6.QtCore import QAbstractAnimation
from PyQt6.QtTest import QTest

from src.profiles import PRESETS, adaptive_quality_value
from src.worker import FileConversionTask, QueueScanWorker, WorkerSignals, get_media_info, get_ffmpeg_path, process_options


@pytest.mark.parametrize('height,expected', [(2160, '23'), (1080, '21'), (720, '20'), (360, '18')])
def test_archive_adapts_quality_to_original_resolution(height, expected):
    assert adaptive_quality_value(PRESETS['아카이빙'], height) == expected
    assert PRESETS['아카이빙']['resolution'] == '원본 유지'


def test_three_presets_and_user_names_at_end(window, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog
    assert [window.preset_combo.itemText(index) for index in range(3)] == ['아카이빙', '1080p', '720p']
    assert window.preset_combo.count() == 3
    monkeypatch.setattr(QInputDialog, 'getText', lambda *args, **kwargs: ('직접 만든 보관', True))
    window.save_user_preset()
    assert window.preset_combo.itemText(window.preset_combo.count() - 1) == '직접 만든 보관'
    assert window.adaptive_quality_check.isChecked()
    assert not window.quality_edit.isEnabled()
    window.adaptive_quality_check.setChecked(False)
    assert window.quality_edit.isEnabled()


@pytest.mark.parametrize('name,maximum', [('1080p', 1080), ('720p', 720)])
def test_playback_presets_are_h264_aac_and_do_not_upscale(tmp_path, name, maximum):
    settings = dict(PRESETS[name], suffix='_test')
    task = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals(),
                              {'streams': [{'codec_type': 'video', 'height': 360, 'width': 640, 'bit_rate': '2000000'}]})
    command = task.build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mp4')
    assert command[command.index('-c:v') + 1] == 'h264_nvenc'
    assert command[command.index('-b:v') + 1] == '1600k'
    assert f'min(ih\\,{maximum})' in command[command.index('-vf') + 1]
    assert command[command.index('-pix_fmt') + 1] == 'yuv420p'
    assert command[command.index('-c:a') + 1] == 'aac'
    assert command[command.index('-multipass') + 1] == 'fullres'


def test_hdr_archive_preserves_10bit_and_playback_tonemaps(tmp_path):
    metadata = {'streams': [{'codec_type': 'video', 'height': 2160, 'width': 3840,
                              'pix_fmt': 'yuv420p10le', 'color_transfer': 'smpte2084', 'bit_rate': '10000000'}]}
    archive = FileConversionTask(tmp_path / 'hdr.mkv', dict(PRESETS['아카이빙'], suffix='_hdr'), WorkerSignals(), metadata)
    command = archive.build_ffmpeg_command('ffmpeg', 'hdr.mkv', 'out.mkv')
    assert command[command.index('-pix_fmt') + 1] == 'p010le'
    assert command[command.index('-color_trc') + 1] == 'smpte2084'
    assert '-vf' not in command
    compatible = FileConversionTask(tmp_path / 'hdr.mkv', dict(PRESETS['1080p'], suffix='_sdr'), WorkerSignals(), metadata)
    command = compatible.build_ffmpeg_command('ffmpeg', 'hdr.mkv', 'out.mp4')
    assert 'tonemap=mobius' in command[command.index('-vf') + 1]
    assert command[command.index('-color_trc') + 1] == 'bt709'


def test_archive_discards_larger_results_and_preserves_original(sample_video):
    settings = dict(PRESETS['아카이빙'], codec='AVC (H.264) - CPU', rate_control='CRF',
                    quality_value='0', adaptive_quality=False, suffix='_lossless_large')
    before = sample_video.read_bytes()
    task = FileConversionTask(sample_video, settings, WorkerSignals())
    outcomes = []
    task.signals.finished.connect(lambda task, outcome: outcomes.append(outcome))
    task.run()
    assert outcomes == ['kept']
    assert task.output_size >= task.input_size
    assert not task.output_file.exists()
    assert not task.partial_file.exists()
    assert sample_video.read_bytes() == before


def test_scan_accepts_non_h264_video_and_skips_folder_results(sample_video):
    source = sample_video.parent / 'mpeg4-source.avi'
    subprocess.run([get_ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-i', str(sample_video),
                    '-an', '-c:v', 'mpeg4', str(source)], check=True, timeout=15, **process_options())
    scanner = QueueScanWorker([source])
    found = []
    scanner.found.connect(lambda path, info: found.append((path, info)))
    scanner.run()
    assert len(found) == 1
    assert found[0][1]['streams'][0]['codec_name'] == 'mpeg4'


def test_animated_footer_uses_actual_values_and_stops_when_idle(window, app):
    bar = window.overall_progress_bar
    bar.setActive(True)
    bar.setValue(65)
    assert bar.value() == 65
    assert bar.animation.state() == QAbstractAnimation.State.Running
    QTest.qWait(320)
    app.processEvents()
    assert bar.displayedProgress == pytest.approx(65)
    assert window.progress_percent_label.text() == '65%'
    bar.setActive(False)
    assert not bar.timer.isActive()
    assert window.queue_panel.geometry().bottom() < window.overall_progress_bar.parentWidget().geometry().bottom()
