"""Create web subsets of the bundled Noto family; original desktop OTFs stay intact."""

from pathlib import Path
from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / 'assets/fonts'


def main():
    for weight in ('Regular', 'Bold'):
        options = subset.Options()
        options.flavor = 'woff2'
        options.name_IDs = ['*']
        options.name_legacy = True
        options.name_languages = ['*']
        options.layout_features = ['*']
        font = subset.load_font(str(FONTS / f'NotoSansCJKkr-{weight}.otf'), options)
        characters = (list(range(0x20, 0x250)) + list(range(0x1100, 0x1200)) + list(range(0x2000, 0x2100))
                      + list(range(0x2190, 0x2300)) + list(range(0x3000, 0x3200))
                      + list(range(0xA960, 0xA980)) + list(range(0xAC00, 0xD7A4)) + list(range(0xD7B0, 0xD800)))
        worker = subset.Subsetter(options=options)
        worker.populate(unicodes=characters)
        worker.subset(font)
        target = FONTS / 'web' / f'NotoSansCJKkr-{weight}.woff2'
        target.parent.mkdir(exist_ok=True)
        subset.save_font(font, str(target), options)
        print(f'{target.name}: {target.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
