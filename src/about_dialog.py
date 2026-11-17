"""Small, readable product information using the shared visual identity."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialogButtonBox, QHBoxLayout, QVBoxLayout, QWidget

from .fluent_icons import app_icon, fluent_icon
from .localized_widgets import QDialog, QLabel, QPushButton


class AboutContent(QWidget):
    def __init__(self, version, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(76, 76))
        header.addWidget(logo)
        titles = QVBoxLayout()
        title = QLabel('VideoBatchConverter')
        title.setObjectName('pageTitle')
        titles.addWidget(title)
        titles.addWidget(QLabel(f'{version}  ·  영상은 선명하게, 보관은 가볍게.'))
        header.addLayout(titles)
        layout.addLayout(header)
        description = QLabel('여러 영상의 코덱을 통일하고, 고효율 코덱으로 보관 용량을 줄입니다.\n'
                             '원본 보호, 목적별 프리셋, NVIDIA NVENC와 CPU 인코딩을 지원합니다.\n\n'
                             '변환은 내 PC에서 진행됩니다. 업데이트 확인과 FFmpeg 최초 설치에는\n'
                             '인터넷을 사용합니다. 코덱과 기기별 재생 호환성은 다를 수 있습니다.\n\n'
                             'MIT License · deuxdoom\n'
                             'Fluent System Icons © Microsoft Corporation (MIT)\n'
                             'FFmpeg is a trademark of Fabrice Bellard.')
        description.setWordWrap(True)
        description.setObjectName('muted')
        layout.addWidget(description)
        sound_credit = QLabel('완료음: Kenney Interface Sounds (CC0)')
        sound_credit.setObjectName('muted')
        layout.addWidget(sound_credit)
        row = QHBoxLayout()
        github = QPushButton('GitHub 저장소')
        github.setIcon(fluent_icon('folder', '#4263EB'))
        github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://github.com/deuxdoom/VideoBatchConverter')))
        row.addWidget(github)
        row.addStretch()
        layout.addLayout(row)


class AboutDialog(QDialog):
    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.setWindowTitle('VideoBatchConverter 정보')
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(490)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.addWidget(AboutContent(version, self))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
