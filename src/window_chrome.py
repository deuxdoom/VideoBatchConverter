"""Frameless chrome with native system move/resize and keyboard shortcuts."""

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QToolButton, QVBoxLayout, QWidget

from .fluent_icons import app_icon, fluent_icon
from .i18n import tr
from .language_switch import LanguageSwitch
from .localized_widgets import QLabel, QToolButton


class TitleBar(QWidget):
    def __init__(self, window, version):
        super().__init__(window)
        self.owner = window
        self.setObjectName("titleBar")
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(28, 28))
        title = QLabel("VideoBatchConverter")
        title.setObjectName("appName")
        version_label = QLabel(version)
        version_label.setObjectName("versionBadge")
        for label in (logo, title, version_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
        layout.addStretch()
        self.language_switch = LanguageSwitch(self)
        layout.addWidget(self.language_switch)
        self.settings_button = self.button("settings", "설정", window.show_settings_dialog)
        self.settings_button.setObjectName('settingsButton')
        layout.addWidget(self.settings_button)
        layout.addSpacing(10)
        self.min_button = self.button("subtract", "최소화", window.showMinimized)
        self.max_button = self.button("maximize", "최대화", self.toggle_maximized)
        self.close_button = self.button("dismiss", "닫기", window.close)
        self.close_button.setObjectName("closeButton")
        for button in (self.min_button, self.max_button, self.close_button):
            layout.addWidget(button)

    def button(self, icon_name, text, callback):
        button = QToolButton(self)
        button.setIcon(fluent_icon(icon_name))
        button.setIconSize(QSize(17, 17))
        button.setFixedSize(34, 30)
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.clicked.connect(callback)
        return button

    def toggle_maximized(self):
        self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()

    def update_state(self):
        maximized = self.owner.isMaximized()
        text = "이전 크기로 복원" if maximized else "최대화"
        self.max_button.setIcon(fluent_icon("restore" if maximized else "maximize"))
        self.max_button.setToolTip(text)
        self.max_button.setAccessibleName(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.owner.windowHandle():
            self.owner.windowHandle().startSystemMove()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.addAction(tr("이전 크기로 복원"), self.owner.showNormal).setEnabled(self.owner.isMaximized())
            menu.addAction(tr("최소화"), self.owner.showMinimized)
            menu.addAction(tr("최대화"), self.owner.showMaximized).setEnabled(not self.owner.isMaximized())
            menu.addSeparator()
            menu.addAction(tr("닫기    Alt+F4"), self.owner.close)
            menu.exec(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()


class FramelessWindow(QMainWindow):
    BORDER = 6

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.chrome_root = QWidget()
        self.chrome_root.setMouseTracking(True)
        self.chrome_root.installEventFilter(self)
        self.setCentralWidget(self.chrome_root)
        self.chrome_layout = QVBoxLayout(self.chrome_root)
        self.chrome_layout.setContentsMargins(self.BORDER, self.BORDER, self.BORDER, self.BORDER)
        self.chrome_layout.setSpacing(0)
        self.surface = QFrame()
        self.surface.setObjectName("windowSurface")
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(0, 0, 0, 0)
        self.surface_layout.setSpacing(0)
        self.chrome_layout.addWidget(self.surface)
        self.title_bar = None
        close_action = QAction(self)
        close_action.setShortcut(QKeySequence("Alt+F4"))
        close_action.triggered.connect(self.close)
        self.addAction(close_action)

    def resize_edges(self, pos):
        if self.isMaximized():
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        if pos.x() < self.BORDER:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= self.width() - self.BORDER:
            edges |= Qt.Edge.RightEdge
        if pos.y() < self.BORDER:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= self.height() - self.BORDER:
            edges |= Qt.Edge.BottomEdge
        return edges

    def eventFilter(self, watched, event):
        if watched is self.chrome_root:
            if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
                edges = self.resize_edges(event.position().toPoint())
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    if edges and self.windowHandle():
                        self.windowHandle().startSystemResize(edges)
                        return True
                diagonal = ((edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or
                            (edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge))
                if edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge) and edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                    cursor = Qt.CursorShape.SizeFDiagCursor if diagonal else Qt.CursorShape.SizeBDiagCursor
                elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                    cursor = Qt.CursorShape.SizeHorCursor
                elif edges:
                    cursor = Qt.CursorShape.SizeVerCursor
                else:
                    cursor = Qt.CursorShape.ArrowCursor
                self.chrome_root.setCursor(cursor)
        return super().eventFilter(watched, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "surface"):
            margin = 0 if self.isMaximized() else self.BORDER
            self.chrome_layout.setContentsMargins(margin, margin, margin, margin)
            self.surface.setProperty("maximized", self.isMaximized())
            self.surface.style().unpolish(self.surface)
            self.surface.style().polish(self.surface)
            if self.title_bar:
                self.title_bar.update_state()
