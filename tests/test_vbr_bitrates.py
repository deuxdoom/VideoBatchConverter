"""Source-relative VBR, unambiguous units, migration and actual AAC packet peaks."""

import json
import subprocess

import pytest

from src.bitrate import BITRATE_UNIT, normalize_bitrate_settings, target_bitrate_kbps
from src.i18n import language_manager, tr
from src.media_summary import source_summary
from src.profiles import LEGACY_PRESETS, PRESETS, PRESET_KEYS, validate_settings
from src.settings import SettingsManager
from src.size_estimator import estimate_key
from src.worker import FileConversionTask, QueueScanWorker, WorkerSignals, analyze_stream_bitrates, get_ffmpeg_path, get_media_info, process_options


def metadata(rate='10000000'):
    return {'streams': [{'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'bit_rate': rate,
                         'width': 1920, 'height': 1080, 'pix_fmt': 'yuv420p'}],
            'format': {'duration': '10', 'bit_rate': '30000000', 'size': '40000000'}}


def test_defaults_are_auto_vbr_at_80_percent(window):
    for settings in PRESETS.values():
        assert settings['rate_control'] == 'VBR' and settings['adaptive_quality']
        assert settings['bitrate_unit'] == BITRATE_UNIT
        assert target_bitrate_kbps(settings, metadata()) == 8000
        assert validate_settings(settings) is None
    window.add_scanned_file('F:/Temp/VideoBatchConverter/reference.mp4', metadata())
    window.file_list_widget.setCurrentRow(0)
    assert window.auto_bitrate_label.isVisible() and not window.quality_edit.isVisible()
    assert '8000 kb/s' in window.auto_bitrate_label.text()
    window.adaptive_quality_check.click()
    assert window.quality_edit.isVisible() and window.quality_edit.text() == '8000'
    assert 'kb/s' in window.quality_edit.accessibleName()


@pytest.mark.parametrize('codec', ['H.265 (HEVC) - GPU', 'AVC (H.264) - GPU', 'AVC (H.264) - CPU', 'H.265 (HEVC) - CPU'])
def test_actual_command_targets_video_bitrate_not_overall(tmp_path, codec):
    settings = dict(PRESETS['아카이빙'], codec=codec)
    task = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals(), metadata())
    command = task.build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mp4')
    assert command[command.index('-b:v') + 1] == '8000k'
    assert command[command.index('-maxrate') + 1] == '10000k'
    assert command[command.index('-bufsize') + 1] == '20000k'
    assert '-cq' not in command and '-crf' not in command
    if 'CPU' in codec:
        assert command[command.index('-preset') + 1] == 'slow'
    else:
        assert command[command.index('-rc') + 1] == 'vbr'
    task.media_info['streams'][0]['bit_rate'] = '2000000'
    changed = task.build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mp4')
    assert changed[changed.index('-b:v') + 1] == '1600k'


@pytest.mark.parametrize('value', ['6000', '192', '1500.5'])
def test_bare_numbers_mean_kbps_and_manual_mode_ignores_source(value, tmp_path):
    settings = dict(PRESETS['아카이빙'], adaptive_quality=False, quality_value=value)
    command = FileConversionTask(tmp_path / 'in', settings, WorkerSignals(), metadata()).build_ffmpeg_command('ffmpeg', 'in', 'out')
    assert command[command.index('-b:v') + 1] == value + 'k'


@pytest.mark.parametrize('value', ['6M', '192k', '0', '-1', 'NaN', '²'])
def test_new_bitrate_input_rejects_units_and_invalid_numbers(value):
    assert validate_settings(dict(PRESETS['아카이빙'], quality_value=value, adaptive_quality=False))


@pytest.mark.parametrize('old,expected', [('6M', '6000'), ('192k', '192'), ('7500000', '7500'), ('6000', '6')])
def test_legacy_ffmpeg_units_migrate_without_changing_their_actual_rate(old, expected):
    values = normalize_bitrate_settings({'rate_control': 'VBR', 'quality_value': old}, legacy=True)
    assert values['quality_value'] == expected and values['bitrate_unit'] == BITRATE_UNIT
    assert normalize_bitrate_settings(values)['quality_value'] == expected


def test_builtin_migration_preserves_custom_and_named_quality_profiles(window):
    manager = window.settings_manager
    manager.save_settings(dict(LEGACY_PRESETS['아카이빙'], preset='아카이빙', preset_kind='builtin'))
    restored = manager.load_settings()
    assert {key: restored[key] for key in PRESET_KEYS} == PRESETS['아카이빙']
    manager.save_settings(dict(LEGACY_PRESETS['아카이빙'], quality_value='40', preset='사용자 정의', preset_kind=''))
    restored = manager.load_settings()
    assert restored['rate_control'] == 'CQP' and restored['quality_value'] == '40'
    manager.settings.setValue('user_presets', json.dumps({'옛 VBR': dict(LEGACY_PRESETS['아카이빙'], rate_control='VBR', quality_value='7.5M', adaptive_quality=False),
                                                        '옛 CQP': LEGACY_PRESETS['아카이빙']}))
    profiles = manager.load_user_presets()
    assert profiles['옛 VBR']['quality_value'] == '7500'
    assert profiles['옛 CQP']['rate_control'] == 'CQP' and profiles['옛 CQP']['quality_value'] == '21'


def test_auto_bitrate_never_substitutes_overall_bitrate():
    info = metadata('N/A')
    with pytest.raises(ValueError, match='원본 비디오 비트레이트'):
        target_bitrate_kbps(PRESETS['아카이빙'], info)
    info['streams'][0]['tags'] = {'BPS': '4000000'}
    assert target_bitrate_kbps(PRESETS['아카이빙'], info) == 3200


def test_actual_aac_lc_vbr_scan_uses_declared_maximum_without_packet_peak(app, tmp_path):
    source = tmp_path / 'aac-vbr.mp4'
    subprocess.run([get_ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=96x64:rate=12', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                    '-t', '2', '-c:v', 'libx264', '-c:a', 'aac', '-profile:a', 'aac_low', '-q:a', '3', str(source)],
                    check=True, timeout=20, **process_options())
    scanner = QueueScanWorker([source])
    found = []
    scanner.found.connect(lambda path, info: found.append(info))
    scanner.run()
    audio = next(s for s in found[0]['streams'] if s['codec_type'] == 'audio')
    assert audio['profile'] == 'LC'
    assert 'packet_peak_bit_rate' not in audio
    assert int(audio['bit_rate']) > 0
    summary = source_summary(found[0])
    assert 'AAC LC · 평균' in summary and '최대' in summary and '패킷' not in summary
    try:
        language_manager().set_language('en')
        translated = tr(summary)
        assert 'Avg ' in translated and 'Max ' in translated and '평균' not in translated
    finally:
        language_manager().set_language('ko')
    untouched = metadata('N/A')
    analyze_stream_bitrates(source, untouched, lambda: True)
    assert untouched['streams'][0]['bit_rate'] == 'N/A'


def test_aac_missing_peak_is_explicit_not_invented():
    info = metadata()
    info['streams'].append({'codec_type': 'audio', 'codec_name': 'aac', 'profile': 'LC', 'bit_rate': '128000'})
    assert '평균 128 kb/s · 최대 —' in source_summary(info)
    info['streams'][-1]['max_bit_rate'] = '256000'
    assert '최대 256 kb/s' in source_summary(info)


def test_ratio_and_manual_are_separate_modes_with_editable_percentage(window, app):
    window.add_scanned_file('F:/Temp/VideoBatchConverter/ratio.mp4', metadata())
    window.file_list_widget.setCurrentRow(0)
    assert window.bitrate_mode_combo.currentData() == '원본 대비 (%)'
    assert window.source_bitrate_percent_spinbox.isVisible() and not window.quality_edit.isVisible()
    window.source_bitrate_percent_spinbox.setValue(50)
    assert window.get_current_settings()['source_bitrate_percent'] == 50
    assert '5000 kb/s' in window.auto_bitrate_label.text()
    window.select_value(window.bitrate_mode_combo, '직접 입력 (kb/s)')
    assert not window.adaptive_quality_check.isChecked()
    assert window.quality_edit.isVisible() and not window.source_bitrate_percent_spinbox.isVisible()
    window.quality_edit.setText('6000')
    assert target_bitrate_kbps(window.get_current_settings(), metadata()) == 6000
    window.save_app_settings()
    window.apply_preset('720p')
    window.load_app_settings()
    assert window.bitrate_mode_combo.currentData() == '직접 입력 (kb/s)'
    assert window.quality_edit.text() == '6000' and window.source_bitrate_percent_spinbox.value() == 50
    window.select_value(window.bitrate_mode_combo, '원본 대비 (%)')
    assert window.adaptive_quality_check.isChecked()
    assert target_bitrate_kbps(window.get_current_settings(), metadata()) == 5000
    window.select_value(window.bitrate_mode_combo, '직접 입력 (kb/s)')
    assert window.quality_edit.text() == '6000'


def test_percentage_changes_cache_only_for_relative_vbr(sample_video):
    first = dict(PRESETS['아카이빙'], source_bitrate_percent=80)
    second = dict(first, source_bitrate_percent=50)
    assert estimate_key(sample_video, first) != estimate_key(sample_video, second)
    assert estimate_key(sample_video, dict(first, adaptive_quality=False)) == estimate_key(sample_video, dict(second, adaptive_quality=False))
    for percent in (0, 201, '80'):
        assert validate_settings(dict(first, source_bitrate_percent=percent))
