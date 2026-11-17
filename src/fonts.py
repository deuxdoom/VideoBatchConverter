"""A single bundled Noto family with native antialiased rendering."""

import logging

from PyQt6.QtGui import QFont, QFontDatabase, QFontInfo
from PyQt6.QtWidgets import QWidget

from .paths import ASSETS

PRIMARY_FONT = 'Noto Sans CJK KR'
RENDERING_STRATEGY = (QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.ForceOutline |
                      QFont.StyleStrategy.NoSubpixelAntialias)


def smooth_widget_fonts(root, descendants=False):
    """Preserve sizes/weights while fixing late-created popup and chooser fonts."""
    for widget in [root] + (root.findChildren(QWidget) if descendants else []):
        font = widget.font()
        if (font.families() != [PRIMARY_FONT] or font.stretch() != 100 or
                font.hintingPreference() != QFont.HintingPreference.PreferNoHinting or font.styleStrategy() != RENDERING_STRATEGY):
            font.setFamilies([PRIMARY_FONT])
            font.setStretch(100)
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            font.setStyleStrategy(RENDERING_STRATEGY)
            widget.setFont(font)


def configure_fonts(app):
    if not app.property('vbcFontsLoaded'):
        for filename in ('NotoSansCJKkr-Regular.otf', 'NotoSansCJKkr-Bold.otf'):
            path = ASSETS / 'fonts' / filename
            if QFontDatabase.addApplicationFont(str(path)) < 0:
                logging.warning('앱 글꼴을 읽지 못했습니다: %s', path)
        app.setProperty('vbcFontsLoaded', True)
    font = QFont()
    font.setFamilies([PRIMARY_FONT])
    font.setPixelSize(13)
    font.setStretch(100)
    font.setStyleStrategy(RENDERING_STRATEGY)
    # CFF hinting produced uneven thin strokes on Windows at fractional DPI.
    # Render the original outlines with grayscale AA, without snapping the strokes.
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    # Windows/Fusion supplies class-specific defaults. Replace those as well;
    # otherwise item views can keep default hinting despite the app font.
    for widget_class in ('QAbstractItemView', 'QHeaderView', 'QComboBox', 'QMenu'):
        app.setFont(font, widget_class)
    logging.info('앱 글꼴: %s · No hinting · 원본 자폭 100%% · 네이티브 DPI', QFontInfo(font).family())
    return font
