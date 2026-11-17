"""Shared preset values and validation for the UI and conversion worker."""

import re
from .bitrate import BITRATE_UNIT

APP_VERSION = "3.0.0"
LEGACY_PRESETS = {
    "아카이빙": {"codec": "H.265 (HEVC) - GPU", "resolution": "원본 유지", "preset_option": "p6", "rate_control": "CQP", "quality_value": "21", "audio_option": "원본 유지 (Passthrough)", "output_format": "mp4", "parallel_jobs": 2, "adaptive_quality": True, "keep_smaller": True, "suffix": "_archive"},
    "1080p": {"codec": "AVC (H.264) - GPU", "resolution": "1080p", "preset_option": "p6", "rate_control": "CQP", "quality_value": "19", "audio_option": "AAC 192kbps", "output_format": "mp4", "parallel_jobs": 2, "adaptive_quality": True, "keep_smaller": False, "suffix": "_1080p"},
    "720p": {"codec": "AVC (H.264) - GPU", "resolution": "720p", "preset_option": "p6", "rate_control": "CQP", "quality_value": "19", "audio_option": "AAC 192kbps", "output_format": "mp4", "parallel_jobs": 2, "adaptive_quality": True, "keep_smaller": False, "suffix": "_720p"},
}
PRESETS = {name: dict(values, rate_control='VBR', quality_value='8000', bitrate_unit=BITRATE_UNIT, source_bitrate_percent=80)
           for name, values in LEGACY_PRESETS.items()}
PRESET_DISPLAY = {
    "아카이빙": ("아카이빙", "원본 해상도 · HEVC MP4 · 원본 비트레이트의 80% · 작은 결과만 보관", "archive", "#187967"),
    "1080p": ("1080p", "최대 1080p · H.264/AAC MP4 · 범용 재생", "devices", "#7653B5"),
    "720p": ("720p", "최대 720p · H.264/AAC MP4 · 가벼운 재생", "video", "#4263EB"),
}
CODECS = ['H.265 (HEVC) - GPU', 'AV1 - GPU', 'AVC (H.264) - GPU',
          'H.265 (HEVC) - CPU', 'AV1 - CPU', 'VP9 - CPU', 'AVC (H.264) - CPU']
PRESET_KEYS = tuple(next(iter(PRESETS.values())))
BOOL_PRESET_KEYS = ('adaptive_quality', 'keep_smaller')


class EncodingCompatibilityError(ValueError):
    pass


def validate_media_settings(settings, info):
    audio = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'audio'), {})
    if (settings.get('output_format') == 'mp4' and 'Passthrough' in settings.get('audio_option', '')
            and audio.get('codec_name') in ('truehd', 'mlp')):
        return 'TrueHD 오디오의 MP4 원본 복사는 지원하지 않습니다. 오디오를 AAC로 바꾸거나 저장 형식을 MKV로 선택하세요.'
    return None
ENCODERS = {
    'H.265 (HEVC) - CPU': 'libx265', 'H.265 (HEVC) - GPU': 'hevc_nvenc',
    'AV1 - CPU': 'libaom-av1', 'AV1 - GPU': 'av1_nvenc', 'VP9 - CPU': 'libvpx-vp9',
    'AVC (H.264) - CPU': 'libx264', 'AVC (H.264) - GPU': 'h264_nvenc',
}
HELP_DETAILS = {
    "codec": "여러 입력 코덱의 영상을 선택한 출력 코덱으로 통일합니다. GPU는 NVIDIA NVENC를 사용하며 지원 여부는 GPU 세대와 드라이버에 따라 다릅니다. GPU를 사용할 수 없으면 CPU 코덱을 선택하세요.",
    "resolution": "원본 유지 또는 최대 1080p/720p로 축소합니다. 작은 영상은 확대하지 않고 원본 비율을 유지합니다.",
    "preset": "NVENC 속도와 압축 효율의 균형입니다. p1은 가장 빠르고, p7은 느리지만 압축 효율이 높습니다. CPU 코덱에서는 사용하지 않습니다.",
    "rate_control": "CQP/CRF는 일정한 화질을 목표로 합니다. 숫자가 낮으면 고품질·큰 용량입니다. VBR은 평균 비트레이트, CBR은 일정한 비트레이트를 목표로 합니다.",
    "quality_value": "VBR은 원본 대비 (%)와 직접 입력 (kb/s) 중 선택합니다. 비율 기본값은 80%이며 사용자가 수정하고 프리셋에 저장할 수 있습니다. 오디오와 컨테이너를 포함한 전체 비트레이트를 영상 값으로 사용하지 않습니다. 직접 입력에서 6000은 6000 kb/s입니다. CQP/CRF는 0~51 품질값을 사용합니다. 손실 압축이며 실제 용량·화질은 원본에 따라 달라집니다.",
    "suffix": "원본 파일명 뒤에 붙입니다. 예: 여행.mp4 → 여행_h265.mp4. 원본 보호를 위해 빈 접미사와 경로 문자는 사용할 수 없습니다.",
    "audio_option": "원본 유지는 첫 번째 오디오 트랙을 재압축 없이 복사합니다. 컨테이너가 오디오 형식을 지원하지 않으면 AAC를 선택하세요. 오디오가 없는 영상도 처리할 수 있습니다.",
    "output_format": "MP4는 범용 재생용, MKV는 유연한 보관용입니다. VP9는 오디오 호환성을 위해 MKV를 권장합니다. 변환 결과에는 첫 번째 영상·오디오 트랙만 포함됩니다.",
    "parallel_jobs": "동시 변환 개수입니다. GPU 메모리와 CPU 성능에 맞춰 조절하세요. 보통 1~2개로 시작하는 것이 좋습니다.",
}
HELP_TEXTS = {
    'codec': '출력 코덱 선택. GPU는 NVIDIA 전용입니다.',
    'resolution': '최대 높이를 제한합니다. 작은 영상은 확대하지 않습니다.',
    'preset': 'p1은 빠르게, p7은 더 작게 압축합니다.\nGPU 전용입니다.',
    'rate_control': 'CQP/CRF는 화질 기준, VBR/CBR은 비트레이트 기준입니다.',
    'quality_value': 'VBR 기본 목표는 원본 비디오의 80%입니다.\n수동 비트레이트 단위는 kb/s입니다.',
    'suffix': '원본 이름 뒤에 붙일 글자입니다. 예: _archive',
    'audio_option': '원본 복사 또는 AAC 변환.\nMP4에서 복사가 안 되면 AAC를 선택하세요.',
    'output_format': 'MP4는 범용 재생, MKV는 유연한 보관에 적합합니다.',
    'parallel_jobs': '동시에 변환할 개수입니다. 1~2개로 시작하세요.',
}


def validate_settings(settings):
    if settings.get('codec') not in ENCODERS:
        return "지원하는 비디오 코덱을 선택해 주세요."
    suffix = settings.get('suffix', '')
    if not suffix.strip() or re.search(r'[<>:"/\\|?*\x00-\x1f]', suffix) or suffix.endswith(('.', ' ')):
        return "파일 접미사를 입력해 주세요. 경로·예약 문자와 끝의 점/공백은 사용할 수 없습니다."
    quality = settings.get('quality_value', '').strip()
    percent = settings.get('source_bitrate_percent', 80)
    if type(percent) is not int or not 1 <= percent <= 200:
        return '원본 대비 비율은 1~200%로 입력하세요.'
    if settings.get('rate_control') in ('CQP', 'CRF'):
        if not re.fullmatch(r'[0-9]+', quality) or not 0 <= int(quality) <= 51:
            return "품질값은 0~51 사이의 정수로 입력해 주세요."
    elif not re.fullmatch(r'(?:[1-9][0-9]*(?:\.[0-9]+)?|0\.[0-9]*[1-9][0-9]*)', quality):
        return "비트레이트는 kb/s 단위의 양수로 입력하세요. 예: 6000"
    if settings.get('output_format') not in ('mp4', 'mkv'):
        return "출력 형식은 MP4 또는 MKV로 선택해 주세요."
    if settings.get('adaptive_quality') and settings.get('rate_control') not in ('CQP', 'CRF', 'VBR'):
        return "자동 조절은 VBR 또는 CQP/CRF 압축 방식에서 사용해 주세요."
    return None


def is_valid_user_preset(values):
    if not isinstance(values, dict) or not all(key in values for key in PRESET_KEYS):
        return False
    if any(not isinstance(values[key], str) for key in PRESET_KEYS if key not in ('parallel_jobs', 'source_bitrate_percent', *BOOL_PRESET_KEYS)):
        return False
    if any(type(values[key]) is not bool for key in BOOL_PRESET_KEYS):
        return False
    modes = ('CQP', 'CBR', 'VBR') if 'GPU' in values['codec'] else ('CRF', 'CBR', 'VBR')
    return (values['bitrate_unit'] == BITRATE_UNIT and values['codec'] in CODECS and values['resolution'] in ('원본 유지', '1080p', '720p')
            and values['preset_option'].split(' ')[0] in ('p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7')
            and values['rate_control'] in modes
            and values['audio_option'] in ('원본 유지 (Passthrough)', 'AAC 128kbps', 'AAC 192kbps', 'AAC 256kbps')
            and type(values['parallel_jobs']) is int and 1 <= values['parallel_jobs'] <= 32
            and validate_settings(values) is None)


def adaptive_quality_value(settings, height):
    """Conservative starting values; do not spend extra bits enlarging small inputs."""
    cap = {'1080p': 1080, '720p': 720}.get(settings['resolution'], height)
    effective = min(height, cap) if height > 0 else 1080
    gpu = 'GPU' in settings['codec']
    if 'H.264' in settings['codec']:
        return str((19 if effective >= 720 else 18) if gpu else (18 if effective >= 720 else 17))
    if effective >= 2160:
        return '23' if gpu else '22'
    if effective >= 1080:
        return '21' if gpu else '20'
    if effective >= 720:
        return '20' if gpu else '19'
    return '18'
