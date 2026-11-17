# src/settings.py
import os
import json
import logging
import sys
from pathlib import Path
from PyQt6.QtCore import QSettings, QCoreApplication
from .profiles import PRESETS, LEGACY_PRESETS, PRESET_KEYS, is_valid_user_preset
from .bitrate import BITRATE_UNIT, normalize_bitrate_settings

def get_settings_path():
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    return str(base / 'settings.ini')

class SettingsManager:
    def __init__(self):
        self.settings = QSettings(get_settings_path(), QSettings.Format.IniFormat)
        # Migrate the previous source-run location once, without writing beside Python.
        legacy_path = os.path.join(QCoreApplication.applicationDirPath(), 'settings.ini')
        if not Path(get_settings_path()).exists() and Path(legacy_path).is_file():
            legacy = QSettings(legacy_path, QSettings.Format.IniFormat)
            for key in legacy.allKeys():
                self.settings.setValue(key, legacy.value(key))

    def save_settings(self, settings_dict):
        for key, value in settings_dict.items():
            self.settings.setValue(key, value)
        self.settings.sync()

    def load_user_presets(self):
        try:
            values = json.loads(self.settings.value('user_presets', '{}', type=str))
            if not isinstance(values, dict):
                return {}
            for name, preset in values.items():
                if isinstance(preset, dict):
                    preset.setdefault('adaptive_quality', False)
                    preset.setdefault('keep_smaller', False)
                    values[name] = normalize_bitrate_settings(preset, legacy=preset.get('bitrate_unit') != BITRATE_UNIT)
            return {name: {key: preset[key] for key in PRESET_KEYS}
                    for name, preset in values.items() if isinstance(name, str) and name.strip() == name
                    and 0 < len(name) <= 60 and not any(ord(character) < 32 for character in name)
                    and name not in PRESETS and is_valid_user_preset(preset)}
        except (ValueError, TypeError):
            logging.warning('저장된 사용자 프리셋을 읽지 못했습니다.')
            return {}

    def save_user_presets(self, presets):
        previous = self.settings.value('user_presets', '{}', type=str)
        self.settings.setValue('user_presets', json.dumps(presets, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            self.settings.setValue('user_presets', previous)
            raise OSError('설정 파일을 저장할 수 없습니다. 프로그램 폴더의 쓰기 권한을 확인해 주세요.')

    def load_settings(self):
        values = {
            "language": self.settings.value("language", "ko", type=str),
            "completion_sound": self.settings.value("completion_sound", True, type=bool),
            "estimate_size": self.settings.value("estimate_size", True, type=bool),
            "gpu_processing": self.settings.value("gpu_processing", True, type=bool),
            "preset": self.settings.value("preset", "아카이빙", type=str),
            "preset_kind": self.settings.value("preset_kind", "builtin", type=str),
            "input_folder": self.settings.value("input_folder", "", type=str),
            "suffix": self.settings.value("suffix", "_archive", type=str),
            "codec": self.settings.value("codec", "H.265 (HEVC) - GPU", type=str),
            "resolution": self.settings.value("resolution", "원본 유지", type=str),
            "preset_option": self.settings.value("preset_option", "p6", type=str),
            "rate_control": self.settings.value("rate_control", "VBR", type=str),
            "quality_value": self.settings.value("quality_value", "8000", type=str),
            "bitrate_unit": self.settings.value("bitrate_unit", BITRATE_UNIT if not self.settings.contains('rate_control') else '', type=str),
            "source_bitrate_percent": self.settings.value('source_bitrate_percent', 80, type=int),
            "audio_option": self.settings.value("audio_option", "원본 유지 (Passthrough)", type=str),
            "output_format": self.settings.value("output_format", "mp4", type=str),
            "parallel_jobs": self.settings.value("parallel_jobs", 2, type=int),
            "adaptive_quality": self.settings.value("adaptive_quality", not self.settings.contains('codec'), type=bool),
            "keep_smaller": self.settings.value("keep_smaller", not self.settings.contains('codec'), type=bool),
            "geometry": self.settings.value("geometry"),
            "windowState": self.settings.value("windowState"),
        }
        legacy_names = {
            '일반용 / 아카이빙 (균형)': '아카이빙', 'Apple 기기 호환 (AV1)': '1080p',
            'Android 기기 호환 (VP9)': '1080p', 'YouTube 업로드 (1080p)': '1080p',
            'YouTube 업로드 (720p)': '720p',
        }
        if values['preset_kind'] == 'builtin' and values['preset'] in legacy_names:
            name = legacy_names[values['preset']]
            values.update(PRESETS[name])
            values['preset'] = name
        # Upgrade only the former built-in defaults. Named/user presets and
        # manually changed settings must keep their chosen container.
        old_archive = dict(PRESETS['아카이빙'], output_format='mkv')
        if (values['preset_kind'] == 'builtin' and values['preset'] == '아카이빙' and
                all(values.get(key) == value for key, value in old_archive.items())):
            values['output_format'] = PRESETS['아카이빙']['output_format']
        name = values.get('preset')
        if values['preset_kind'] == 'builtin' and name in LEGACY_PRESETS:
            old = LEGACY_PRESETS[name]
            if (all(values.get(key) == value for key, value in old.items() if key != 'output_format') and
                    (values['output_format'] == old['output_format'] or name == '아카이빙' and values['output_format'] == 'mkv')):
                values.update(PRESETS[name])
        return normalize_bitrate_settings(values, legacy=values.get('bitrate_unit') != BITRATE_UNIT)
