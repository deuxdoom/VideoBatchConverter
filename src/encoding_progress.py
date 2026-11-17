"""Actual progress drives the fill; animation only smooths it and adds activity."""

import math

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QTimer, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget
from .localized_widgets import LocalizedProperties


class EncodingProgressBar(LocalizedProperties, QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = 0
        self._displayed = 0.0
        self._active = False
        self._indeterminate = False
        self._phase = 0.0
        self.setMinimumHeight(25)
        self.setMaximumHeight(32)
        self.setAccessibleName('전체 인코딩 진행률')
        self.animation = QPropertyAnimation(self, b'displayedProgress', self)
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.advance_phase)

    @pyqtProperty(float)
    def displayedProgress(self):
        return self._displayed

    @displayedProgress.setter
    def displayedProgress(self, value):
        self._displayed = value
        self.update()

    def value(self):
        return self._target

    def setValue(self, value):
        value = min(100, max(0, int(value)))
        self.animation.stop()
        if value < self._target:
            self._displayed = float(value)
        else:
            self.animation.setStartValue(self._displayed)
            self.animation.setEndValue(float(value))
            self.animation.start()
        self._target = value
        self.setAccessibleDescription(f'{value}%')
        self.valueChanged.emit(value)
        self.update()

    def setActive(self, active):
        self._active = active
        self.timer.start() if active and self.isVisible() else self.timer.stop()
        self.update()

    def setIndeterminate(self, indeterminate):
        self._indeterminate = indeterminate
        self.setActive(indeterminate or self._active)

    def advance_phase(self):
        self._phase = (self._phase + .035) % 1.0
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._active:
            self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        count = max(20, width // 10)
        gap = 3
        bar_width = max(1., (width - (count - 1) * gap) / count)
        painter.setPen(Qt.PenStyle.NoPen)
        gradient = QLinearGradient(0, 0, width, 0)
        gradient.setColorAt(0, QColor('#4263EB'))
        gradient.setColorAt(1, QColor('#309EAB'))
        for index in range(count):
            relative = (index + .5) / count
            bar_height = height * (.56 + .44 * abs(math.sin(index * .57)))
            area = QRectF(index * (bar_width + gap), height - bar_height, bar_width, bar_height)
            painter.setBrush(QColor('#E6ECF7'))
            painter.drawRoundedRect(area, 2, 2)
            fill = (self._indeterminate and abs(relative - self._phase) < .12) or (not self._indeterminate and relative <= self._displayed / 100)
            if fill:
                painter.setBrush(gradient)
                painter.drawRoundedRect(area, 2, 2)
                if self._active and not self._indeterminate and abs(relative - self._phase) < .045:
                    painter.setBrush(QColor(255, 255, 255, 65))
                    painter.drawRoundedRect(area, 2, 2)
