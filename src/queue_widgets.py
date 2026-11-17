"""Dense queue rows and accessible click-to-add empty areas."""

from pathlib import Path
import math

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QFrame, QListWidget, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
)
from .i18n import tr
from .localized_widgets import LocalizedProperties
from .fonts import smooth_widget_fonts

PATH_ROLE = Qt.ItemDataRole.UserRole
INFO_ROLE = int(PATH_ROLE) + 1
STATE_ROLE = int(PATH_ROLE) + 2
DETAIL_ROLE = int(PATH_ROLE) + 3
ESTIMATE_ROLE = int(PATH_ROLE) + 4
TIME_ESTIMATE_ROLE = int(PATH_ROLE) + 5


def time_text(seconds):
    seconds = max(1, math.ceil(seconds))
    return (f'{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}' if seconds >= 3600
            else f'{seconds // 60}:{seconds % 60:02d}')


def time_estimate_text(result):
    if result.get('estimated_seconds') is not None:
        return f'예상 약 {time_text(result["estimated_seconds"])}'
    return {'pending': '시간 계산 대기', 'working': '시간 계산 중…'}.get(result.get('state'), '예상 시간 —')


def size_estimate_text(result):
    size = result.get('estimated_bytes')
    if size is not None:
        return f'예상 {size / 1048576:.1f} MB' if size >= 1048576 else f'예상 {size / 1024:.1f} KB'
    return {'pending': '예상 용량 계산 대기', 'working': '예상 용량 계산 중…'}.get(result.get('state'), '예상 용량 —')


def queue_details(item):
    """Compose the visible metadata from the current estimate, including cache hits."""
    details = item.data(DETAIL_ROLE) or ''
    estimate = item.data(ESTIMATE_ROLE)
    return f'{details} · {size_estimate_text(estimate)}' if estimate else details


class ClickableEmptyState(LocalizedProperties, QFrame):
    activated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('파일 또는 폴더 추가')

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class QueueListWidget(LocalizedProperties, QListWidget):
    add_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blank_press = None

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.prepare_fonts)

    def prepare_fonts(self):
        smooth_widget_fonts(self, descendants=True)

    def mousePressEvent(self, event):
        position = event.position().toPoint()
        self._blank_press = position if event.button() == Qt.MouseButton.LeftButton and self.itemAt(position) is None else None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        position = event.position().toPoint()
        activate = (event.button() == Qt.MouseButton.LeftButton and self._blank_press is not None
                    and self.itemAt(position) is None
                    and (position - self._blank_press).manhattanLength() < QApplication.startDragDistance())
        self._blank_press = None
        super().mouseReleaseEvent(event)
        if activate:
            self.add_requested.emit()


class QueueItemDelegate(QStyledItemDelegate):
    """Keep status in its own column while names elide to the available space."""

    def sizeHint(self, option, index):
        return QSize(280, 64)

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        icon = QIcon(styled.icon)
        styled.text = ''
        styled.icon = QIcon()
        style = styled.widget.style() if styled.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        state = index.data(STATE_ROLE) or '대기'
        colors = {
            '완료': ('#187967', '#DDF5EE'), '실패': ('#B3424F', '#FFE9EC'),
            '중지': ('#9F541D', '#FFF0E2'), '기존 결과 있음': ('#7653B5', '#EEE8FF'),
            '중지 중': ('#9F541D', '#FFF0E2'),
            '원본 유지': ('#187967', '#DDF5EE'),
            '결과 제외': ('#9F541D', '#FFF0E2'), '용량 주의': ('#9F541D', '#FFF0E2'),
            '예측 제외': ('#9F541D', '#FFF0E2'), '예측 실패': ('#9F541D', '#FFF0E2'),
            '분석 실패': ('#B3424F', '#FFE9EC'), '분석 중지': ('#9F541D', '#FFF0E2'),
            '설정 확인': ('#9F541D', '#FFF0E2'),
        }
        foreground, background = colors.get(state, ('#3856CE', '#EDF1FF') if '%' in state else ('#62708A', '#F0F3F9'))
        state = tr(state)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setRenderHint(painter.RenderHint.TextAntialiasing)
        row = option.rect.adjusted(12, 0, -12, 0)
        icon.paint(painter, QRect(row.left(), row.center().y() - 12, 24, 24))
        badge_font = QFont(option.font)
        badge_font.setPixelSize(11)
        painter.setFont(badge_font)
        badge_width = painter.fontMetrics().horizontalAdvance(state) + 20
        badge = QRect(row.right() - badge_width, row.top() + 2, badge_width, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(badge, 7, 7)
        painter.setPen(QColor(foreground))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, state)
        left = row.left() + 36
        prediction = tr(time_estimate_text(index.data(TIME_ESTIMATE_ROLE) or {}))
        prediction_width = painter.fontMetrics().horizontalAdvance(prediction) + 12
        prediction_rect = QRect(badge.left() - prediction_width - 8, row.top() + 2, prediction_width, 22)
        painter.setPen(QColor('#4263EB'))
        painter.drawText(prediction_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, prediction)
        width = max(0, prediction_rect.left() - left - 10)
        title_font = QFont(option.font)
        title_font.setPixelSize(13)
        title_font.setWeight(title_font.Weight.DemiBold)
        painter.setFont(title_font)
        filename = Path(index.data(PATH_ROLE) or '').name
        filename = painter.fontMetrics().elidedText(filename, Qt.TextElideMode.ElideMiddle, width)
        painter.setPen(QColor('#304FC8' if option.state & QStyle.StateFlag.State_Selected else '#202B45'))
        painter.drawText(QRect(left, row.top() + 1, width, 22), Qt.AlignmentFlag.AlignVCenter, filename)
        painter.setFont(badge_font)
        painter.setPen(QColor('#62708A'))
        detail_width = max(0, row.right() - left)
        for line_number, line in enumerate(tr(queue_details(index)).split('\n')):
            details = painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, detail_width)
            painter.drawText(QRect(left, row.top() + 23 + line_number * 18, detail_width, 18),
                             Qt.AlignmentFlag.AlignVCenter, details)
        painter.restore()
