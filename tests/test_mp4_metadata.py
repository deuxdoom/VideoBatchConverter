"""Declared AAC maxRate regression: 162000 b/s, not a packet-duration spike."""

from src.mp4_metadata import aac_maximum_bitrate
from src.media_summary import source_summary


def box(kind, payload):
    return (len(payload) + 8).to_bytes(4, 'big') + kind + payload


def track(identifier, maximum):
    config = bytes([0x40, 0x15, 0, 0, 0]) + maximum.to_bytes(4, 'big') + (119785).to_bytes(4, 'big')
    decoder = bytes([4, len(config)]) + config
    es = b'\x00\x02\x00' + decoder
    esds = box(b'esds', b'\x00' * 4 + bytes([3, len(es)]) + es)
    entry = box(b'mp4a', b'\x00' * 28 + esds)
    stsd = box(b'stsd', b'\x00' * 4 + (1).to_bytes(4, 'big') + entry)
    mdia = box(b'mdia', box(b'hdlr', b'\x00' * 8 + b'soun') + box(b'minf', box(b'stbl', stsd)))
    tkhd = box(b'tkhd', b'\x00' * 12 + identifier.to_bytes(4, 'big') + b'\x00' * 8)
    return box(b'trak', tkhd + mdia)


def test_declared_maximum_uses_correct_audio_track_and_ignores_packet_spikes(tmp_path):
    source = tmp_path / 'metadata.mp4'
    source.write_bytes(box(b'ftyp', b'isom') + box(b'mdat', b'esds decoy media bytes') + box(b'moov', track(1, 320000) + track(2, 162000)))
    assert aac_maximum_bitrate(source, '0x2') == 162000
    assert aac_maximum_bitrate(source, '0x1') == 320000
    info = {'streams': [{'codec_type': 'audio', 'codec_name': 'aac', 'profile': 'LC',
                         'bit_rate': '119785', 'max_bit_rate': 162000, 'packet_peak_bit_rate': 1219000}]}
    text = source_summary(info)
    assert '평균 120 kb/s · 최대 162 kb/s' in text
    assert '1219' not in text


def test_extended_atom_size_tail_moov_and_missing_metadata_are_safe(tmp_path):
    source = tmp_path / 'extended.mp4'
    source.write_bytes((1).to_bytes(4, 'big') + b'mdat' + (32).to_bytes(8, 'big') + b'x' * 16
                       + box(b'moov', track(2, 162000)))
    assert aac_maximum_bitrate(source, '0x2') == 162000
    assert aac_maximum_bitrate(source, '0x3') is None
    assert aac_maximum_bitrate(source, '0x2', lambda: True) is None
    source.write_bytes(b'\xff\xff\xff\xffmoovtruncated')
    assert aac_maximum_bitrate(source) is None
