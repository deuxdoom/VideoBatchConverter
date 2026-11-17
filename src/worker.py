"""FFmpeg tasks: cancellable jobs, explicit outcomes and atomic output files."""

import json
import logging
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy

from PyQt6.QtCore import QObject, QRunnable, QThread, pyqtSignal

from .profiles import APP_VERSION, ENCODERS, adaptive_quality_value, validate_media_settings, EncodingCompatibilityError
from .paths import ffmpeg_directory
from .bitrate import BITRATE_UNIT, normalize_bitrate_settings, target_bitrate_kbps, bitrate_argument, source_video_bitrate
from .media_summary import number, stream_bitrate
from .mp4_metadata import aac_maximum_bitrate
from .packet_metrics import PacketStats

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.ts', '.webm',
                    '.m2ts', '.mts', '.mpeg', '.mpg', '.vob', '.3gp', '.ogv', '.asf', '.mxf'}


def cuda_failure(message):
    return any(token in message.lower() for token in ('cuda', 'cuvid', 'nvdec', 'hwaccel', 'hardware frames', 'decoder surfaces'))


def video_stream(info):
    return next((stream for stream in (info or {}).get('streams', []) if stream.get('codec_type') == 'video'
                 and not stream.get('disposition', {}).get('attached_pic')), {})


def get_ffmpeg_path(tool='ffmpeg'):
    candidate = ffmpeg_directory() / f'{tool}.exe'
    return str(candidate) if candidate.is_file() else None


def process_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def missing_bitrate_streams(info):
    audio = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
    return [s for s in (video_stream(info), audio)
            if s and s.get('index') is not None and not stream_bitrate(s)]


def analyze_stream_bitrates(file_path, info, cancelled=lambda: False):
    """Read AAC maxima from headers; measure missing averages in one deferred pass."""
    audio = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), {})
    if audio.get('codec_name') == 'aac' and not cancelled():
        maximum = aac_maximum_bitrate(file_path, audio.get('id'), cancelled)
        if maximum:
            audio['max_bit_rate'] = maximum
            audio['max_bit_rate_source'] = 'container'
    streams = missing_bitrate_streams(info)
    if not streams or cancelled():
        return
    ffprobe = get_ffmpeg_path('ffprobe')
    if not ffprobe:
        return
    stats = {int(s['index']): PacketStats() for s in streams}
    finished = threading.Event()
    timed_out = threading.Event()
    process = None
    watcher = None
    try:
        process = subprocess.Popen([ffprobe, '-v', 'error', '-show_packets', '-show_entries',
            'packet=stream_index,size,pts_time,dts_time,duration_time', '-of', 'compact=p=0:nk=0', str(file_path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', **process_options())
        deadline = time.monotonic() + 60
        def watch():
            while not finished.wait(.05):
                if cancelled() or time.monotonic() >= deadline:
                    timed_out.set()
                    try:
                        process.terminate()
                    except OSError:
                        pass
                    return
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        for line in process.stdout:
            fields = dict(part.split('=', 1) for part in line.strip().split('|') if '=' in part)
            try:
                stat = stats.get(int(fields.get('stream_index', '-1')))
            except (TypeError, ValueError):
                continue
            if stat is not None:
                stat.add(fields)
        process.wait()
        if process.returncode or timed_out.is_set() or cancelled():
            return
        for stream in streams:
            stat = stats[int(stream['index'])]
            duration = stat.duration(number(stream.get('duration')) or number(info.get('format', {}).get('duration')))
            if stat.bytes and duration:
                stream['bit_rate'] = round(stat.bytes * 8 / duration)
                stream['bit_rate_source'] = 'packets'
    except (OSError, subprocess.SubprocessError):
        logging.warning('패킷 비트레이트를 분석하지 못했습니다: %s', file_path)
    finally:
        finished.set()
        if watcher:
            watcher.join()
        if process:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


def get_media_info(file_path, cancelled=None):
    ffprobe = get_ffmpeg_path('ffprobe')
    if not ffprobe:
        return None
    try:
        command = [ffprobe, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(file_path)]
        if cancelled is None:
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=20, check=True, **process_options())
            return json.loads(result.stdout)
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                              encoding='utf-8', errors='replace', **process_options()) as process:
            deadline = time.monotonic() + 20
            while True:
                if cancelled() or time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    return None
                try:
                    output, _ = process.communicate(timeout=.1)
                    return json.loads(output) if process.returncode == 0 else None
                except subprocess.TimeoutExpired:
                    pass
    except (OSError, subprocess.SubprocessError, ValueError):
        logging.warning('미디어 정보를 읽지 못했습니다: %s', file_path)
        return None


def get_video_codec(file_path):
    info = get_media_info(file_path)
    return next((s.get('codec_name') for s in info.get('streams', []) if s.get('codec_type') == 'video'), None) if info else None


def get_video_duration(file_path):
    info = get_media_info(file_path)
    try:
        return float(info.get('format', {}).get('duration', 0)) if info else 0.0
    except (ValueError, TypeError):
        return 0.0


class QueueScanWorker(QThread):
    queued = pyqtSignal(str, dict)
    analyzing = pyqtSignal(str, str)
    details = pyqtSignal(str, dict)
    rejected = pyqtSignal(str, str, bool)
    found = pyqtSignal(str, dict)
    status = pyqtSignal(str)
    summary = pyqtSignal(int, int)

    def __init__(self, paths, existing=(), parent=None, max_workers=4):
        super().__init__(parent)
        self.paths = [Path(path) for path in paths]
        self.existing = {os.path.normcase(os.path.abspath(path)) for path in existing}
        self.explicit = {os.path.normcase(os.path.abspath(path)) for path in self.paths if path.is_file()}
        self.max_workers = max(1, min(max_workers, os.cpu_count() or 1))
        self.cancel_requested = threading.Event()
        self.was_cancelled = False

    def is_cancelled(self):
        return self.cancel_requested.is_set() or self.isInterruptionRequested()

    def cancel(self):
        self.cancel_requested.set()
        self.requestInterruption()

    def _basic_info(self, path, _):
        info = get_media_info(path, self.is_cancelled)
        audio = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'audio'), {})
        if audio.get('codec_name') == 'aac':
            maximum = aac_maximum_bitrate(path, audio.get('id'), self.is_cancelled)
            if maximum:
                audio['max_bit_rate'] = maximum
                audio['max_bit_rate_source'] = 'container'
        return info

    def _extra_info(self, path, info):
        analyze_stream_bitrates(path, info, self.is_cancelled)
        return info

    def _parallel(self, jobs, callback, state):
        # Dispatch in queue order, keep only a bounded number of probes in flight.
        # Completion order never changes the already-created queue rows.
        iterator = iter(jobs)
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix='vbc-info') as pool:
            pending = {}
            def submit_next():
                job = next(iterator, None)
                if job is not None and not self.is_cancelled():
                    self.analyzing.emit(job[0], state)
                    pending[pool.submit(callback, *job)] = job
            for _ in range(self.max_workers):
                submit_next()
            while pending and not self.is_cancelled():
                done, _ = wait(pending, timeout=.05, return_when=FIRST_COMPLETED)
                for future in done:
                    path, _ = pending.pop(future)
                    try:
                        result = future.result()
                    except Exception:
                        logging.exception('파일 정보 분석 실패: %s', path)
                        result = None
                    if not self.is_cancelled():
                        yield path, result
                        submit_next()
            for future in pending:
                future.cancel()

    def run(self):
        added = skipped = 0
        jobs = []
        for candidate in self.candidates():
            if self.is_cancelled():
                break
            key = os.path.normcase(os.path.abspath(candidate))
            if key in self.existing or candidate.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            self.existing.add(key)
            path = str(candidate.resolve())
            try:
                size = candidate.stat().st_size
            except OSError:
                size = 0
            self.queued.emit(path, {'format': {'size': size}, '_scan_pending': True})
            jobs.append((path, None))
        extras = []
        for path, info in self._parallel(jobs, self._basic_info, '정보 분석 중'):
            video = video_stream(info)
            marker = (info or {}).get('format', {}).get('tags', {}).get('comment', '')
            generated = str(marker).startswith('VideoBatchConverter ') and os.path.normcase(path) not in self.explicit
            if video and not generated:
                needs_extra = bool(missing_bitrate_streams(info))
                snapshot = deepcopy(info)
                snapshot['_extra_pending'] = needs_extra
                self.details.emit(path, snapshot)
                if needs_extra:
                    extras.append((path, info))
                else:
                    self.found.emit(path, info)
                    added += 1
            else:
                self.rejected.emit(path, '앱이 만든 결과 파일입니다.' if generated else '파일 정보를 읽지 못했거나 영상 스트림이 없습니다.', generated)
                skipped += 1
        for path, info in self._parallel(extras, self._extra_info, '추가 분석 중'):
            if info:
                self.found.emit(path, info)
                added += 1
            else:
                self.rejected.emit(path, '파일 정보를 읽지 못했거나 영상 스트림이 없습니다.', False)
                skipped += 1
        self.was_cancelled = self.is_cancelled()
        self.summary.emit(added, skipped)

    def candidates(self):
        for path in self.paths:
            if self.is_cancelled():
                return
            if path.is_dir():
                for root, dirs, files in os.walk(path):
                    if self.is_cancelled():
                        return
                    dirs.sort()
                    for name in sorted(files):
                        if self.is_cancelled():
                            return
                        yield Path(root) / name
            elif path.is_file():
                yield path


class WorkerSignals(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(object, str)


class FileConversionTask(QRunnable):
    def __init__(self, input_file, settings, signals, media_info=None):
        super().__init__()
        self.input_file = Path(input_file)
        self.settings = normalize_bitrate_settings(settings, legacy=settings.get('bitrate_unit') != BITRATE_UNIT)
        self.signals = signals
        self.process = None
        self.cancelled = threading.Event()
        self.media_info = media_info or {}
        self.input_size = 0
        self.output_size = 0
        self.applied_quality = settings.get('quality_value', '')
        self.output_file = self.input_file.with_name(f"{self.input_file.stem}{settings['suffix']}.{settings['output_format']}")
        self.partial_file = self.output_file.with_name(f'.{self.output_file.stem}.{uuid.uuid4().hex[:8]}.partial{self.output_file.suffix}')

    def run(self):
        outcome = 'failed'
        try:
            if self.cancelled.is_set():
                outcome = 'stopped'
                return
            if self.output_file == self.input_file:
                raise ValueError('출력 경로가 원본 경로와 같습니다.')
            if self.output_file.exists():
                self.signals.log.emit(f'건너뜀 · 이미 존재: {self.output_file.name}')
                outcome = 'skipped'
                return
            ffmpeg = get_ffmpeg_path()
            if not ffmpeg:
                raise FileNotFoundError('ffmpeg.exe를 찾을 수 없습니다.')
            if not video_stream(self.media_info):
                self.media_info = get_media_info(self.input_file) or {}
            if self.settings.get('adaptive_quality') and self.settings['rate_control'] == 'VBR' and not source_video_bitrate(self.media_info):
                analyze_stream_bitrates(self.input_file, self.media_info, self.cancelled.is_set)
            try:
                duration = float(self.media_info.get('format', {}).get('duration', 0))
            except (TypeError, ValueError):
                duration = 0
            self.input_size = self.input_file.stat().st_size
            command = self.build_ffmpeg_command(ffmpeg, self.input_file, self.partial_file)
            kind = '목표 비트레이트' if self.settings['rate_control'] in ('VBR', 'CBR') else '화질'
            self.signals.log.emit(f"설정 · {self.input_file.name} · {self.settings['codec']} · {kind} {self.applied_quality} · {self.settings['resolution']}")
            logging.info('FFmpeg 명령: %s', command)
            if self.cancelled.is_set():
                outcome = 'stopped'
                return
            self.signals.progress.emit(str(self.input_file), 0)
            returncode, tail = self.execute(command, duration)
            if returncode and '-hwaccel' in command and not self.cancelled.is_set() and cuda_failure('\n'.join(tail)):
                self.signals.log.emit(f'GPU 전처리 복귀 · {self.input_file.name} · 소프트웨어 디코딩으로 다시 시도합니다.')
                if self.partial_file.exists():
                    self.partial_file.unlink()
                command = self.build_ffmpeg_command(ffmpeg, self.input_file, self.partial_file, gpu_pipeline=False)
                self.signals.progress.emit(str(self.input_file), 0)
                returncode, tail = self.execute(command, duration)
            if self.cancelled.is_set():
                outcome = 'stopped'
            elif returncode:
                raise RuntimeError('\n'.join(tail[-8:]))
            else:
                self.output_size = self.partial_file.stat().st_size
                if self.settings.get('keep_smaller') and self.output_size >= self.input_size:
                    self.signals.log.emit(f'결과 제외 · {self.input_file.name} · 원본 {self.input_size / 1048576:.1f} MB → 결과 {self.output_size / 1048576:.1f} MB · 원본보다 작아지지 않았습니다. 압축 설정을 확인하세요.')
                    outcome = 'kept'
                else:
                    self.partial_file.rename(self.output_file)
                    self.signals.progress.emit(str(self.input_file), 100)
                    difference = (1 - self.output_size / self.input_size) * 100 if self.input_size else 0
                    comparison = f'{abs(difference):.1f}% ' + ('감소' if difference >= 0 else '증가')
                    self.signals.log.emit(f'완료 · {self.output_file.name} · 원본 대비 {comparison}')
                    outcome = 'done'
        except Exception as exc:
            if self.cancelled.is_set():
                outcome = 'stopped'
            else:
                logging.exception('변환 실패: %s', self.input_file)
                self.signals.log.emit(f'실패 · {self.input_file.name}\n{exc}')
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()
            if self.partial_file.exists():
                try:
                    self.partial_file.unlink()
                except OSError:
                    logging.exception('임시 출력 파일을 정리하지 못했습니다: %s', self.partial_file)
            self.signals.finished.emit(self, outcome)

    def execute(self, command, duration):
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding='utf-8', errors='replace', **process_options())
        if self.cancelled.is_set():
            self.stop()
        tail = []
        for line in self.process.stdout:
            progress_keys = ('frame=', 'fps=', 'stream_', 'bitrate=', 'total_size=', 'out_time_',
                             'out_time=', 'dup_frames=', 'drop_frames=', 'speed=', 'progress=')
            if not line.startswith(progress_keys):
                tail.append(line.rstrip())
                tail = tail[-16:]
            if line.startswith('out_time_us=') and duration > 0:
                try:
                    progress = min(99, max(0, int(int(line.split('=')[1]) / (duration * 10000))))
                    self.signals.progress.emit(str(self.input_file), progress)
                except ValueError:
                    pass
        self.process.wait()
        returncode = self.process.returncode
        self.process.stdout.close()
        return returncode, tail

    def stop(self):
        self.cancelled.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass

    def build_ffmpeg_command(self, ffmpeg_path, input_file, output_file, gpu_pipeline=None):
        s = self.settings
        compatibility_error = validate_media_settings(s, self.media_info)
        if compatibility_error:
            raise EncodingCompatibilityError(compatibility_error)
        video = video_stream(self.media_info)
        adaptive = s.get('adaptive_quality', False)
        quality = adaptive_quality_value(s, int(video.get('height') or 0)) if adaptive and s['rate_control'] in ('CQP', 'CRF') else s['quality_value']
        self.applied_quality = quality
        target = target_bitrate_kbps(s, self.media_info) if s['rate_control'] in ('VBR', 'CBR') else None
        if target is not None:
            self.applied_quality = f'{target} kb/s'
        mapping = f"0:{video['index']}" if 'index' in video else '0:v:0'
        command = [str(ffmpeg_path), '-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-i', str(input_file),
                   '-map', mapping, '-map', '0:a:0?', '-progress', 'pipe:1', '-nostats',
                   '-fps_mode:v', 'passthrough', '-c:v', ENCODERS[s['codec']]]
        filters = []
        hdr = video.get('color_transfer') in ('smpte2084', 'arib-std-b67')
        compatible = 'H.264' in s['codec']
        eligible = ('GPU' in s['codec'] and s.get('gpu_processing', True) and
                    video.get('codec_name') in ('h264', 'hevc', 'av1', 'vp9', 'vp8', 'mpeg2video', 'vc1') and
                    video.get('pix_fmt', 'yuv420p') in ('yuv420p', 'nv12', 'yuv420p10le', 'p010le') and
                    not (hdr and compatible))
        cuda = eligible if gpu_pipeline is None else bool(gpu_pipeline and eligible)
        self.gpu_pipeline_used = cuda
        if cuda:
            index = command.index('-i')
            command[index:index] = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-extra_hw_frames', '8']
        ten_bit = any(depth in str(video.get('pix_fmt', '')) for depth in ('10', '12', '16')) or hdr
        if hdr and compatible:
            filters += ['zscale=t=linear:npl=100', 'format=gbrpf32le', 'tonemap=mobius:desat=2',
                        'zscale=p=bt709:t=bt709:m=bt709:r=limited', 'format=yuv420p']
            command += ['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv']
        elif compatible and not cuda:
            command += ['-pix_fmt', 'yuv420p']
        elif ten_bit and not cuda:
            command += ['-pix_fmt', 'p010le' if 'GPU' in s['codec'] else 'yuv420p10le']
        if hdr and not compatible:
            command += ['-color_primaries', video.get('color_primaries', 'bt2020'),
                        '-color_trc', video['color_transfer'], '-colorspace', video.get('color_space', 'bt2020nc'),
                        '-color_range', video.get('color_range', 'tv')]
        if cuda:
            height = {'1080p': 1080, '720p': 720}.get(s['resolution'])
            size = f'w=-2:h=trunc(min(ih\\,{height})/2)*2' if height else 'w=iw:h=ih'
            pixel_format = 'p010le' if ten_bit and not compatible else 'nv12'
            # A separate CUDA frame pool lets NVDEC and NVENC lookahead overlap.
            filters += [f'scale_cuda={size}:format={pixel_format}:interp_algo=lanczos:passthrough=0']
        elif s['resolution'] in ('1080p', '720p'):
            height = 1080 if s['resolution'] == '1080p' else 720
            filters += [f'scale=-2:trunc(min(ih\\,{height})/2)*2:flags=lanczos']
        if filters:
            command += ['-vf', ','.join(filters)]
        if 'GPU' in s['codec']:
            command += ['-preset', s['preset_option'].split()[0]]
            if adaptive:
                command += ['-tune', 'hq', '-multipass', 'fullres', '-spatial-aq', '1', '-temporal-aq', '1',
                            '-aq-strength', '8', '-rc-lookahead', '32']
            if s['rate_control'] == 'CQP':
                command += ['-rc', 'vbr', '-cq', quality, '-b:v', '0']
            else:
                command += ['-rc', s['rate_control'].lower(), '-b:v', bitrate_argument(target)]
                peak = target if s['rate_control'] == 'CBR' else round(target * 5 / 4)
                command += ['-maxrate', bitrate_argument(peak), '-bufsize', bitrate_argument(peak * 2)]
        elif s['rate_control'] == 'CRF':
            command += ['-crf', quality]
            if 'H.264' in s['codec'] or 'HEVC' in s['codec']:
                command += ['-preset', 'slow']
            if s['codec'] in ('VP9 - CPU', 'AV1 - CPU'):
                command += ['-b:v', '0']
        else:
            command += ['-b:v', bitrate_argument(target)]
            if 'H.264' in s['codec'] or 'HEVC' in s['codec']:
                command += ['-preset', 'slow']
            if s['rate_control'] == 'CBR':
                command += ['-minrate', bitrate_argument(target), '-maxrate', bitrate_argument(target), '-bufsize', bitrate_argument(target)]
            else:
                command += ['-maxrate', bitrate_argument(round(target * 5 / 4)), '-bufsize', bitrate_argument(round(target * 5 / 2))]
        audio = next((stream for stream in self.media_info.get('streams', []) if stream.get('codec_type') == 'audio'), {})
        try:
            audio_bitrate = int(audio.get('bit_rate', 0))
        except (TypeError, ValueError):
            audio_bitrate = 0
        aac_copy = (adaptive and s['audio_option'].startswith('AAC ') and audio.get('codec_name') == 'aac'
                    and 0 < audio_bitrate <= int(s['audio_option'].split()[1].replace('kbps', '')) * 1000)
        if 'Passthrough' in s['audio_option'] or aac_copy:
            command += ['-c:a', 'copy']
        else:
            command += ['-c:a', 'aac', '-b:a', s['audio_option'].split()[1].replace('kbps', 'k')]
        if s['output_format'] == 'mp4':
            command += ['-movflags', '+faststart']
            if 'HEVC' in s['codec']:
                command += ['-tag:v', 'hvc1']
        previous_comment = str(self.media_info.get('format', {}).get('tags', {}).get('comment', ''))
        command += ['-metadata', f'comment=VideoBatchConverter {APP_VERSION}' + (' | ' + previous_comment if previous_comment else '')]
        return command + [str(output_file)]
