"""Small, consistent product dialogs with a quiet brand header."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from .fluent_icons import app_icon
from .localized_widgets import QDialog, QLabel, QPushButton
from .fonts import smooth_widget_fonts


class BrandDialog(QDialog):
    def __init__(self, title, parent=None, width=420):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('brandDialog')
        self.setMinimumWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        surface = QFrame()
        surface.setObjectName('dialogSurface')
        outer.addWidget(surface)
        self.content = QVBoxLayout(surface)
        self.content.setContentsMargins(24, 22, 24, 22)
        self.content.setSpacing(16)
        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(26, 26))
        header.addWidget(icon)
        name = QLabel('VideoBatchConverter')
        name.setObjectName('appName')
        header.addWidget(name)
        header.addStretch()
        self.content.addLayout(header)
        heading = QLabel(title)
        heading.setObjectName('dialogTitle')
        heading.setWordWrap(True)
        self.content.addWidget(heading)
        self.actions = QHBoxLayout()
        self.actions.addStretch()

    def add_action(self, text, callback, primary=False, default=False):
        button = QPushButton(text)
        button.setMinimumWidth(92)
        if primary:
            button.setObjectName('primaryButton')
        button.setDefault(default)
        button.clicked.connect(callback)
        self.actions.addWidget(button)
        return button

    def finish_layout(self):
        self.content.addLayout(self.actions)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.prepare_fonts)

    def prepare_fonts(self):
        smooth_widget_fonts(self, descendants=True)


class ConfirmExitDialog(BrandDialog):
    def __init__(self, busy=False, parent=None):
        super().__init__('프로그램을 종료할까요?', parent)
        if busy:
            hint = QLabel('진행 중인 작업을 중지하고 종료합니다.')
            hint.setObjectName('muted')
            self.content.addWidget(hint)
        self.cancel_button = self.add_action('취소', self.reject, default=True)
        self.exit_button = self.add_action('종료', self.accept, primary=True)
        self.finish_layout()
