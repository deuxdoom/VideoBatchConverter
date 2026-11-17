"""Let wrapped text reserve its actual height after font and width changes."""

from PyQt6.QtCore import QEvent
from .localized_widgets import QLabel


class ReadableLabel(QLabel):
    def fit_wrapped_height(self):
        if self.wordWrap() and self.width() > 30:
            needed = max(self.fontMetrics().height() + 4, self.heightForWidth(self.width()))
            if needed != self.minimumHeight():
                self.setMinimumHeight(needed)

    def setText(self, text):
        super().setText(text)
        self.fit_wrapped_height()

    def setWordWrap(self, enabled):
        super().setWordWrap(enabled)
        self.fit_wrapped_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_wrapped_height()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.fit_wrapped_height()
