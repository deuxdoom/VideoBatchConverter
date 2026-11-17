"""Readable source metadata without assuming that every ffprobe field exists."""

import math


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def codec_name(stream):
    codec = str(stream.get('codec_name') or '—').lower()
    name = {'h264': 'H.264', 'hevc': 'HEVC', 'mpeg4': 'MPEG-4'}.get(codec, codec.upper())
    return name + ' LC' if codec == 'aac' and stream.get('profile') == 'LC' else name


def bitrate_text(value):
    bitrate = number(value)
    return f'{bitrate / 1000:.0f} kb/s' if bitrate else '—'


def stream_bitrate(stream):
    tags = {str(key).upper(): value for key, value in (stream.get('tags') or {}).items()}
    return number(stream.get('bit_rate')) or number(tags.get('BPS')) or number(tags.get('BPS-ENG'))


def audio_bitrate_text(stream):
    average = bitrate_text(stream_bitrate(stream))
    if stream.get('codec_name') != 'aac':
        return average
    maximum = number(stream.get('max_bit_rate')) or number(stream.get('tags', {}).get('MAX_BITRATE'))
    if maximum:
        return f'평균 {average} · 최대 {bitrate_text(maximum)}'
    return f'평균 {average} · 최대 —' if stream.get('profile') == 'LC' else average


def source_summary(info):
    info = info or {}
    video = next((stream for stream in info.get('streams', []) if stream.get('codec_type') == 'video'
                  and not stream.get('disposition', {}).get('attached_pic')), {})
    audio = next((stream for stream in info.get('streams', []) if stream.get('codec_type') == 'audio'), {})
    fmt = info.get('format', {})
    duration = number(fmt.get('duration')) or number(video.get('duration'))
    seconds = int(duration)
    length = (f'{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}' if seconds >= 3600
              else f'{seconds // 60}:{seconds % 60:02d}') if duration else '—'
    tracks = f'비디오 {codec_name(video)} · {bitrate_text(stream_bitrate(video))}'
    tracks += (f'  |  오디오 {codec_name(audio)} · {audio_bitrate_text(audio)}'
               if audio else '  |  오디오 없음')
    width, height = (int(number(video.get(key))) or '—' for key in ('width', 'height'))
    details = f'{length} · {width} × {height}'
    if not stream_bitrate(video) or (audio and not stream_bitrate(audio)):
        total = number(fmt.get('bit_rate'))
        if not total and duration:
            total = number(fmt.get('size')) * 8 / duration
        if total:
            details += f' · 전체 {bitrate_text(total)}'
    size = number(fmt.get('size'))
    details += f' · {size / 1048576:.1f} MB' if size else ' · —'
    return f'{tracks}\n{details}'
