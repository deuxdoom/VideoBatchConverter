"""Rebuild deterministic CI exports. Run from the repository with Python + PyQt6."""

import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.fonts import configure_fonts
BRAND = ROOT / 'assets/brand'
SOCIAL = ROOT / 'assets/social'


def render(source, path, width, height):
    renderer = QSvgRenderer(QByteArray(source.encode('utf-8')))
    if not renderer.isValid():
        raise ValueError(f'Invalid SVG: {path}')
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    if not canvas.save(str(path)):
        raise RuntimeError(f'Cannot save {path}')


def main():
    app = QApplication.instance() or QApplication([])
    configure_fonts(app)
    mark = (BRAND / 'mark.svg').read_text(encoding='utf-8')
    inner = mark[mark.index('>') + 1:mark.rindex('</svg>')]
    BRAND.mkdir(exist_ok=True)
    SOCIAL.mkdir(exist_ok=True)
    for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        render(mark, BRAND / f'app-icon-{size}.png', size, size)
    # Qt's ICO writer keeps a crisp 256px app icon. Windows scales smaller sizes.
    icon = QImage(str(BRAND / 'app-icon-256.png'))
    if not icon.save(str(BRAND / 'app-icon.ico')):
        raise RuntimeError('ICO encoder unavailable')
    wordmark = f'''<svg xmlns="http://www.w3.org/2000/svg" width="660" height="128" viewBox="0 0 660 128">
<g>{inner}</g><text x="150" y="64" font-family="Noto Sans CJK KR" font-size="34" font-weight="700" fill="#202B45">VideoBatchConverter</text>
<text x="151" y="94" font-family="Noto Sans CJK KR" font-size="17" fill="#62708A">영상은 선명하게, 보관은 가볍게.</text></svg>'''
    (BRAND / 'wordmark.svg').write_text(wordmark, encoding='utf-8')
    render(wordmark, BRAND / 'wordmark.png', 1320, 256)
    social = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640">
<rect width="1280" height="640" fill="#F5F7FC"/>
<circle cx="1100" cy="120" r="290" fill="#EEE8FF"/><circle cx="1230" cy="650" r="310" fill="#DDF5EE"/>
<g transform="translate(88 80) scale(.47)">{inner}</g>
<text x="164" y="106" font-family="Noto Sans CJK KR" font-size="15" font-weight="700" letter-spacing="2" fill="#4263EB">VIDEO BATCH CONVERTER</text>
<text x="164" y="131" font-family="Noto Sans CJK KR" font-size="14" fill="#62708A">3.0.0 · 2026-11-17</text>
<text x="88" y="240" font-family="Noto Sans CJK KR" font-size="76" font-weight="700" letter-spacing="-2" fill="#202B45">VideoBatch</text>
<text x="88" y="322" font-family="Noto Sans CJK KR" font-size="76" font-weight="700" letter-spacing="-2" fill="#202B45">Converter</text>
<text x="92" y="382" font-family="Noto Sans CJK KR" font-size="25" fill="#4C5A73">영상은 선명하게, 보관은 가볍게.</text>
<rect x="92" y="419" width="105" height="36" rx="18" fill="#DDF5EE"/><text x="113" y="443" font-family="Noto Sans CJK KR" font-size="16" font-weight="600" fill="#187967">아카이빙</text>
<rect x="208" y="419" width="80" height="36" rx="18" fill="#EEE8FF"/><text x="232" y="443" font-family="Noto Sans CJK KR" font-size="16" font-weight="600" fill="#7653B5">1080p</text>
<rect x="299" y="419" width="80" height="36" rx="18" fill="#FFF0E2"/><text x="321" y="443" font-family="Noto Sans CJK KR" font-size="16" font-weight="600" fill="#9F541D">720p</text>
<text x="92" y="546" font-family="Noto Sans CJK KR" font-size="18" fill="#62708A">deuxdoom / VideoBatchConverter</text>
<rect x="748" y="151" width="368" height="249" rx="24" fill="#DFD6FA" transform="rotate(-9 932 275)"/>
<rect x="770" y="181" width="368" height="249" rx="24" fill="#B4E8DA" transform="rotate(-3 954 305)"/>
<rect x="794" y="211" width="368" height="249" rx="24" fill="white" stroke="#DCE3F0"/>
<rect x="815" y="232" width="326" height="171" rx="14" fill="#4263EB"/>
<circle cx="977" cy="317" r="39" fill="#FFFFFF" fill-opacity=".15"/>
<path d="m969 296 29 18c3 2 3 5 0 7l-29 18c-3 2-6 0-6-3v-37c0-3 3-5 6-3Z" fill="white"/>
<rect x="817" y="425" width="90" height="7" rx="3.5" fill="#CED7EE"/>
<rect x="1021" y="418" width="120" height="22" rx="11" fill="#DDF5EE"/>
<text x="1035" y="434" font-family="Noto Sans CJK KR" font-size="12" font-weight="600" fill="#187967">Ready to convert</text>
<text x="832" y="510" font-family="Noto Sans CJK KR" font-size="17" fill="#4C5A73">Batch in. Better out.</text>
</svg>'''
    (SOCIAL / 'social-card.svg').write_text(social, encoding='utf-8')
    render(social, SOCIAL / 'social-card.png', 1280, 640)
    board = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">
<rect width="1440" height="900" fill="#F5F7FC"/>
<text x="80" y="92" font-family="Noto Sans CJK KR" font-size="17" font-weight="600" letter-spacing="3" fill="#4263EB">VISUAL IDENTITY / 3.0</text>
<text x="80" y="150" font-family="Noto Sans CJK KR" font-size="38" font-weight="700" fill="#202B45">VideoBatchConverter</text>
<text x="82" y="192" font-family="Noto Sans CJK KR" font-size="22" fill="#62708A">여러 프레임이 모여, 가벼운 하나의 결과로.</text>
<rect x="80" y="235" width="1280" height="320" rx="24" fill="white" stroke="#E2E8F2"/>
<g transform="translate(140 275) scale(1.8)">{inner}</g>
<g transform="translate(420 355) scale(.65)">{inner}</g>
<text x="525" y="394" font-family="Noto Sans CJK KR" font-size="38" font-weight="700" fill="#202B45">VideoBatchConverter</text>
<text x="528" y="435" font-family="Noto Sans CJK KR" font-size="22" fill="#62708A">영상은 선명하게, 보관은 가볍게.</text>
<text x="80" y="623" font-family="Noto Sans CJK KR" font-size="17" font-weight="600" fill="#202B45">LIGHT SURFACES. CLEAR CONTRAST.</text>
{''.join(f'<rect x="{80+i*215}" y="655" width="195" height="100" rx="16" fill="{color}"/><text x="{80+i*215}" y="789" font-family="Noto Sans CJK KR" font-size="17" fill="#202B45">{name}</text><text x="{80+i*215}" y="817" font-family="Noto Sans CJK KR" font-size="15" fill="#62708A">{color}</text>' for i,(name,color) in enumerate([('Action blue','#4263EB'),('Mint','#DDF5EE'),('Lavender','#EEE8FF'),('Peach','#FFF0E2'),('Canvas','#F5F7FC'),('Ink','#202B45')]))}
</svg>'''
    (BRAND / 'brand-board.svg').write_text(board, encoding='utf-8')
    render(board, BRAND / 'brand-board.png', 1440, 900)
    print('Brand assets generated: SVG, PNG, ICO; social-card.png = 1280 x 640')


if __name__ == '__main__':
    main()
