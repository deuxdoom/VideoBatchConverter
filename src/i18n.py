"""Display-only translations. Saved settings and media names stay canonical."""

import json
import re
from string import Formatter

from PyQt6.QtCore import QObject, QLibraryInfo, QLocale, QTranslator, pyqtSignal
from PyQt6.QtWidgets import QApplication

from .paths import ASSETS


with (ASSETS / 'i18n/en.json').open(encoding='utf-8') as catalog_file:
    ENGLISH = json.load(catalog_file)


def _pattern(source):
    parts = []
    for literal, field, *_ in Formatter().parse(source):
        parts.append(re.escape(literal))
        if field:
            value = r'\d+' if field in {'count', 'added', 'skipped', 'selected', 'done', 'total', 'parallel', 'failed'} else r'\d+(?:\.\d+)?' if field in {'value', 'percent', 'size', 'input', 'output'} else '.+?'
            parts.append('(?P<' + field + '>' + value + ')')
    return re.compile(''.join(parts), re.DOTALL)


TEMPLATES = [(_pattern(source), target) for source, target in sorted(ENGLISH.items(), key=lambda pair: len(pair[0]), reverse=True) if '{' in source]
TRANSLATED_FIELDS = {'state', 'comparison', 'resolution', 'details', 'error', 'summary', 'audio_rate'}


class LanguageManager(QObject):
    changed = pyqtSignal(str)

    def __init__(self, app):
        super().__init__(app)
        self.language = ''
        self.qt_translator = QTranslator(self)
        self.qt_translator.load('qtbase_ko', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))

    def set_language(self, language):
        language = language if language in ('ko', 'en') else 'ko'
        if self.language == language:
            return
        self.language = language
        app = QApplication.instance()
        app.removeTranslator(self.qt_translator)
        if language == 'ko':
            app.installTranslator(self.qt_translator)
        QLocale.setDefault(QLocale('ko_KR' if language == 'ko' else 'en_US'))
        self.changed.emit(language)


def language_manager():
    app = QApplication.instance()
    if not hasattr(app, '_vbc_language_manager'):
        app._vbc_language_manager = LanguageManager(app)
        app._vbc_language_manager.set_language('ko')
    return app._vbc_language_manager


def get_language():
    return language_manager().language


def tr(source):
    """Translate a complete UI message, never arbitrary substrings of a filename."""
    if get_language() != 'en' or not source:
        return source
    if source in ENGLISH:
        return ENGLISH[source]
    for pattern, target in TEMPLATES:
        match = pattern.fullmatch(source)
        if match:
            values = {key: tr(value) if key in TRANSLATED_FIELDS else value
                      for key, value in match.groupdict().items()}
            rendered = target.format(**values)
            if values.get('count') == '1':
                rendered = rendered.replace('1 files', '1 file')
            if values.get('parallel') == '1':
                rendered = rendered.replace('1 parallel jobs', '1 parallel job')
            return rendered
    if source.startswith('03  '):
        return '03  ' + tr(source[4:])
    if source.endswith(' 도움말'):
        return tr(source[:-4]) + ' help'
    # Queue totals are made of complete, known state/count pairs.
    if re.fullmatch(r'(?:설정 확인|정보 대기|정보 분석 중|추가 분석 중|분석 실패|분석 중지|대기|진행|완료|원본 유지|결과 제외|실패|건너뜀|중지 중|중지|예측 제외|예측 실패|용량 주의|용량 예측 중) \d+(?: · (?:설정 확인|정보 대기|정보 분석 중|추가 분석 중|분석 실패|분석 중지|대기|진행|완료|원본 유지|결과 제외|실패|건너뜀|중지 중|중지|예측 제외|예측 실패|용량 주의|용량 예측 중) \d+)*', source):
        return ' · '.join(tr(part.rsplit(' ', 1)[0]) + ' ' + part.rsplit(' ', 1)[1]
                          for part in source.split(' · '))
    return source
