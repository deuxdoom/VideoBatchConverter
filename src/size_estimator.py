"""Cancellable sampled encodes, before committing to a long full-size batch."""

import hashlib
import json
import logging
from pathlib import Path
import subprocess
import tempfile
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .media_summary import number
from .bitrate import source_video_bitrate
from .profiles import validate_media_settings, EncodingCompatibilityError
from .packet_metrics import PacketStats
from .worker import FileConversionTask, WorkerSignals, cuda_failure, get_ffmpeg_path, get_media_info, process_options, video_stream


def sample_ranges(duration):
    if duration <= 0:
        return []
    if duration <= 12:
        return [(0.0, duration)]
    length = 4.0
    return [(min(max(0.0, duration * position - length / 2), duration - length), length)
            for position in (.1, .5, .9)]


ESTIMATE_SETTING_KEYS = ('codec', 'resolution', 'preset_option', 'rate_control', 'quality_value',
                         'audio_option', 'output_format', 'adaptive_quality', 'gpu_processing', 'bitrate_unit', 'source_bitrate_percent')


def estimate_key(path, settings):
    stat = Path(path).stat()
    values = {key: settings.get(key) for key in ESTIMATE_SETTING_KEYS}
    if settings.get('rate_control') != 'VBR' or not settings.get('adaptive_quality'):
        values['source_bitrate_percent'] = None
    payload = [str(Path(path).resolve()), stat.st_size, stat.st_mtime_ns, values, 6]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class SizeEstimateWorker(QThread):
    progress = pyqtSignal(str, dict, int, int)
    warning = pyqtSignal(dict)

    def __init__(self, jobs, settings, cache=None, parent=None, temp_root=None, skip_existing=True):
        super().__init__(parent)
        self.jobs = jobs
        self.settings = dict(settings)
        self.cache = dict(cache or {})
        self.results = []
        self.process = None
        self._lock = threading.Lock()
        self.cancel_requested = threading.Event()
        self.pause_on_warning = False
        self._decision_ready = threading.Event()
        self.decision = None
        self.warning_acknowledged = False
        self.temp_root = temp_root
        self.skip_existing = skip_existing
        self.last_stderr = ''

    def is_cancelled(self):
        return self.cancel_requested.is_set() or self.isInterruptionRequested()

    def cancel(self):
        self.cancel_requested.set()
        self._decision_ready.set()
        self.requestInterruption()
        with self._lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    pass

    def respond(self, decision):
        self.decision = decision
        if decision in ('adjust', 'cancel'):
            self.cancel()
        self._decision_ready.set()

    def capture(self, command, timeout=90):
        if self.is_cancelled():
            raise InterruptedError()
        with self._lock:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding='utf-8', errors='replace', **process_options())
        deadline = time.monotonic() + timeout
        try:
            while True:
                if self.is_cancelled():
                    self.cancel()
                try:
                    output, error = self.process.communicate(timeout=.15)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() > deadline:
                        self.process.kill()
                        self.process.communicate()
                        raise TimeoutError('샘플 인코딩 시간이 초과되었습니다.')
            if self.is_cancelled():
                raise InterruptedError()
            self.last_stderr = error
            return self.process.returncode, output if self.process.returncode == 0 else output + '\n' + error
        finally:
            with self._lock:
                if self.process and self.process.poll() is None:
                    self.process.kill()
                    self.process.communicate()
                self.process = None

    def run(self):
        # Runtime samples belong in an isolated system temp directory, not beside
        # the original videos. Tests can supply the requested workspace temp root.
        with tempfile.TemporaryDirectory(prefix='VideoBatchConverter-estimate-', dir=self.temp_root) as work:
            for index, (path, info) in enumerate(self.jobs):
                if self.is_cancelled():
                    break
                result = {'path': path, 'state': 'unknown'}
                try:
                    key = estimate_key(path, self.settings)
                    output = Path(path).with_name(Path(path).stem + self.settings['suffix'] + '.' + self.settings['output_format'])
                    if self.skip_existing and output.exists():
                        result.update(state='existing', key=key)
                    elif (key in self.cache and self.cache[key].get('state') in ('safe', 'risk')
                          and number(self.cache[key].get('estimated_bytes'))):
                        result = dict(self.cache[key], path=path, cached=True)
                    else:
                        self.progress.emit(path, {'state': 'working'}, index, len(self.jobs))
                        info = info or get_media_info(path) or {}
                        compatibility_error = validate_media_settings(self.settings, info)
                        if compatibility_error:
                            result.update(source_bytes=Path(path).stat().st_size, info=info)
                            raise EncodingCompatibilityError(compatibility_error)
                        if self.settings.get('adaptive_quality') and self.settings['rate_control'] == 'VBR' and not source_video_bitrate(info):
                            from .worker import analyze_stream_bitrates
                            analyze_stream_bitrates(path, info, self.is_cancelled)
                        duration = number(info.get('format', {}).get('duration'))
                        source_bytes = Path(path).stat().st_size
                        result.update(source_bytes=source_bytes, info=info)
                        ranges = sample_ranges(duration)
                        if not ranges or not source_bytes:
                            raise ValueError('재생 시간 또는 원본 크기를 읽지 못했습니다.')
                        rates = []
                        actual_bytes = 0
                        encode_seconds = 0.0
                        task = FileConversionTask(path, self.settings, WorkerSignals(), info)
                        used_cuda = None
                        for sample_index, (start, length) in enumerate(ranges):
                            sample = Path(work) / f'{index}-{sample_index}.{self.settings["output_format"]}'
                            command = task.build_ffmpeg_command(get_ffmpeg_path(), path, sample, gpu_pipeline=used_cuda)
                            input_index = command.index('-i')
                            command[input_index:input_index] = ['-ss', str(start)]
                            # Input seeking is fast, but copied audio can contain
                            # packets preceding the seek point. MP4 edit lists and
                            # MKV timestamp shifts expose that preroll differently.
                            command[-1:-1] = ['-ss', '0', '-t', str(length)]
                            started = time.perf_counter()
                            code, message = self.capture(command)
                            if code and '-hwaccel' in command and cuda_failure(message):
                                sample.unlink(missing_ok=True)
                                used_cuda = False
                                command = task.build_ffmpeg_command(get_ffmpeg_path(), path, sample, gpu_pipeline=False)
                                input_index = command.index('-i')
                                command[input_index:input_index] = ['-ss', str(start)]
                                command[-1:-1] = ['-ss', '0', '-t', str(length)]
                                started = time.perf_counter()
                                code, message = self.capture(command)
                            if code:
                                raise RuntimeError(message.strip()[-1800:])
                            encode_seconds += time.perf_counter() - started
                            sample_info = get_media_info(sample) or {}
                            # Exclude repeated sample container headers before extrapolating.
                            code, packets = self.capture([get_ffmpeg_path('ffprobe'), '-v', 'error', '-show_packets',
                                '-show_entries', 'packet=stream_index,size,pts_time,dts_time,duration_time', '-of', 'json', str(sample)], timeout=20)
                            if code:
                                raise RuntimeError(packets[-800:])
                            try:
                                packet_info = json.loads(packets)
                            except ValueError:
                                raise RuntimeError('샘플 패킷 정보를 읽지 못했습니다. ' + (self.last_stderr or packets)[-800:]) from None
                            payload = sum(int(packet['size']) for packet in packet_info.get('packets', []))
                            if not payload:
                                raise ValueError('샘플 크기를 계산하지 못했습니다.')
                            video = video_stream(sample_info)
                            stats = PacketStats()
                            for packet in packet_info.get('packets', []):
                                if packet.get('stream_index') == video.get('index'):
                                    stats.add(packet)
                            seconds = stats.duration(number(video.get('duration')))
                            if not seconds:
                                raise ValueError('샘플의 재생 시간을 읽지 못했습니다.')
                            rates.append(payload / seconds)
                            actual_bytes = sample.stat().st_size
                        estimated = actual_bytes if len(ranges) == 1 else round(sum(rates) / len(rates) * duration * 1.01 + 65536)
                        result.update(key=key, source_bytes=source_bytes, estimated_bytes=estimated, duration=duration,
                                      estimated_seconds=encode_seconds / sum(length for _, length in ranges) * duration,
                                      sample_seconds=sum(length for _, length in ranges), quality=task.applied_quality,
                                      info=info, state='risk' if estimated >= source_bytes * .95 else 'safe')
                except InterruptedError:
                    break
                except EncodingCompatibilityError as exc:
                    result.update(state='blocked', error=str(exc))
                except Exception as exc:
                    if self.is_cancelled():
                        break
                    result['error'] = str(exc)
                    logging.exception('샘플 예측 실패: %s', path)
                if result.get('key') and result['state'] in ('safe', 'risk'):
                    self.cache[result['key']] = dict(result)
                self.results.append(result)
                self.progress.emit(path, result, index + 1, len(self.jobs))
                if (self.pause_on_warning and not self.warning_acknowledged and
                        result['state'] in ('risk', 'unknown', 'blocked') and not self.is_cancelled()):
                    # Warn on the first problem, before sampling the rest of a
                    # large queue. No further GPU/CPU work while awaiting input.
                    self.warning.emit(result)
                    while not self.is_cancelled() and not self._decision_ready.wait(.1):
                        pass
                    if self.is_cancelled():
                        break
                    self.warning_acknowledged = True
