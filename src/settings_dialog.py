"""Modeless application preferences, grouped by purpose and easy to extend."""

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .about_dialog import AboutContent
from .brand_dialog import BrandDialog
from .fluent_icons import fluent_icon
from .i18n import language_manager, tr
from .language_switch import LanguageSwitch
from .localized_widgets import QLineEdit, QPushButton
from .paths import ffmpeg_directory
from .profiles import APP_VERSION, HELP_DETAILS
from .source_picker import SourceFileDialog
from .text_widgets import ReadableLabel


HELP_TITLES = {
    'codec': '비디오 코덱', 'resolution': '해상도', 'preset': 'GPU 프리셋',
    'rate_control': '압축 방식', 'quality_value': '품질과 자동 조절',
    'suffix': '파일 접미사', 'audio_option': '오디오',
    'output_format': '저장 형식', 'parallel_jobs': '동시 작업 수',
}


def caption(text, heading=False):
    label = ReadableLabel(text)
    label.setObjectName('sectionTitle' if heading else 'muted')
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class SettingsDialog(BrandDialog):
    def __init__(self, owner):
        super().__init__('설정', owner, width=760)
        self.owner = owner
        self.resize(800, 590)
        self.setMinimumHeight(520)
        self.categories = {}
        body = QHBoxLayout()
        body.setSpacing(24)
        self.navigation = QListWidget()
        self.navigation.setObjectName('settingsNavigation')
        self.navigation.setAccessibleName(tr('설정 카테고리'))
        self.navigation.setFixedWidth(148)
        self.navigation.setIconSize(QSize(18, 18))
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(self.navigation)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.content.addLayout(body, 1)
        self.add_category('general', '일반', 'settings', self.general_page())
        self.add_category('advanced', '고급', 'sparkle', self.advanced_page())
        self.add_category('folders', '폴더', 'folder', self.folders_page())
        self.add_category('help', '도움말', 'info', self.help_page())
        self.add_category('about', '정보', 'video', AboutContent(APP_VERSION))
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.content.addWidget(caption('변경 사항은 즉시 저장됩니다.'))
        self.close_button = self.add_action('닫기', self.accept, primary=True, default=True)
        self.finish_layout()
        language_manager().changed.connect(self.retranslate_categories)
        owner.input_path_edit.textChanged.connect(self.folder_path.setText)
        self.refresh_controls()

    def add_category(self, key, title, icon, content):
        """Register a stable category key and its scrollable content in one place."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        item = QListWidgetItem(fluent_icon(icon, '#4263EB'), tr(title))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setSizeHint(QSize(140, 44))
        self.navigation.addItem(item)
        self.pages.addWidget(scroll)
        self.categories[key] = (title, item, scroll)

    def select_category(self, key):
        if key in self.categories:
            self.navigation.setCurrentItem(self.categories[key][1])

    def retranslate_categories(self, *_):
        for title, item, _ in self.categories.values():
            item.setText(tr(title))
        self.navigation.setAccessibleName(tr('설정 카테고리'))

    def page(self, title, description):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 2, 12, 8)
        layout.setSpacing(14)
        layout.addWidget(caption(title, heading=True))
        layout.addWidget(caption(description))
        return widget, layout

    def general_page(self):
        widget, layout = self.page('일반', '언어와 완료 알림을 설정합니다.')
        layout.addWidget(caption('표시 언어', heading=True))
        self.language_switch = LanguageSwitch()
        layout.addWidget(self.language_switch, 0, Qt.AlignmentFlag.AlignLeft)
        self.completion_sound_check = self.owner.completion_sound_check
        layout.addWidget(self.completion_sound_check)
        self.completion_sound_check.show()
        layout.addWidget(caption('실제 변환이 모두 끝나면 한 번 재생합니다. 작업 중에도 끌 수 있습니다.'))
        layout.addStretch()
        return widget

    def advanced_page(self):
        widget, layout = self.page('고급', 'GPU 프리셋·압축 방식·파일 접미사·동시 작업 수와 변환 전 확인을 설정합니다.')
        for name in ('preset_option_combo', 'rate_control_combo', 'suffix_edit', 'parallel_jobs_spinbox',
                     'keep_smaller_check', 'estimate_size_check', 'gpu_processing_check'):
            setattr(self, name, getattr(self.owner, name))
        layout.addWidget(self.owner.advanced_panel)
        self.owner.advanced_panel.show()
        self.busy_hint = caption('작업 중에는 변환 관련 설정을 바꿀 수 없습니다.')
        layout.addWidget(self.busy_hint)
        layout.addStretch()
        return widget

    def folders_page(self):
        widget, layout = self.page('폴더', '파일을 추가할 때 열 폴더와 저장 위치를 확인합니다.')
        layout.addWidget(caption('파일 추가 시작 폴더', heading=True))
        self.folder_path = QLineEdit(self.owner.input_path_edit.text())
        self.folder_path.setReadOnly(True)
        self.folder_path.setAccessibleName('파일 추가 시작 폴더')
        self.folder_path.setPlaceholderText('마지막으로 사용한 폴더가 없습니다.')
        layout.addWidget(self.folder_path)
        self.folder_browse = QPushButton('폴더 선택')
        self.folder_browse.setIcon(fluent_icon('folder'))
        self.folder_browse.clicked.connect(self.choose_folder)
        layout.addWidget(self.folder_browse, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(caption('결과 저장 위치', heading=True))
        layout.addWidget(caption('결과는 원본과 같은 폴더에 저장합니다. 기존 파일을 덮어쓰지 않습니다.'))
        layout.addWidget(caption('프로그램 폴더', heading=True))
        for title, path in (('설정 파일 폴더 열기', Path(self.owner.settings_manager.settings.fileName()).parent),
                            ('FFmpeg 폴더 열기', ffmpeg_directory())):
            button = QPushButton(title)
            button.setIcon(fluent_icon('folder', '#4263EB'))
            button.clicked.connect(lambda checked=False, target=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))))
            button.setEnabled(path.is_dir())
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return widget

    def choose_folder(self):
        if not self.folder_browse.isEnabled():
            return
        picker = SourceFileDialog(self, tr('파일 추가 시작 폴더'), self.folder_path.text())
        picker.setOption(SourceFileDialog.Option.DontUseNativeDialog, True)
        picker.setOption(SourceFileDialog.Option.ShowDirsOnly, True)
        picker.setFileMode(SourceFileDialog.FileMode.Directory)
        if picker.exec() == SourceFileDialog.DialogCode.Accepted and picker.selectedFiles():
            folder = picker.selectedFiles()[0]
            self.owner.input_path_edit.setText(folder)
            self.owner.settings_manager.save_settings({'input_folder': folder})
        picker.deleteLater()

    def help_page(self):
        widget, layout = self.page('도움말', '기능별 동작과 설정 방법을 확인하세요.')
        self.help_sections = {}
        for key, title in HELP_TITLES.items():
            heading = caption(title, heading=True)
            self.help_sections[key] = heading
            layout.addWidget(heading)
            layout.addWidget(caption(HELP_DETAILS[key]))
        for key, title, description in (
            ('bitrates', 'VBR과 오디오 비트레이트', 'VBR은 원본 대비 비율(%)과 직접 입력(kb/s) 중 선택합니다. 비율 기본값은 80%이며 1~200%로 수정하고 프리셋에 저장할 수 있습니다. 6000은 6000 kb/s입니다. AAC LC의 최대값은 MP4의 해당 오디오 트랙 헤더에서 읽습니다. 순간 패킷 값으로 대체하지 않으며 기록된 최대값이 없으면 —로 표시합니다. 파일은 먼저 목록에 담고 기본 정보부터 최대 4개씩 병렬 분석합니다. MKV 등에 평균값이 없으면 한 번의 추가 패킷 분석으로 누락된 비디오·오디오 값을 함께 계산합니다. 실패·중지 항목은 우클릭의 정보 다시 분석으로 재시도합니다.'),
            ('time', '예상 변환 시간', '파일을 추가하거나 인코딩 설정을 바꾸면 짧은 샘플을 실제로 변환해 영상별 예상 시간을 계산합니다. 행과 오른쪽 합계에서 확인할 수 있습니다. 합계는 개별 파일의 시간을 더한 값이며 동시 작업 수·PC 부하·영상 구간에 따라 실제 완료 시간은 달라집니다. 같은 파일과 인코딩 설정의 샘플은 용량 확인에도 재사용합니다. 계산에 실패한 항목은 —로 표시하고 툴팁에 이유를 남깁니다.'),
            ('estimate', '예상 용량 확인', '긴 영상은 10·50·90% 부근의 각 4초, 12초 이하는 전체를 샘플로 변환합니다. 원본 대비 95% 이상 예상되거나 예측에 실패하면 즉시 멈춥니다. 설정 조정·주의 파일 제외·그대로 진행 중 선택하며, 선택은 이후 주의 파일에도 적용됩니다. 추정값과 실제 크기는 다를 수 있습니다. 완료한 예측은 목록을 유지하는 동안 캐시합니다. 중지 후 같은 파일·인코딩 설정으로 다시 시작하면 재사용하고, 미완료 항목이나 변경된 파일·설정만 다시 검사합니다.'),
            ('queue', '목록과 처리 결과', '목록에는 첫 번째 실제 비디오와 첫 번째 오디오의 코덱·비트레이트를 각각 표시합니다. 누락된 값은 —, 전체 비트레이트는 별도로 표시합니다. 완료 후 원본/결과 크기와 증감률을 확인하세요. 결과가 더 작지 않아 제외되면 원본은 유지됩니다. 완료 항목 따라가기는 선택을 바꾸지 않고 스크롤합니다.'),
            ('sources', '파일·폴더 추가와 선택', '빈 목록이나 목록의 빈 공간을 누르면 파일과 폴더를 함께 추가할 수 있습니다. 폴더를 더블클릭하면 내부로 이동하며, 현재 폴더 추가로 폴더 전체를 담습니다. 하위 폴더도 검색하고 중복 파일과 앱이 만든 결과는 제외합니다. 결과 파일을 직접 선택하면 다시 변환할 수 있습니다. 선택한 파일만 변환을 켜면 선택된 항목만 처리합니다.'),
            ('presets', '기본·사용자 프리셋', '아카이빙은 원본 해상도의 HEVC MP4와 오디오 복사를 사용하고 더 작아진 결과만 보관합니다. 1080p·720p는 H.264/AAC MP4이며 작은 원본을 확대하지 않습니다. 저장 버튼으로 현재 인코딩 설정에 이름을 붙이고 다시 적용할 수 있습니다. 언어·완료음·용량 예측·GPU 처리 선호는 프리셋과 별도로 유지됩니다.'),
            ('gpu', 'GPU 처리와 HDR', 'GPU 디코딩·리사이즈 가속은 지원되는 입력을 NVDEC·CUDA로 처리합니다. CUDA 관련 실패일 때만 소프트웨어 디코딩으로 한 번 재시도하며 NVENC 품질 설정을 유지합니다. HDR 아카이빙은 10비트·색상 태그를 유지하고, H.264 출력은 BT.709 SDR로 톤 매핑합니다. 동적 HDR 메타데이터나 추가 트랙 보존은 보장하지 않습니다.'),
            ('stop', '중지와 원본 보호', '변환 중에는 목록에서 중지할 항목을 선택하고 선택 중지를 누르세요. 선택한 실행·대기 항목만 중지하고 나머지는 계속 변환합니다. 여러 항목은 Ctrl·Shift로 선택합니다. 전체를 중지하려면 목록 우클릭 메뉴의 전체 작업 중지를 사용합니다. 실행·대기 작업이 모두 정리된 뒤 다시 시작할 수 있습니다. 성공한 결과만 최종 이름으로 저장하고 기존 결과를 덮어쓰지 않습니다. 원본은 자동 삭제하지 않으며, 감소율은 두 파일의 크기 비교입니다.'),
            ('preferences', '언어·완료음·폴더 설정', '일반에서 한국어·영어와 완료음을 바꿉니다. 언어를 바꿔도 파일 선택과 진행 중인 작업은 유지됩니다. 완료음은 실제 변환 배치가 끝날 때 한 번 재생하며 중지나 예측만 마친 경우에는 재생하지 않습니다. 폴더에서 파일 추가 시작 위치를 지정할 수 있으며 결과는 원본과 같은 폴더에 저장됩니다. 변경 사항은 즉시 저장됩니다.'),
        ):
            heading = caption(title, heading=True)
            self.help_sections[key] = heading
            layout.addWidget(heading)
            layout.addWidget(caption(description))
        layout.addStretch()
        return widget

    def show_help(self, key):
        self.select_category('help')
        if key in self.help_sections:
            QTimer.singleShot(0, lambda: self.categories['help'][2].verticalScrollBar().setValue(
                max(0, self.help_sections[key].y() - 8)))

    def refresh_controls(self):
        busy = self.owner.converting or self.owner.scanning or self.owner.preflighting or self.owner._close_pending
        self.folder_browse.setEnabled(not busy)
        self.busy_hint.setVisible(busy)
