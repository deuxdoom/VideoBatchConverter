"""A decision before spending time on potentially larger outputs."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from .brand_dialog import BrandDialog
from .i18n import tr
from .localized_widgets import QLabel


class EstimateDialog(BrandDialog):
    SKIP_RISK = 2

    def __init__(self, problems, parent=None):
        super().__init__('예상 용량을 확인해 주세요', parent, width=740)
        hint = QLabel('샘플 기준 추정값입니다. 실제 크기는 다를 수 있습니다.\nCQ/CRF는 숫자를 높이고, 비트레이트는 낮추면 용량을 줄일 수 있습니다.')
        hint.setObjectName('muted')
        hint.setWordWrap(True)
        self.content.addWidget(hint)
        scope = QLabel('이 선택은 이후의 주의 파일에도 적용됩니다.')
        scope.setObjectName('muted')
        self.content.addWidget(scope)
        table = QTableWidget(len(problems), 4)
        table.setHorizontalHeaderLabels([tr(text) for text in ('파일', '원본', '예상', '확인 사항')])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setMinimumHeight(160)
        table.setMaximumHeight(290)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for row, result in enumerate(problems):
            source = result.get('source_bytes', 0)
            estimate = result.get('estimated_bytes')
            values = (Path(result['path']).name, f'{source / 1048576:.1f} MB' if source else '—',
                      f'{estimate / 1048576:.1f} MB' if estimate is not None else '—',
                      tr('절감 불확실') if result['state'] == 'risk' else tr('설정 확인') if result['state'] == 'blocked' else tr('예측 실패'))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(result.get('error', '') or text)
                table.setItem(row, column, item)
        self.content.addWidget(table)
        self.adjust_button = self.add_action('설정 조정', self.reject, default=True)
        self.skip_button = self.add_action('주의 파일 제외', lambda: self.done(self.SKIP_RISK))
        self.continue_button = self.add_action('그대로 진행', self.accept, primary=True)
        self.continue_button.setEnabled(not any(result['state'] == 'blocked' for result in problems))
        self.finish_layout()
