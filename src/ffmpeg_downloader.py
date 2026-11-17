"""First-run installer with cancellation, timeouts and automatic staging cleanup."""

from pathlib import Path
import os
import logging
import tempfile
import zipfile

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from .fluent_icons import app_icon
from .localized_widgets import QDialog, QLabel, QPushButton

FFMPEG_API_URL = 'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest'
DOWNLOAD_ASSET_NAME = 'ffmpeg-master-latest-win64-gpl.zip'


class DownloadWorker(QThread):
    status_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    result = pyqtSignal(bool, str)

    def __init__(self, target_dir, parent=None):
        super().__init__(parent)
        self.target_dir = Path(target_dir)

    def run(self):
        try:
            self.target_dir.mkdir(parents=True, exist_ok=True)
            self.status_changed.emit('최신 FFmpeg 정보를 확인하고 있습니다…')
            response = requests.get(FFMPEG_API_URL, timeout=(10, 20))
            response.raise_for_status()
            url = next((a['browser_download_url'] for a in response.json().get('assets', [])
                        if a['name'] == DOWNLOAD_ASSET_NAME), None)
            if not url:
                raise RuntimeError('Windows용 FFmpeg 다운로드를 찾지 못했습니다.')
            with tempfile.TemporaryDirectory(prefix='.install-', dir=self.target_dir) as staging:
                archive = Path(staging) / 'ffmpeg.zip'
                self.status_changed.emit('FFmpeg을 다운로드하고 있습니다…')
                with requests.get(url, stream=True, timeout=(10, 30)) as stream:
                    stream.raise_for_status()
                    total = int(stream.headers.get('content-length', 0))
                    downloaded = 0
                    with archive.open('wb') as output:
                        for chunk in stream.iter_content(chunk_size=256 * 1024):
                            if self.isInterruptionRequested():
                                self.result.emit(False, '설치를 취소했습니다.')
                                return
                            output.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                self.progress_updated.emit(int(downloaded * 100 / total))
                if self.isInterruptionRequested():
                    self.result.emit(False, '설치를 취소했습니다.')
                    return
                self.status_changed.emit('FFmpeg과 FFprobe를 설치하고 있습니다…')
                with zipfile.ZipFile(archive) as package:
                    for tool in ('ffmpeg.exe', 'ffprobe.exe'):
                        member = next((name for name in package.namelist() if name.endswith('/bin/' + tool)), None)
                        if not member:
                            raise RuntimeError(f'다운로드에 {tool}이 없습니다.')
                        (Path(staging) / tool).write_bytes(package.read(member))
                for tool in ('ffmpeg.exe', 'ffprobe.exe'):
                    os.replace(Path(staging) / tool, self.target_dir / tool)
            self.result.emit(True, '설치를 완료했습니다.')
        except Exception as exc:
            if not self.isInterruptionRequested():
                logging.exception('FFmpeg 설치 실패')
            self.result.emit(False, f'설치하지 못했습니다: {exc}')


class FFmpegDownloaderDialog(QDialog):
    def __init__(self, target_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle('동영상 변환 준비')
        self.setWindowIcon(app_icon())
        self.setModal(True)
        self.setMinimumWidth(470)
        self._result = (False, '')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        title = QLabel('처음 한 번, FFmpeg이 필요합니다.')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        hint = QLabel('영상 변환에 사용할 FFmpeg과 FFprobe를 내려받습니다.\n설치 후에는 내 PC에서 영상을 변환할 수 있습니다.')
        hint.setObjectName('muted')
        layout.addWidget(hint)
        self.status_label = QLabel('설치 준비 중…')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        self.cancel_button = QPushButton('설치 취소')
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        self.worker = DownloadWorker(target_dir, self)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.result.connect(self.remember_result)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def remember_result(self, success, message):
        self._result = success, message

    def on_finished(self):
        success, message = self._result
        if success:
            self.accept()
        elif self.worker.isInterruptionRequested():
            super().reject()
        else:
            self.status_label.setText(message + '\n인터넷 연결을 확인한 뒤 프로그램을 다시 실행해 주세요.')
            self.cancel_button.setText('닫기')
            self.cancel_button.setEnabled(True)

    def reject(self):
        if self.worker.isRunning():
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status_label.setText('다운로드를 중지하고 임시 파일을 정리하고 있습니다…')
        else:
            super().reject()

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
