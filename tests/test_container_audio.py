"""Container-independent sample timing and missing MKV audio averages."""

import json
import subprocess

import pytest

from src.media_summary import source_summary, stream_bitrate
from src.packet_metrics import PacketStats
from src.profiles import PRESETS
from src.size_estimator import SizeEstimateWorker
from src.worker import FileConversionTask, WorkerSignals, QueueScanWorker, get_ffmpeg_path, get_media_info, process_options


def test_packet_time_span_handles_reordered_negative_and_quantized_timestamps():
    stats = PacketStats()
    # Millisecond container precision must not turn 24 fps into 24.39 fps.
    for frame in [2, 0, 1, *range(3, 240)]:
        stats.add({'size': 1000, 'pts_time': round(frame / 24 - .083, 3), 'duration_time': '.041'})
    assert stats.duration() == pytest.approx(10, abs=.001)
    assert stats.bytes * 8 / stats.duration() == pytest.approx(192000, rel=.0002)


def test_missing_packet_timing_uses_complete_durations_or_explicit_fallback():
    stats = PacketStats()
    stats.add({'size': 200, 'duration_time': '.5', 'pts_time': 'N/A'})
    stats.add({'size': 200, 'duration_time': '.5'})
    assert stats.duration() == 1
    stats.add({'size': 200, 'duration_time': 'N/A', 'pts_time': 'NaN'})
    assert stats.duration(3) == 3


def test_audio_missing_bitrate_is_deferred_even_when_video_rate_is_known(app, tmp_path, monkeypatch):
    from src import worker
    source = tmp_path / 'missing-audio.mkv'
    source.write_bytes(b'fixture')
    info = {'streams': [{'index': 0, 'codec_type': 'video', 'bit_rate': '4000000'},
                        {'index': 1, 'codec_type': 'audio', 'codec_name': 'aac', 'profile': 'LC'}]}
    monkeypatch.setattr(worker, 'get_media_info', lambda *args: info)
    monkeypatch.setattr(worker, 'aac_maximum_bitrate', lambda *args: None)
    calls, details, found = [], [], []
    def analyze(path, data, cancelled):
        calls.append(path)
        data['streams'][1]['bit_rate'] = 128000
    monkeypatch.setattr(worker, 'analyze_stream_bitrates', analyze)
    scan = QueueScanWorker([source])
    scan.details.connect(lambda path, data: details.append(data))
    scan.found.connect(lambda path, data: found.append(data))
    scan.run()
    assert calls == [str(source.resolve())] and details[0]['_extra_pending']
    assert '평균 128 kb/s · 최대 —' in source_summary(found[0])


def test_actual_mkv_audio_without_header_bitrate_is_measured_in_same_pass(app, sample_video, tmp_path):
    source = tmp_path / 'untagged.mkv'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-i', str(sample_video), '-map', '0',
                    '-c', 'copy', '-map_metadata', '-1', str(source)], check=True, timeout=20, **process_options())
    before = get_media_info(source)
    assert not stream_bitrate(before['streams'][1])
    found = []
    scanner = QueueScanWorker([source])
    scanner.found.connect(lambda path, info: found.append(info))
    scanner.run()
    audio = found[0]['streams'][1]
    assert audio['bit_rate_source'] == 'packets' and audio['bit_rate'] > 0
    assert 'max_bit_rate' not in audio and 'packet_peak_bit_rate' not in audio
    assert '평균 —' not in source_summary(found[0])


def test_real_seek_samples_have_matching_video_frames_and_size_across_containers(app, tmp_path):
    source = tmp_path / 'long-gop.mkv'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=96x64:rate=24', '-f', 'lavfi', '-i', 'sine=sample_rate=48000',
                    '-t', '20', '-c:v', 'libx264', '-g', '240', '-c:a', 'aac', str(source)],
                   check=True, timeout=20, **process_options())
    results, observations = {}, {}
    for container in ('mp4', 'mkv'):
        settings = dict(PRESETS['아카이빙'], output_format=container, codec='AVC (H.264) - CPU',
                        rate_control='CRF', quality_value='23', adaptive_quality=False)
        worker = SizeEstimateWorker([(str(source), get_media_info(source))], settings, temp_root=tmp_path)
        capture = worker.capture
        samples = []
        def inspect(command, timeout=90):
            code, output = capture(command, timeout)
            if '-show_packets' in command and not code:
                info = get_media_info(command[-1])
                video = next(s for s in info['streams'] if s['codec_type'] == 'video')
                packets = json.loads(output)['packets']
                stats = PacketStats()
                for packet in packets:
                    if packet['stream_index'] == video['index']:
                        stats.add(packet)
                samples.append((stats.count, stats.bytes, stats.duration()))
            return code, output
        worker.capture = inspect
        worker.run()
        assert worker.results[0]['state'] in ('safe', 'risk'), worker.results
        results[container] = worker.results[0]['estimated_bytes']
        observations[container] = samples
    assert len(observations['mp4']) == len(observations['mkv']) == 3
    for mp4, mkv in zip(observations['mp4'], observations['mkv']):
        assert mp4[:2] == mkv[:2]  # Every encoded frame and video byte agrees.
        assert mp4[2] == pytest.approx(mkv[2], abs=.002)
    assert results['mp4'] == pytest.approx(results['mkv'], rel=.002)


def test_variable_frame_timestamps_survive_both_output_containers(app, tmp_path):
    source = tmp_path / 'vfr.mkv'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=96x64:rate=24:duration=2', '-vf', 'select=not(mod(n\\,3))',
                    '-fps_mode:v', 'vfr', '-c:v', 'libx264', str(source)],
                   check=True, timeout=20, **process_options())
    def positions(path):
        result = subprocess.run([get_ffmpeg_path('ffprobe'), '-v', 'error', '-select_streams', 'v:0',
                                 '-show_packets', '-show_entries', 'packet=pts_time', '-of', 'json', str(path)],
                                capture_output=True, text=True, check=True, timeout=20, **process_options())
        return sorted(float(p['pts_time']) for p in json.loads(result.stdout)['packets'])
    expected = positions(source)
    assert len(expected) == 16
    for container in ('mp4', 'mkv'):
        settings = dict(PRESETS['아카이빙'], output_format=container, codec='AVC (H.264) - CPU',
                        rate_control='CRF', quality_value='23', adaptive_quality=False, keep_smaller=False)
        task = FileConversionTask(source, settings, WorkerSignals(), get_media_info(source))
        task.run()
        actual = positions(task.output_file)
        assert len(actual) == len(expected)
        assert [p - actual[0] for p in actual] == pytest.approx([p - expected[0] for p in expected], abs=.002)
