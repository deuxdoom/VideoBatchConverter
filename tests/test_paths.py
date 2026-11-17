from pathlib import Path
import runpy


def test_packaged_resources_and_ffmpeg_share_single_bin(monkeypatch, tmp_path):
    import sys
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path / 'bin'), raising=False)
    loaded = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'src/paths.py'))
    assert loaded['ASSETS'] == tmp_path / 'bin'
    assert loaded['ffmpeg_directory']() == tmp_path / 'bin/ffmpeg'
