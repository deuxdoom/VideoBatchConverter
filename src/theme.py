"""An explicit light palette for every widget, popup and native window."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

COLORS = {
    "primary": "#4263EB", "ink": "#202B45", "muted": "#62708A",
    "canvas": "#F5F7FC", "line": "#E2E8F2", "mint": "#DDF5EE",
    "teal": "#187967", "lavender": "#EEE8FF", "purple": "#7653B5",
    "peach": "#FFF0E2", "orange": "#9F541D",
}


def light_palette():
    """Do not inherit unspecified dark roles from the Windows system palette."""
    palette = QPalette()
    colors = {
        'Window': '#F5F7FC', 'WindowText': '#202B45', 'Base': '#FFFFFF',
        'AlternateBase': '#F7F9FD', 'Text': '#202B45', 'Button': '#F5F7FC',
        'ButtonText': '#202B45', 'BrightText': '#FFFFFF', 'Light': '#FFFFFF',
        'Midlight': '#EEF2FA', 'Mid': '#DCE3F0', 'Dark': '#BAC6DA',
        'Shadow': '#C6CEE0', 'Highlight': '#EDF1FF', 'HighlightedText': '#304FC8',
        'Link': '#4263EB', 'LinkVisited': '#7653B5', 'ToolTipBase': '#202B45',
        'ToolTipText': '#FFFFFF', 'PlaceholderText': '#62708A', 'Accent': '#4263EB',
    }
    for name, color in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, name), QColor(color))
    for name in ('WindowText', 'Text', 'ButtonText', 'PlaceholderText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, name), QColor('#8C97AC'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor('#E9EEF8'))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor('#62708A'))
    return palette


def configure_theme(app):
    # The scheme also controls Windows title bars; QSS alone does not cover them.
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle('Fusion')
    # Changing the Qt style resets class fonts for views/headers. Apply the font
    # policy afterwards so popups and file lists keep the same no-hinting font.
    from .fonts import configure_fonts
    configure_fonts(app)
    app.setPalette(light_palette())
    app.setStyleSheet(stylesheet())

STYLESHEET = """
QWidget { color: #202B45; }
QMainWindow, QDialog { background: #F5F7FC; }
QDialog#brandDialog { background: transparent; }
QFrame#dialogSurface { background: white; border: 1px solid #DCE3F0; border-radius: 14px; }
QLabel#dialogTitle { font-size: 18px; font-weight: 700; }
QFrame#windowSurface { background: #F5F7FC; border: 1px solid #DAE1EF; border-radius: 12px; }
QFrame#windowSurface[maximized="true"] { border-radius: 0; border: none; }
QWidget#titleBar { background: transparent; }
QLabel { background: transparent; border: none; }
QLabel#appName { font-size: 14px; font-weight: 700; }
QLabel#versionBadge { color: #62708A; background: #E9EEF8; border-radius: 6px; padding: 3px 8px; font-size: 11px; max-height: 20px; }
QLabel#pageTitle { font-size: 25px; font-weight: 700; color: #202B45; }
QLabel#workspaceTitle { font-size: 21px; font-weight: 700; }
QLabel#eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: #4263EB; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; }
QLabel#muted, QLabel#fieldLabel { color: #62708A; }
QLabel#fieldLabel { font-size: 11px; }
QLabel#countBadge { background: #EDF1FF; color: #3856CE; border-radius: 10px; padding: 4px 10px; font-weight: 600; }
QLabel#statusBadge { background: #DDF5EE; color: #187967; border-radius: 7px; padding: 5px 10px; font-weight: 600; }
QLabel#statusBadge[attention="true"] { background: #FFF0E2; color: #9F541D; }
QFrame#card { background: white; border: 1px solid #E2E8F2; border-radius: 12px; }
QFrame#dropZone { background: #F8FAFF; border: 1px dashed #BAC9E5; border-radius: 12px; }
QFrame#outputPreview { background: #EDF1FF; border: none; border-radius: 9px; }
QFrame#divider { background: #E2E8F2; max-height: 1px; border: none; }
QPushButton { background: white; border: 1px solid #DCE3F0; border-radius: 7px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #F0F4FF; border-color: #A9B9E6; }
QPushButton:pressed { background: #E3EAFE; }
QPushButton:focus, QToolButton:focus { border: 1px solid #4263EB; }
QPushButton:disabled { background: #F1F3F8; color: #8C97AC; border-color: #E6EBF4; }
QPushButton#primaryButton { background: #4263EB; border: 1px solid #4263EB; color: white; padding: 11px 24px; }
QPushButton#primaryButton:hover { background: #3553D0; }
QPushButton#primaryButton:disabled { background: #DCE3F7; border-color: #DCE3F7; color: #6E7C9D; }
QPushButton#stopButton { color: #B3424F; }
QPushButton#stopButton:disabled { color: #8C97AC; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px; }
QToolButton:hover { background: #E8EEF9; }
QToolButton#settingsButton, QToolButton#settingsButton:pressed, QToolButton#settingsButton:checked { border: none; background: transparent; }
QToolButton#settingsButton:hover, QToolButton#settingsButton:focus { border: none; background: #EDF1FF; }
QFrame#languageSwitch { background: #EDF1FF; border: 1px solid #D6DFF8; border-radius: 16px; }
QPushButton#languageOption { padding: 0; margin: 0; min-height: 0; border: 1px solid transparent; border-radius: 12px; color: #62708A; background: transparent; font-size: 11px; }
QPushButton#languageOption:hover { color: #304FC8; background: #E1E8FF; }
QPushButton#languageOption:checked { background: #4263EB; color: white; }
QPushButton#languageOption:focus { border: 1px solid #202B45; }
QToolButton#savePresetButton { background: #EDF1FF; color: #3856CE; padding: 7px; }
QToolButton#closeButton:hover { background: #FFE1E4; }
QLineEdit, QComboBox, QSpinBox { background: #FAFBFE; color: #202B45; border: 1px solid #DCE3F0; border-radius: 6px; padding: 7px 9px; min-height: 18px; selection-background-color: #4263EB; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #4263EB; background: white; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #F3F5F9; color: #8C97AC; }
QComboBox { padding-right: 25px; }
QComboBox::drop-down { width: 23px; border: none; }
QComboBox::down-arrow { image: url(__CHEVRON__); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: white; color: #202B45; selection-background-color: #EDF1FF; selection-color: #304FC8; border: 1px solid #DCE3F0; padding: 4px; outline: none; }
QComboBox QAbstractItemView::item { min-height: 24px; padding: 4px 9px; border: none; }
QComboBox QAbstractItemView::item:selected { background: #EDF1FF; color: #304FC8; }
QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; }
QSpinBox::up-arrow { image: url(__UP__); width: 12px; height: 12px; }
QSpinBox::down-arrow { image: url(__CHEVRON__); width: 12px; height: 12px; }
QAbstractItemView { background: white; alternate-background-color: #F7F9FD; color: #202B45; selection-background-color: #EDF1FF; selection-color: #304FC8; outline: none; }
QAbstractItemView::item:selected { background: #EDF1FF; color: #304FC8; }
QTreeView, QTableView, QFileDialog QListView { border: 1px solid #DCE3F0; border-radius: 5px; }
QHeaderView { background: #F0F3F9; }
QHeaderView::section { background: #F0F3F9; color: #4C5A73; border: none; border-right: 1px solid #E2E8F2; border-bottom: 1px solid #DCE3F0; padding: 7px 9px; font-weight: 700; }
QTableCornerButton::section { background: #F0F3F9; border: none; }
QFileDialog QSplitter::handle { background: #F5F7FC; }
QListWidget { background: white; border: none; outline: none; padding: 2px; }
QListWidget::item { border: 1px solid transparent; border-bottom: 1px solid #EEF1F7; border-radius: 7px; margin: 1px 0; padding: 8px; }
QListWidget::item:hover { background: #F5F7FD; }
QListWidget::item:selected { background: #EDF1FF; border: 1px solid #BECBF6; color: #304FC8; }
QListWidget:disabled { color: #62708A; }
QListWidget#settingsNavigation { background: #F5F7FC; border-radius: 9px; padding: 4px; }
QListWidget#settingsNavigation::item { padding: 8px 10px; border: none; margin: 2px 0; }
QListWidget#settingsNavigation::item:selected { background: #E7EDFF; color: #304FC8; }
QTextEdit { background: #F8FAFD; color: #4C5A73; border: 1px solid #E7ECF4; border-radius: 7px; padding: 8px; font-size: 12px; selection-background-color: #4263EB; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QProgressBar { background: #E9EEF8; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #4263EB; border-radius: 4px; }
QSplitter::handle:horizontal { background: transparent; width: 12px; }
QSplitter::handle:horizontal:hover { background: #E8EDF9; border-radius: 4px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #C9D3E5; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QMenu { background: white; border: 1px solid #DCE3F0; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 8px 24px; border-radius: 4px; }
QMenu::item:selected { background: #EDF1FF; color: #304FC8; }
QToolTip { background: #202B45; color: white; border: none; padding: 6px; }
QCheckBox { spacing: 7px; }
"""


def stylesheet():
    from .fluent_icons import ASSETS
    return (STYLESHEET.replace("__CHEVRON__", (ASSETS / "icons/chevron-down.svg").as_posix())
            .replace("__UP__", (ASSETS / "icons/chevron-up.svg").as_posix()))
