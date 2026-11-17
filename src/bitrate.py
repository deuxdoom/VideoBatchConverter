"""Explicit kb/s settings and a per-video source-relative VBR target."""

from decimal import Decimal, InvalidOperation
import re

from .media_summary import stream_bitrate

BITRATE_UNIT = 'kb/s'
SOURCE_BITRATE_PERCENT = 80


def normalize_bitrate_settings(values, *, legacy=False):
    values = dict(values)
    if values.get('rate_control') in ('VBR', 'CBR'):
        raw = str(values.get('quality_value', '')).strip()
        match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)([kKmM]?)', raw)
        if match:
            amount = Decimal(match[1])
            suffix = match[2].lower()
            if suffix == 'm':
                amount *= 1000
            elif not suffix and legacy:
                amount /= 1000
            values['quality_value'] = format(amount, 'f').rstrip('0').rstrip('.') if '.' in format(amount, 'f') else str(amount)
    values['bitrate_unit'] = BITRATE_UNIT
    values.setdefault('source_bitrate_percent', SOURCE_BITRATE_PERCENT)
    return values


def source_video_bitrate(info):
    stream = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'video'
                   and not s.get('disposition', {}).get('attached_pic')), {})
    return stream_bitrate(stream)


def target_bitrate_kbps(settings, info):
    if settings.get('adaptive_quality') and settings['rate_control'] == 'VBR':
        source = source_video_bitrate(info)
        if not source:
            raise ValueError('원본 비디오 비트레이트를 읽지 못했습니다. 직접 입력 (kb/s)을 선택해 목표값을 입력하세요.')
        percent = settings.get('source_bitrate_percent', SOURCE_BITRATE_PERCENT)
        if type(percent) is not int or not 1 <= percent <= 200:
            raise ValueError('원본 대비 비율은 1~200%로 입력하세요.')
        return max(1, round(source * percent / 100 / 1000))
    try:
        value = Decimal(str(settings['quality_value']))
        if not value.is_finite() or value <= 0:
            raise ValueError()
        return value
    except (InvalidOperation, ValueError):
        raise ValueError('비트레이트는 kb/s 단위의 양수로 입력하세요. 예: 6000') from None


def bitrate_argument(kbps):
    return f'{kbps}k'
