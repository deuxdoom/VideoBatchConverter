from io import BytesIO
import zipfile

from src.ffmpeg_downloader import DOWNLOAD_ASSET_NAME, DownloadWorker


class Response:
    headers = {'content-length': '0'}

    def __init__(self, content=b''):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {'assets': [{'name': DOWNLOAD_ASSET_NAME, 'browser_download_url': 'https://example.invalid/ffmpeg.zip'}]}

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def install_worker(tmp_path, monkeypatch, content):
    from src import ffmpeg_downloader
    responses = iter((Response(), Response(content)))
    monkeypatch.setattr(ffmpeg_downloader.requests, 'get', lambda *args, **kwargs: next(responses))
    return DownloadWorker(tmp_path)


def test_installer_extracts_only_tools_and_cleans_staging(tmp_path, monkeypatch):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('ffmpeg/bin/ffmpeg.exe', b'ffmpeg')
        archive.writestr('ffmpeg/bin/ffprobe.exe', b'ffprobe')
        archive.writestr('../../unwanted.txt', b'ignore')
    worker = install_worker(tmp_path, monkeypatch, buffer.getvalue())
    results = []
    worker.result.connect(lambda success, message: results.append(success))
    worker.run()
    assert results == [True]
    assert {p.name for p in tmp_path.iterdir()} == {'ffmpeg.exe', 'ffprobe.exe'}


def test_installer_failure_cleans_staging(tmp_path, monkeypatch):
    worker = install_worker(tmp_path, monkeypatch, b'broken archive')
    results = []
    worker.result.connect(lambda success, message: results.append(success))
    worker.run()
    assert results == [False]
    assert not list(tmp_path.iterdir())


def test_installer_cancel_cleans_staging(tmp_path, monkeypatch):
    worker = install_worker(tmp_path, monkeypatch, b'partial')
    monkeypatch.setattr(worker, 'isInterruptionRequested', lambda: True)
    results = []
    worker.result.connect(lambda success, message: results.append(success))
    worker.run()
    assert results == [False]
    assert not list(tmp_path.iterdir())
