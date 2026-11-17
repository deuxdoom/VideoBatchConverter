"""Queue first, bounded parallel metadata, stable rows and cancellable retry."""

import threading
import time
from pathlib import Path

from src import worker
from src.queue_widgets import INFO_ROLE, PATH_ROLE, STATE_ROLE
from tests.test_ui import wait_until


def media(rate='4000000'):
    return {'streams': [{'index': 0, 'codec_type': 'video', 'codec_name': 'h264', 'bit_rate': rate,
                         'width': 1920, 'height': 1080}], 'format': {'duration': '10', 'size': 1000000}}


def test_rows_exist_before_probes_finish_and_parallel_results_keep_order(window, app, tmp_path, monkeypatch):
    files = [tmp_path / f'{index}.mp4' for index in range(6)]
    for file in files:
        file.write_bytes(b'fixture')
    started, release_first = [], threading.Event()
    lock = threading.Lock()
    def probe(path, cancelled=None):
        index = int(Path(path).stem)
        with lock:
            started.append(index)
        if index == 0:
            while not release_first.wait(.01) and not cancelled():
                pass
        return media()
    monkeypatch.setattr(worker, 'get_media_info', probe)
    window.add_paths_to_queue([str(file) for file in files])
    wait_until(app, lambda: window.file_list_widget.count() == 6 and len(started) >= 4)
    assert window.scanning and window.file_list_widget.item(0).data(STATE_ROLE) == '정보 분석 중'
    wait_until(app, lambda: window.file_list_widget.item(1).data(STATE_ROLE) == '대기')
    assert [window.file_list_widget.item(index).data(PATH_ROLE) for index in range(6)] == [str(file.resolve()) for file in files]
    release_first.set()
    wait_until(app, lambda: not window.scanning)
    assert window.target_count() == 6
    assert all(window.file_list_widget.item(index).data(INFO_ROLE)['streams'] for index in range(6))


def test_stop_finishes_running_probes_keeps_unchecked_rows_and_retry_works(window, app, tmp_path, monkeypatch):
    files = [tmp_path / f'{index}.mp4' for index in range(8)]
    for file in files:
        file.write_bytes(b'fixture')
    entered = threading.Event()
    def blocked(path, cancelled=None):
        entered.set()
        while not cancelled():
            time.sleep(.01)
        return None
    monkeypatch.setattr(worker, 'get_media_info', blocked)
    window.add_paths_to_queue([str(file) for file in files])
    wait_until(app, lambda: entered.is_set() and window.file_list_widget.count() == 8)
    window.stop_conversion()
    wait_until(app, lambda: not window.scanning)
    assert window.scan_worker.was_cancelled
    assert window.file_list_widget.count() == 8 and window.target_count() == 0
    assert all(window.file_list_widget.item(index).data(STATE_ROLE) == '분석 중지' for index in range(8))
    monkeypatch.setattr(worker, 'get_media_info', lambda *args, **kwargs: media())
    window.file_list_widget.selectAll()
    window.retry_file_info()
    wait_until(app, lambda: not window.scanning)
    assert window.target_count() == 8
    assert all(window.file_list_widget.item(index).data(STATE_ROLE) == '대기' for index in range(8))


def test_invalid_files_remain_explained_and_generated_folder_results_are_removed(window, app, tmp_path, monkeypatch):
    invalid = tmp_path / 'bad.mp4'
    generated = tmp_path / 'generated.mp4'
    for path in (invalid, generated):
        path.write_bytes(b'fixture')
    def probe(path, cancelled=None):
        if Path(path).name == 'bad.mp4':
            return None
        info = media()
        info['format']['tags'] = {'comment': 'VideoBatchConverter 3.0.0'}
        return info
    monkeypatch.setattr(worker, 'get_media_info', probe)
    window.add_paths_to_queue([str(tmp_path)])
    wait_until(app, lambda: not window.scanning)
    assert window.file_list_widget.count() == 1
    item = window.file_list_widget.item(0)
    assert item.data(PATH_ROLE) == str(invalid.resolve())
    assert item.data(STATE_ROLE) == '분석 실패' and '영상 스트림' in item.toolTip()
    assert window.target_count() == 0


def test_missing_video_bitrate_is_deferred_until_all_basic_info_is_published(app, tmp_path, monkeypatch):
    files = [tmp_path / f'{index}.mkv' for index in range(4)]
    for path in files:
        path.write_bytes(b'fixture')
    sequence = []
    monkeypatch.setattr(worker, 'get_media_info', lambda *args, **kwargs: media('N/A'))
    scanner = worker.QueueScanWorker(files, max_workers=2)
    scanner.details.connect(lambda path, info: sequence.append(('basic', path)))
    def extra(path, info, cancelled):
        sequence.append(('extra', path))
        info['streams'][0]['bit_rate'] = '1000000'
    monkeypatch.setattr(worker, 'analyze_stream_bitrates', extra)
    scanner.run()
    assert [phase for phase, _ in sequence[:4]] == ['basic'] * 4
    assert len(sequence) == 8
