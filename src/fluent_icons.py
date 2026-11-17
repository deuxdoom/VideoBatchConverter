"""Project-local Fluent SVGs, tinted and rendered at multiple resolutions."""

from functools import lru_cache
import re

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


from .paths import ASSETS


@lru_cache(maxsize=128)
def fluent_icon(name, color="#62708A"):
    source = (ASSETS / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    source = re.sub(r'fill="(#[0-9a-fA-F]+|currentColor)"', f'fill="{color}"', source)
    return svg_icon(source)


def svg_icon(source):
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


@lru_cache(maxsize=1)
def app_icon():
    return svg_icon((ASSETS / "brand" / "mark.svg").read_text(encoding="utf-8"))
