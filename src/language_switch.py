"""Compact keyboard-accessible Korean/English segmented switch."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton

from .i18n import get_language, language_manager


class LanguageSwitch(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('languageSwitch')
        self.setFixedHeight(32)
        self.setAccessibleName('한국어 / English')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for language, caption, name in [('ko', '한국어', '한국어로 표시'), ('en', 'EN', 'Display in English')]:
            button = QPushButton(caption)
            button.setObjectName('languageOption')
            button.setCheckable(True)
            button.setFixedSize(58 if language == 'ko' else 42, 24)
            button.setAccessibleName(name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked, value=language: language_manager().set_language(value))
            self.group.addButton(button)
            self.buttons[language] = button
            layout.addWidget(button)
        language_manager().changed.connect(self.refresh)
        self.refresh(get_language())

    def refresh(self, language):
        self.buttons[language].setChecked(True)
