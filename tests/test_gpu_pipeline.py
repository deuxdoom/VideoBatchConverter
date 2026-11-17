from pathlib import Path

from src.profiles import PRESETS
from src.worker import FileConversionTask, WorkerSignals


def metadata(**video):
    return {'streams': [dict(codec_type='video', codec_name='h264', pix_fmt='yuv420p',
                              width=3840, height=2160, bit_rate='10000000', **video)], 'format': {'duration': '1'}}


def test_cuda_pipeline_keeps_quality_and_resize_on_gpu(tmp_path):
    settings = dict(PRESETS['1080p'])
    task = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals(), metadata())
    command = task.build_ffmpeg_command('ffmpeg', 'in.mp4', 'out.mp4')
    assert command.index('-hwaccel') < command.index('-i')
    assert command[command.index('-hwaccel_output_format') + 1] == 'cuda'
    filters = command[command.index('-vf') + 1]
    assert 'scale_cuda=' in filters and 'min(ih\\,1080)' in filters
    assert 'interp_algo=lanczos' in filters and 'passthrough=0' in filters
    assert command[command.index('-preset') + 1] == 'p6'
    assert command[command.index('-b:v') + 1] == '8000k'
    assert command[command.index('-multipass') + 1] == 'fullres'
    assert '-split_encode_mode' not in command


def test_hdr_tonemapping_and_explicit_gpu_disable_use_software_frames(tmp_path):
    settings = dict(PRESETS['1080p'])
    info = metadata(color_transfer='smpte2084')
    command = FileConversionTask(tmp_path / 'in.mp4', settings, WorkerSignals(), info).build_ffmpeg_command('ffmpeg', 'in', 'out.mp4')
    assert '-hwaccel' not in command
    assert 'tonemap=mobius' in command[command.index('-vf') + 1]
    command = FileConversionTask(tmp_path / 'in.mp4', dict(settings, gpu_processing=False), WorkerSignals(), metadata()).build_ffmpeg_command('ffmpeg', 'in', 'out.mp4')
    assert '-hwaccel' not in command
    assert command[command.index('-c:v') + 1] == 'h264_nvenc'


def test_cuda_error_retries_software_decoding_without_changing_encoder(sample_video, monkeypatch):
    settings = dict(PRESETS['아카이빙'], keep_smaller=False, suffix='_gpu_fallback')
    task = FileConversionTask(sample_video, settings, WorkerSignals(), metadata())
    commands, messages, results = [], [], []
    task.signals.log.connect(messages.append)
    task.signals.finished.connect(lambda _, outcome: results.append(outcome))
    def execute(command, duration):
        commands.append(command)
        if len(commands) == 1:
            return 1, ['CUDA decoder initialization failed']
        task.partial_file.write_bytes(b'fixture-output')
        return 0, []
    monkeypatch.setattr(task, 'execute', execute)
    task.run()
    assert results == ['done'] and len(commands) == 2
    assert '-hwaccel' in commands[0] and '-hwaccel' not in commands[1]
    assert commands[1][commands[1].index('-c:v') + 1] == 'hevc_nvenc'
    assert any('GPU 전처리 복귀' in message for message in messages)
    assert not task.partial_file.exists()
