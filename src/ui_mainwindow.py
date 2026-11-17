"""VideoBatchConverter 3: a light, task-focused desktop workspace."""

from collections import Counter
import math
import os
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThreadPool, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QInputDialog,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidgetItem, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from .settings_dialog import SettingsDialog
from .brand_dialog import BrandDialog, ConfirmExitDialog
from .media_summary import source_summary
from .completion_sound import play_completion_sound
from .bitrate import BITRATE_UNIT, normalize_bitrate_settings, target_bitrate_kbps, source_video_bitrate
from .size_estimator import SizeEstimateWorker
from .time_preview import TimePreview
from .estimate_dialog import EstimateDialog
from .ffmpeg_downloader import FFmpegDownloaderDialog
from .fluent_icons import app_icon, fluent_icon
from .encoding_progress import EncodingProgressBar
from .profiles import APP_VERSION, CODECS, HELP_TEXTS, PRESETS, PRESET_DISPLAY, PRESET_KEYS, validate_settings, validate_media_settings
from .paths import ffmpeg_directory
from .queue_widgets import ClickableEmptyState, QueueItemDelegate, QueueListWidget, PATH_ROLE, INFO_ROLE, STATE_ROLE, DETAIL_ROLE, ESTIMATE_ROLE, TIME_ESTIMATE_ROLE, time_text, time_estimate_text, queue_details
from .settings import SettingsManager
from .source_picker import SourceFileDialog, SourcePickerDialog
from .theme import stylesheet
from .text_widgets import ReadableLabel
from .update_checker import UpdateCheckWorker
from .window_chrome import FramelessWindow, TitleBar
from .worker import FileConversionTask, QueueScanWorker, WorkerSignals, get_ffmpeg_path, video_stream, VIDEO_EXTENSIONS
from .i18n import get_language, language_manager, tr
from .localized_widgets import QCheckBox, QComboBox, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTextEdit, QToolButton

def label(text, name=None):
    widget = ReadableLabel(text)
    widget.setContentsMargins(0, 1, 0, 2)
    if name:
        widget.setObjectName(name)
    return widget


def media_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except (ValueError, TypeError):
        return 0.0


def card():
    widget = QFrame()
    widget.setObjectName('card')
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(18, 17, 18, 17)
    layout.setSpacing(12)
    return widget, layout


class MainWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.is_initialized = False
        self._is_applying_preset = False
        self.converting = False
        self.stop_requested = False
        self.scanning = False
        self.preflighting = False
        self.estimate_worker = None
        self.estimate_cache = {}
        self._pending_batch = None
        self._estimated_skips = 0
        self._close_pending = False
        self.settings_dialog = None
        self.time_preview = None
        self._preview_pending_batch = None
        self.thread_pool = QThreadPool(self)
        self.active_tasks = []
        self.stopping_paths = set()
        self.scan_worker = None
        self._scan_refresh_timer = QTimer(self)
        self._scan_refresh_timer.setSingleShot(True)
        self._scan_refresh_timer.setInterval(50)
        self._scan_refresh_timer.timeout.connect(self.refresh_queue)
        self.update_worker = None
        self.queue_items = {}
        self.queue_states = Counter()
        self.results = Counter()
        self.task_progress = {}
        self.task_weights = {}
        self._weighted_progress = 0.0
        self._weight_total = 1.0
        self.result_input_bytes = 0
        self.result_output_bytes = 0
        self.total_files_count = 0
        self.completed_files_count = 0
        self.settings_manager = SettingsManager()
        language_manager().set_language(self.settings_manager.load_settings().get('language', 'ko'))
        self.log_entries = []
        self.user_presets = self.settings_manager.load_user_presets()
        self.setWindowTitle(f'VideoBatchConverter {APP_VERSION}')
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1000, 680)
        self.resize(1240, 850)
        self.build_ui()
        self.setStyleSheet(stylesheet())
        self.load_app_settings()
        self.time_preview = TimePreview(self)
        self.time_preview.idle.connect(self.begin_pending_conversion)
        self.refresh_queue()
        language_manager().changed.connect(self.on_language_changed)
        if self.check_and_prepare_ffmpeg():
            self.is_initialized = True
            QTimer.singleShot(500, self.check_for_updates)
        else:
            QTimer.singleShot(0, self.close)

    def build_ui(self):
        self.title_bar = TitleBar(self, APP_VERSION)
        self.surface_layout.addWidget(self.title_bar)
        divider = QFrame()
        divider.setObjectName('divider')
        self.surface_layout.addWidget(divider)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 12, 20, 16)
        body_layout.setSpacing(12)
        header = QHBoxLayout()
        titles = QHBoxLayout()
        titles.setSpacing(12)
        titles.addWidget(label('영상 일괄 변환', 'workspaceTitle'))
        titles.addWidget(label('코덱 통일 · 고효율 보관', 'muted'))
        titles.addStretch()
        header.addLayout(titles, 1)
        self.update_button = self.make_button('새 버전 다운로드', 'sync', lambda: QDesktopServices.openUrl(
            QUrl('https://github.com/deuxdoom/VideoBatchConverter/releases/latest')), '#4263EB')
        self.update_button.hide()
        header.addWidget(self.update_button, 0, Qt.AlignmentFlag.AlignTop)
        self.state_badge = label('준비 완료', 'statusBadge')
        header.addWidget(self.state_badge, 0, Qt.AlignmentFlag.AlignTop)
        body_layout.addLayout(header)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.queue_panel = self.build_queue()
        self.splitter.addWidget(self.queue_panel)
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(330)
        self.sidebar.setMaximumWidth(440)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)
        sidebar_layout.addWidget(self.build_settings(), 1)
        sidebar_layout.addWidget(self.build_progress())
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([780, 390])
        body_layout.addWidget(self.splitter, 1)
        body_layout.addWidget(self.build_encoding_footer())
        self.surface_layout.addWidget(body, 1)
        self.setAcceptDrops(True)
        self.add_shortcut('Ctrl+O', self.add_files)
        self.add_shortcut('Ctrl+Shift+O', self.add_folder)
        delete_action = QAction(self.file_list_widget)
        delete_action.setShortcut(QKeySequence('Delete'))
        delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        delete_action.triggered.connect(self.remove_selected_files)
        self.file_list_widget.addAction(delete_action)

    def add_shortcut(self, sequence, callback):
        action = QAction(self)
        action.setShortcut(QKeySequence(sequence))
        action.triggered.connect(callback)
        self.addAction(action)

    def make_button(self, text, icon_name, callback, color='#62708A'):
        button = QPushButton(text)
        button.setIcon(fluent_icon(icon_name, color))
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def build_queue(self):
        panel, layout = card()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        panel.setMinimumWidth(335)
        top = QHBoxLayout()
        top.addWidget(label('01  변환할 영상', 'sectionTitle'))
        self.queue_count_label = label('0개', 'countBadge')
        top.addWidget(self.queue_count_label)
        top.addStretch()
        self.add_file_btn = self.make_button('파일 추가', 'file-add', self.add_files, '#4263EB')
        self.input_browse_btn = self.make_button('폴더 추가', 'folder-add', self.add_folder, '#187967')
        self.add_file_btn.setToolTip('동영상 파일 추가 (Ctrl+O)')
        self.input_browse_btn.setToolTip('하위 폴더까지 검색 (Ctrl+Shift+O)')
        top.addWidget(self.add_file_btn)
        top.addWidget(self.input_browse_btn)
        self.clear_btn = QToolButton()
        self.clear_btn.setIcon(fluent_icon('delete'))
        self.clear_btn.setToolTip('목록 비우기')
        self.clear_btn.setAccessibleName('목록 비우기')
        self.clear_btn.clicked.connect(self.clear_queue)
        top.addWidget(self.clear_btn)
        layout.addLayout(top)
        summary = QHBoxLayout()
        self.queue_summary_label = label('대기 0', 'muted')
        self.queue_summary_label.setFixedHeight(self.fontMetrics().height() + 6)
        self.queue_summary_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        summary.addWidget(self.queue_summary_label)
        summary.addStretch()
        self.follow_results_check = QCheckBox('완료 항목 따라가기')
        self.follow_results_check.setChecked(True)
        self.follow_results_check.setToolTip('선택을 유지하며 최근 처리한 행으로 스크롤합니다.')
        summary.addWidget(self.follow_results_check)
        layout.addLayout(summary)
        self.empty_state = ClickableEmptyState()
        self.empty_state.activated.connect(self.add_sources)
        self.empty_state.setObjectName('dropZone')
        self.empty_state.setMinimumHeight(150)
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(16, 24, 16, 24)
        empty_layout.addStretch()
        empty_icon = QLabel()
        empty_icon.setPixmap(fluent_icon('video', '#4263EB').pixmap(52, 52))
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        title = label('변환할 영상을 여기에 놓으세요', 'sectionTitle')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(title)
        hint = label('여기를 클릭해 파일·폴더를 선택하거나\n탐색기에서 끌어 놓으세요.', 'muted')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(hint)
        empty_layout.addSpacing(12)
        support = label('여러 코덱의 영상 자동 분석 · 하위 폴더 포함', 'muted')
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(support)
        self.empty_icon = empty_icon
        self.empty_hint = hint
        self.empty_support = support
        for child in (empty_icon, title, hint, support):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        empty_layout.addStretch()
        layout.addWidget(self.empty_state, 1)
        self.file_list_widget = QueueListWidget()
        self.file_list_widget.add_requested.connect(self.add_sources)
        self.file_list_widget.setItemDelegate(QueueItemDelegate(self.file_list_widget))
        self.file_list_widget.setAccessibleName('변환할 영상 목록')
        self.file_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list_widget.setUniformItemSizes(True)
        self.file_list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.file_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_list_widget.currentItemChanged.connect(self.update_file_info_panel)
        self.file_list_widget.itemSelectionChanged.connect(self.refresh_selection)
        self.file_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list_widget.customContextMenuRequested.connect(self.queue_context_menu)
        layout.addWidget(self.file_list_widget, 1)
        self.input_path_edit = QLineEdit(panel)
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText('추가한 폴더 경로가 여기에 표시됩니다')
        self.input_path_edit.setAccessibleName('마지막으로 추가한 폴더')
        self.input_path_edit.hide()
        info = QFrame()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        self.info_filename_label = label('목록에서 파일을 선택하면 정보를 표시합니다.', 'muted')
        self.info_filename_label.setParent(info)
        self.info_filename_label.hide()
        self.info_filename_label.setWordWrap(True)
        self.info_summary_label = label('해상도 · 용량 · 재생 시간', 'muted')
        self.info_summary_label.setWordWrap(True)
        info.setParent(panel)
        info.hide()
        selection = QHBoxLayout()
        self.selection_only_check = QCheckBox('선택한 파일만 변환')
        self.selection_only_check.toggled.connect(self.refresh_selection)
        selection.addWidget(self.selection_only_check)
        selection.addStretch()
        self.remove_btn = QToolButton()
        self.remove_btn.setIcon(fluent_icon('dismiss'))
        self.remove_btn.setToolTip('선택 삭제')
        self.remove_btn.setAccessibleName('선택 삭제')
        self.remove_btn.clicked.connect(self.remove_selected_files)
        selection.addWidget(self.remove_btn)
        layout.addLayout(selection)
        self.selection_label = label('전체 목록을 변환합니다.', 'muted')
        self.selection_label.setParent(panel)
        self.selection_label.hide()
        self.latest_result_label = label('완료한 파일은 목록에 남아 계속 확인할 수 있습니다.', 'muted')
        self.latest_result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.latest_result_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.queue_details_stack = QStackedWidget(panel)
        self.queue_details_stack.addWidget(self.info_summary_label)
        self.queue_details_stack.addWidget(self.latest_result_label)
        # Row metadata and tooltips already show this information. Keep the
        # canonical labels for selection/language updates without a second footer.
        self.queue_details_stack.hide()
        return panel

    def build_settings(self):
        panel, outer = card()
        panel.setMinimumWidth(330)
        heading = QHBoxLayout()
        heading.addWidget(label('02  변환 설정', 'sectionTitle'))
        heading.addStretch()
        self.preset_label = label('아카이빙', 'muted')
        self.preset_label.setMaximumWidth(155)
        heading.addWidget(self.preset_label)
        outer.addLayout(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 7, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(label('프리셋', 'fieldLabel'))
        preset_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.setAccessibleName('프리셋 선택')
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preset_combo.setMinimumContentsLength(8)
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.rebuild_preset_combo()
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        preset_row.addWidget(self.preset_combo, 1)
        self.save_preset_btn = QToolButton()
        self.save_preset_btn.setObjectName('savePresetButton')
        self.save_preset_btn.setText('저장')
        self.save_preset_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.save_preset_btn.setIcon(fluent_icon('save', '#4263EB'))
        self.save_preset_btn.setToolTip('현재 설정을 내 프리셋으로 저장')
        self.save_preset_btn.setAccessibleName('사용자 프리셋 저장')
        self.save_preset_btn.clicked.connect(self.save_user_preset)
        preset_row.addWidget(self.save_preset_btn)
        self.delete_preset_btn = QToolButton()
        self.delete_preset_btn.setIcon(fluent_icon('delete'))
        self.delete_preset_btn.setToolTip('선택한 내 프리셋 삭제')
        self.delete_preset_btn.setAccessibleName('사용자 프리셋 삭제')
        self.delete_preset_btn.clicked.connect(self.delete_user_preset)
        preset_row.addWidget(self.delete_preset_btn)
        content_layout.addLayout(preset_row)
        self.detail_controls = []
        fields = QGridLayout()
        fields.setHorizontalSpacing(12)
        fields.setVerticalSpacing(9)
        self.codec_combo = self.combo(CODECS)
        self.resolution_combo = self.combo(['원본 유지', '1080p', '720p'])
        self.output_format_combo = self.combo(['mp4', 'mkv'])
        self.audio_option_combo = self.combo(['원본 유지 (Passthrough)', 'AAC 128kbps', 'AAC 192kbps', 'AAC 256kbps'])
        self.quality_edit = QLineEdit('8000')
        self.quality_edit.setMaxLength(12)
        self.quality_edit.setAccessibleName('품질 또는 비트레이트')
        self.detail_controls.append(self.quality_edit)
        self.quality_field = self.field('품질 · CQP (0~51)', self.quality_edit, 'quality_value')
        self.bitrate_mode_combo = self.combo(['원본 대비 (%)', '직접 입력 (kb/s)'])
        self.bitrate_mode_combo.setAccessibleName('비트레이트 설정 방식')
        self.bitrate_mode_combo.currentIndexChanged.connect(self.on_bitrate_mode_changed)
        self.quality_field.layout().insertWidget(1, self.bitrate_mode_combo)
        self.source_bitrate_percent_spinbox = QSpinBox()
        self.source_bitrate_percent_spinbox.setRange(1, 200)
        self.source_bitrate_percent_spinbox.setValue(80)
        self.source_bitrate_percent_spinbox.setSuffix(' %')
        self.source_bitrate_percent_spinbox.setAccessibleName('원본 대비 비트레이트 비율 (%)')
        self.detail_controls.append(self.source_bitrate_percent_spinbox)
        self.quality_field.layout().insertWidget(2, self.source_bitrate_percent_spinbox)
        self.auto_bitrate_label = label('영상별 원본 비트레이트의 80%', 'muted')
        self.auto_bitrate_label.setWordWrap(True)
        self.quality_field.layout().addWidget(self.auto_bitrate_label)
        self.auto_bitrate_label.hide()
        fields.addWidget(self.field('비디오 코덱', self.codec_combo, 'codec'), 0, 0, 1, 2)
        fields.addWidget(self.field('최대 해상도', self.resolution_combo, 'resolution'), 1, 0)
        fields.addWidget(self.field('출력 형식', self.output_format_combo, 'output_format'), 1, 1)
        fields.addWidget(self.quality_field, 2, 0)
        fields.addWidget(self.field('오디오', self.audio_option_combo, 'audio_option'), 2, 1)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)
        content_layout.addLayout(fields)
        self.adaptive_quality_check = QCheckBox('원본별 화질 자동 조절')
        self.adaptive_quality_check.setToolTip(HELP_TEXTS['quality_value'])
        self.detail_controls.append(self.adaptive_quality_check)
        content_layout.addWidget(self.adaptive_quality_check)
        self.time_summary_label = label('예상 시간 합계 · —', 'muted')
        self.time_summary_label.setWordWrap(True)
        self.time_summary_label.setToolTip('파일별 샘플 시간을 더한 값입니다. 동시 작업 수와 PC 부하에 따라 실제 완료 시간은 달라집니다.')
        content_layout.addWidget(self.time_summary_label)
        # Construct once; SettingsDialog adopts these same controls when opened.
        self.advanced_panel = QWidget(self)
        advanced = QGridLayout(self.advanced_panel)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setHorizontalSpacing(12)
        self.preset_option_combo = self.combo(['p1 (빠름, 낮은 품질)', 'p2', 'p3', 'p4 (중간)', 'p5', 'p6', 'p7 (느림, 고품질)'])
        self.rate_control_combo = self.combo(['VBR', 'CQP', 'CBR'])
        self.suffix_edit = QLineEdit('_h265')
        self.suffix_edit.setMaxLength(60)
        self.detail_controls.append(self.suffix_edit)
        self.parallel_jobs_spinbox = QSpinBox()
        self.parallel_jobs_spinbox.setRange(1, max(2, min(32, self.thread_pool.maxThreadCount())))
        self.detail_controls.append(self.parallel_jobs_spinbox)
        self.gpu_field = self.field('GPU 프리셋', self.preset_option_combo, 'preset')
        advanced.addWidget(self.gpu_field, 0, 0)
        advanced.addWidget(self.field('압축 방식', self.rate_control_combo, 'rate_control'), 0, 1)
        advanced.addWidget(self.field('파일 접미사', self.suffix_edit, 'suffix'), 1, 0)
        advanced.addWidget(self.field('동시 작업 수', self.parallel_jobs_spinbox, 'parallel_jobs'), 1, 1)
        self.keep_smaller_check = QCheckBox('원본보다 커진 결과는 보관하지 않음')
        self.keep_smaller_check.setToolTip('원본보다 작지 않은 결과만 제외합니다. 원본은 유지합니다.')
        self.detail_controls.append(self.keep_smaller_check)
        advanced.addWidget(self.keep_smaller_check, 2, 0, 1, 2)
        self.estimate_size_check = QCheckBox('변환 전 예상 용량 확인')
        self.estimate_size_check.setChecked(True)
        self.detail_controls.append(self.estimate_size_check)
        advanced.addWidget(self.estimate_size_check, 3, 0, 1, 2)
        self.gpu_processing_check = QCheckBox('GPU 디코딩·리사이즈 가속')
        self.gpu_processing_check.setChecked(True)
        self.gpu_processing_check.setToolTip('NVDEC·CUDA로 가속합니다.\n사용할 수 없으면 소프트웨어 디코딩합니다.')
        self.detail_controls.append(self.gpu_processing_check)
        advanced.addWidget(self.gpu_processing_check, 4, 0, 1, 2)
        self.completion_sound_check = QCheckBox('완료음', self)
        self.completion_sound_check.setChecked(True)
        self.completion_sound_check.hide()
        self.completion_sound_check.toggled.connect(lambda checked: self.settings_manager.save_settings({'completion_sound': checked})
                                                   if self.is_initialized else None)
        advanced.setColumnStretch(0, 1)
        advanced.setColumnStretch(1, 1)
        self.advanced_panel.hide()
        preview = QFrame()
        self.output_preview_frame = preview
        preview.setObjectName('outputPreview')
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(12, 9, 12, 9)
        preview_layout.setSpacing(3)
        preview_layout.addWidget(label('저장 미리보기 · 원본과 같은 폴더', 'fieldLabel'))
        self.output_preview_label = QLabel()
        self.output_preview_label.setWordWrap(True)
        self.output_preview_label.setTextFormat(Qt.TextFormat.PlainText)
        preview_layout.addWidget(self.output_preview_label)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(preview)
        for control in self.detail_controls:
            if isinstance(control, QComboBox):
                control.currentTextChanged.connect(self.on_setting_changed)
            elif isinstance(control, QSpinBox):
                control.valueChanged.connect(self.on_setting_changed)
            elif isinstance(control, QCheckBox):
                control.toggled.connect(self.on_setting_changed)
            else:
                control.textChanged.connect(self.on_setting_changed)
        self.codec_combo.currentTextChanged.connect(self.on_codec_changed)
        self.rate_control_combo.currentTextChanged.connect(self.on_rate_control_changed)
        return panel

    def combo(self, values):
        widget = QComboBox()
        for value in values:
            widget.addItem(tr(value), value)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumContentsLength(8)
        self.detail_controls.append(widget)
        return widget

    @staticmethod
    def select_value(control, value):
        index = control.findData(value)
        if index >= 0:
            control.setCurrentIndex(index)

    def on_language_changed(self, language):
        # Translate captions without emitting setting changes or recreating workers.
        for control in self.detail_controls:
            if isinstance(control, QComboBox):
                blocked = control.blockSignals(True)
                for index in range(control.count()):
                    control.setItemText(index, tr(control.itemData(index)))
                control.blockSignals(blocked)
        self.rebuild_preset_combo(self.preset_combo.currentData() or '')
        self.update_preset_caption()
        for path, item in self.queue_items.items():
            self.update_item_text(item)
        self.file_list_widget.viewport().update()
        self.log_edit.setPlainText('\n'.join(tr(message) for message in self.log_entries) + ('\n' if self.log_entries else ''))
        if self.queue_details_stack.currentWidget() is self.info_summary_label:
            self.update_file_info_panel(self.file_list_widget.currentItem())
        else:
            self.update_output_preview()
        self.update_compact_layout()
        self.update_time_summary()
        self.settings_manager.save_settings({'language': language})

    def field(self, text, control, help_key):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        title = label(text, 'fieldLabel')
        title.setBuddy(control)
        row.addWidget(title)
        help_button = QToolButton()
        help_button.setIcon(fluent_icon('info', '#7786A2'))
        help_button.setIconSize(QSize(13, 13))
        help_button.setFixedSize(18, 18)
        help_button.setToolTip(HELP_TEXTS[help_key])
        help_button.setAccessibleName(text + ' 도움말')
        help_button.clicked.connect(lambda: self.show_settings_dialog(category='help', help_key=help_key))
        row.addWidget(help_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(control)
        control.setAccessibleName(text)
        control.setToolTip(HELP_TEXTS[help_key])
        return container

    def build_progress(self):
        # Actions stay below the settings; the former 03 card is removed.
        panel = QWidget()
        panel.setObjectName('conversionActions')
        buttons = QHBoxLayout(panel)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.stop_button = self.make_button('선택 중지', 'stop', self.stop_selected_conversion, '#B3424F')
        self.stop_button.setObjectName('stopButton')
        buttons.addWidget(self.stop_button)
        self.start_button = self.make_button('변환 시작', 'play', self.start_conversion, '#FFFFFF')
        self.start_button.setObjectName('primaryButton')
        buttons.addWidget(self.start_button, 1)
        return panel

    def build_encoding_footer(self):
        panel, layout = card()
        self.encoding_footer = panel
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(5)
        row = QHBoxLayout()
        self.progress_title = label('인코딩 진행', 'sectionTitle')
        row.addWidget(self.progress_title)
        self.encoding_status_label = label('분석 후 선택한 코덱으로 일괄 변환합니다.', 'muted')
        self.encoding_status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.encoding_status_label, 1)
        self.progress_summary = label('파일을 추가하고 원하는 프리셋을 선택하세요.', 'muted')
        self.progress_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.progress_summary, 1)
        # General hints use the same compact status line instead of a third card.
        self.status_label = self.encoding_status_label
        self.progress_percent_label = label('0%', 'countBadge')
        row.addWidget(self.progress_percent_label)
        self.log_toggle = QToolButton()
        self.log_toggle.setText('작업 기록')
        self.log_toggle.setIcon(fluent_icon('chevron-down'))
        self.log_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.log_toggle.setCheckable(True)
        self.log_toggle.toggled.connect(self.toggle_log)
        row.addWidget(self.log_toggle)
        layout.addLayout(row)
        self.overall_progress_bar = EncodingProgressBar()
        self.overall_progress_bar.valueChanged.connect(lambda value: self.progress_percent_label.setText(f'{value}%'))
        layout.addWidget(self.overall_progress_bar)
        self.log_dialog = BrandDialog('작업 기록', self, width=760)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setAccessibleName('작업 기록')
        self.log_edit.document().setMaximumBlockCount(1500)
        self.log_edit.setMinimumHeight(210)
        self.log_dialog.content.addWidget(self.log_edit)
        self.log_dialog.add_action('닫기', self.log_dialog.reject, default=True)
        self.log_dialog.finish_layout()
        self.log_dialog.finished.connect(lambda _: self.log_toggle.setChecked(False))
        return panel

    def toggle_log(self, checked):
        self.log_dialog.setVisible(checked)
        self.log_toggle.setIcon(fluent_icon('chevron-up' if checked else 'chevron-down'))
        self.update_compact_layout()

    def dragEnterEvent(self, event):
        if not self.converting and not self.scanning and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.converting and not self.scanning:
            self.add_paths_to_queue([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
            event.acceptProposedAction()

    def add_sources(self):
        if self.converting or self.scanning or self.preflighting or self._close_pending:
            return
        picker = SourcePickerDialog(self.input_path_edit.text(), self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self.add_paths_to_queue(picker.paths)

    def add_files(self):
        if self.converting or self.scanning or self.preflighting:
            return
        picker = SourceFileDialog(self, tr('동영상 파일 추가'), self.input_path_edit.text(),
                                  tr('동영상 (' + ' '.join('*' + ext for ext in sorted(VIDEO_EXTENSIONS)) + ')'))
        picker.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        picker.setFileMode(QFileDialog.FileMode.ExistingFiles)
        files = picker.selectedFiles() if picker.exec() == QDialog.DialogCode.Accepted else []
        picker.deleteLater()
        if files:
            self.add_paths_to_queue(files)

    def add_folder(self):
        if self.converting or self.scanning or self.preflighting:
            return
        picker = SourceFileDialog(self, tr('하위 폴더까지 검색할 폴더 선택'), self.input_path_edit.text())
        picker.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        picker.setOption(QFileDialog.Option.ShowDirsOnly, True)
        picker.setFileMode(QFileDialog.FileMode.Directory)
        folders = picker.selectedFiles() if picker.exec() == QDialog.DialogCode.Accepted else []
        folder = folders[0] if folders else ''
        picker.deleteLater()
        if folder:
            self.input_path_edit.setText(folder)
            self.add_paths_to_queue([folder])

    def add_paths_to_queue(self, paths, *, reanalyze=False):
        if self.converting or self.scanning or self.preflighting or not paths:
            return
        first = Path(paths[0])
        self.input_path_edit.setText(str(first if first.is_dir() else first.parent))
        self.scanning = True
        self.time_preview.pause()
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setIndeterminate(True)
        self.progress_percent_label.setText('분석 중')
        self.encoding_status_label.setText('영상 코덱·해상도·비트 깊이·재생 시간을 분석합니다.')
        self.state_badge.setText('파일 검색 중')
        self.progress_title.setText('영상 검색 중')
        self.status_label.setText('영상을 분석하고 있습니다. 중지 버튼으로 검색을 취소할 수 있습니다.')
        existing = set(self.queue_items)
        if reanalyze:
            existing.difference_update(str(Path(path).resolve()) for path in paths)
        self.scan_worker = QueueScanWorker(paths, existing, self)
        self.scan_worker.queued.connect(self.add_queued_file)
        self.scan_worker.analyzing.connect(self.set_item_state)
        self.scan_worker.details.connect(self.update_scanned_file)
        self.scan_worker.found.connect(self.update_scanned_file)
        self.scan_worker.rejected.connect(self.reject_scanned_file)
        self.scan_worker.status.connect(self.set_scan_status)
        self.scan_worker.summary.connect(self.scan_summary)
        self.scan_worker.finished.connect(self.scan_finished)
        self.refresh_controls()
        self.scan_worker.start()

    def set_scan_status(self, message):
        self.status_label.setText(message)
        self.status_label.setToolTip(message)

    def add_scanned_file(self, path, info, *, refresh=True):
        path = str(Path(path).resolve())
        if path in self.queue_items:
            return
        item = QListWidgetItem()
        item.setData(PATH_ROLE, path)
        item.setData(INFO_ROLE, info)
        item.setToolTip(path)
        self.queue_items[path] = item
        self.file_list_widget.addItem(item)
        self.set_item_state(path, '대기')
        if refresh:
            self.refresh_queue()
        if not self.scanning:
            self.time_preview.schedule()

    def add_queued_file(self, path, info):
        if path not in self.queue_items:
            self.add_scanned_file(path, info, refresh=False)
        else:
            self.queue_items[path].setData(INFO_ROLE, info)
        self.queue_items[path].setData(ESTIMATE_ROLE, None)
        self.queue_items[path].setData(TIME_ESTIMATE_ROLE, None)
        self.set_item_state(path, '정보 대기')
        if self.file_list_widget.count() == 1:
            self.refresh_queue()
        if not self._scan_refresh_timer.isActive():
            self._scan_refresh_timer.start()

    def update_scanned_file(self, path, info):
        item = self.queue_items.get(path)
        if item is None:
            return
        item.setData(INFO_ROLE, info)
        self.set_item_state(path, '추가 분석 중' if info.get('_extra_pending') else '대기')
        if item is self.file_list_widget.currentItem():
            self.update_file_info_panel(item)
            self.update_quality_label()
        if not self._scan_refresh_timer.isActive():
            self._scan_refresh_timer.start()

    def reject_scanned_file(self, path, reason, remove):
        item = self.queue_items.get(path)
        if item is None:
            return
        if remove:
            self.queue_states[item.data(STATE_ROLE)] -= 1
            self.queue_items.pop(path)
            self.file_list_widget.takeItem(self.file_list_widget.row(item))
        else:
            info = item.data(INFO_ROLE) or {}
            info['_scan_pending'] = False
            info['_scan_error'] = reason
            item.setData(INFO_ROLE, info)
            self.set_item_state(path, '분석 실패')
        self._scan_refresh_timer.start()

    def retry_file_info(self):
        paths = [item.data(PATH_ROLE) for item in self.file_list_widget.selectedItems()
                 if item.data(STATE_ROLE) in ('분석 실패', '분석 중지')]
        if paths:
            self.add_paths_to_queue(paths, reanalyze=True)

    def scan_summary(self, added, skipped):
        message = f'분석 완료 · {added}개 추가 / {skipped}개 제외 (읽기 실패·기존 변환 결과 등)'
        if self.scan_worker and self.scan_worker.was_cancelled:
            message = f'분석 중지 · 영상 {added}개 확인 · 미확인 항목은 정보 다시 분석으로 재시도하세요.'
        self.append_log(message)
        self.progress_summary.setText(f'분석 완료 · {added}개 추가 · {skipped}개 제외')

    def scan_finished(self):
        self.scanning = False
        self._scan_refresh_timer.stop()
        for path, item in self.queue_items.items():
            info = item.data(INFO_ROLE) or {}
            if info.get('_scan_pending') or info.get('_extra_pending'):
                self.set_item_state(path, '분석 중지')
        self.overall_progress_bar.setIndeterminate(False)
        self.overall_progress_bar.setActive(False)
        self.progress_percent_label.setText('0%')
        self.encoding_status_label.setText('프리셋을 선택하면 각 원본에 맞춰 처리합니다.')
        self.state_badge.setText('준비 완료')
        self.progress_title.setText('변환 준비')
        self.status_label.setText('원본과 같은 폴더에 저장합니다. 기존 결과 파일은 덮어쓰지 않습니다.')
        self.refresh_queue()
        self.time_preview.schedule()

    def set_item_state(self, path, state):
        item = self.queue_items.get(path)
        if item is None:
            return
        old = item.data(STATE_ROLE)
        old_category = '진행' if old and '%' in old else old
        category = '진행' if '%' in state else state
        if old_category != category:
            if old_category:
                self.queue_states[old_category] -= 1
            self.queue_states[category] += 1
        item.setData(STATE_ROLE, state)
        details = source_summary(item.data(INFO_ROLE))
        item.setData(DETAIL_ROLE, details)
        self.update_item_text(item)
        color = '#4263EB' if '%' in state else '#62708A'
        name = 'video'
        if state == '완료':
            name, color = 'checkmark', '#187967'
        elif state == '실패':
            name, color = 'warning', '#B3424F'
        elif state in ('중지', '중지 중'):
            name = 'stop'
        elif state in ('결과 제외', '용량 주의', '예측 실패', '예측 제외'):
            name, color = 'warning', '#9F541D'
        item.setIcon(fluent_icon(name, color))
        self.update_queue_summary()

    def update_item_text(self, item):
        path = item.data(PATH_ROLE)
        details = tr(queue_details(item))
        state = tr(item.data(STATE_ROLE) or '대기')
        estimate = item.data(TIME_ESTIMATE_ROLE) or {}
        prediction = tr(time_estimate_text(estimate))
        item.setText(f'{Path(path).name}\n{details} · {state}\n{prediction}')
        tooltip = f'{path}\n{details} · {state}\n{prediction}'
        if estimate.get('error'):
            tooltip += '\n' + tr('설정 확인: {error}' if estimate.get('state') == 'blocked' else '예상 시간 계산 실패: {error}').format(error=tr(estimate['error']))
        if (item.data(INFO_ROLE) or {}).get('_scan_error'):
            tooltip += '\n' + tr(item.data(INFO_ROLE)['_scan_error'])
        item.setToolTip(tooltip)

    def update_time_summary(self):
        items = self.target_items()
        values = [(item.data(TIME_ESTIMATE_ROLE) or {}).get('estimated_seconds') for item in items]
        ready = [value for value in values if value is not None]
        if ready:
            text = f'예상 시간 합계 · 약 {time_text(sum(ready))} ({len(ready)}/{len(items)}개)'
        elif any((item.data(TIME_ESTIMATE_ROLE) or {}).get('state') in ('pending', 'working') for item in items):
            text = '예상 시간 계산 중…'
        else:
            text = '예상 시간 합계 · —'
        self.time_summary_label.setText(text)

    def update_queue_summary(self):
        labels = ('정보 대기', '정보 분석 중', '추가 분석 중', '분석 실패', '분석 중지', '설정 확인', '대기', '진행', '완료', '결과 제외', '실패', '기존 결과 있음', '중지 중', '중지', '용량 예측 중', '용량 주의', '예측 실패', '예측 제외')
        summary = ' · '.join(f"{name if name != '기존 결과 있음' else '건너뜀'} {self.queue_states[name]}"
                             for name in labels if self.queue_states[name]) or '대기 0'
        self.queue_summary_label.setText(summary)
        self.queue_summary_label.setToolTip(summary)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'log_toggle'):
            self.update_compact_layout()

    def update_compact_layout(self):
        compact = self.height() < 750
        self.output_preview_frame.setVisible(True)
        self.empty_icon.setVisible(not compact)
        self.empty_support.setVisible(not compact)
        self.empty_state.setMinimumHeight(90 if compact else 150)

    def refresh_queue(self):
        count = self.file_list_widget.count()
        self.empty_state.setVisible(count == 0)
        self.file_list_widget.setVisible(count > 0)
        self.queue_count_label.setText(f'{count}개')
        self.refresh_selection()

    def refresh_selection(self, *args):
        count = self.target_count()
        selected = len(self.file_list_widget.selectedItems())
        self.selection_label.setText(f'선택 {selected}개 · 변환 대상 {count}개' if self.selection_only_check.isChecked()
                                     else f'전체 {self.file_list_widget.count()}개 변환 · 파일 선택으로 정보 확인')
        self.start_button.setText(f'{count}개 변환 시작' if count else '변환 시작')
        self.refresh_controls()
        self.update_time_summary()
        self.update_quality_label()

    def target_items(self):
        if self.selection_only_check.isChecked():
            items = self.file_list_widget.selectedItems()
        else:
            items = [self.file_list_widget.item(i) for i in range(self.file_list_widget.count())]
        return [item for item in items if item.data(STATE_ROLE) not in ('분석 실패', '분석 중지')]

    def target_count(self):
        return len(self.target_items()) if self.selection_only_check.isChecked() else self.file_list_widget.count() - self.queue_states['분석 실패'] - self.queue_states['분석 중지']

    def refresh_controls(self):
        busy = self.converting or self.scanning or self.preflighting or self._close_pending
        for control in [self.add_file_btn, self.input_browse_btn, self.clear_btn, self.selection_only_check]:
            control.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy and bool(self.file_list_widget.selectedItems()))
        self.start_button.setEnabled(not busy and self.target_count() > 0)
        self.stop_button.setEnabled((self.preflighting and not self.stop_requested) or
                                    (self.converting and not self.stop_requested and bool(self.selected_active_tasks())) or
                                    (self.scanning and self.scan_worker is not None and not self.scan_worker.isInterruptionRequested()))
        self.stop_button.setText('예측 중지' if self.preflighting and not self.stop_requested else '검색 중지' if self.scanning
                                 else ('중지 중…' if self.stop_requested and self.converting else '선택 중지'))
        self.stop_button.setToolTip('선택한 실행·대기 항목만 중지합니다.' if self.converting and self.selected_active_tasks()
                                   else '중지할 실행·대기 항목을 선택하세요.' if self.converting
                                   else '용량 예측을 중지합니다.' if self.preflighting else '폴더 검색을 중지합니다.' if self.scanning
                                   else '변환 중 선택한 항목만 중지합니다.')
        for control in [*self.detail_controls, self.preset_combo, self.save_preset_btn]:
            control.setEnabled(not busy)
        self.delete_preset_btn.setEnabled(not busy and str(self.preset_combo.currentData() or '').startswith('user:'))
        self.gpu_field.setEnabled(not busy and 'GPU' in self.codec_combo.currentData())
        self.gpu_processing_check.setEnabled(not busy and 'GPU' in self.codec_combo.currentData())
        self.quality_edit.setEnabled(not busy and not self.adaptive_quality_check.isChecked())
        self.adaptive_quality_check.setEnabled(not busy and self.rate_control_combo.currentData() in ('CQP', 'CRF', 'VBR'))
        self.source_bitrate_percent_spinbox.setEnabled(not busy and self.rate_control_combo.currentData() == 'VBR'
                                                       and self.adaptive_quality_check.isChecked())
        if self.settings_dialog is not None:
            self.settings_dialog.refresh_controls()

    def remove_selected_files(self):
        if self.converting or self.scanning or self.preflighting:
            return
        for item in list(self.file_list_widget.selectedItems()):
            state = item.data(STATE_ROLE)
            self.queue_states['진행' if '%' in state else state] -= 1
            self.queue_items.pop(item.data(PATH_ROLE), None)
            self.file_list_widget.takeItem(self.file_list_widget.row(item))
        self.refresh_queue()
        self.update_queue_summary()
        if not self.queue_items:
            self.update_file_info_panel(None)
        self.time_preview.schedule()

    def clear_queue(self):
        if self.converting or self.scanning or self.preflighting:
            return
        self.time_preview.pause()
        self.time_preview.failures.clear()
        self.queue_items.clear()
        self.estimate_cache.clear()
        self.queue_states.clear()
        self.file_list_widget.clear()
        self.update_file_info_panel(None)
        self.refresh_queue()
        self.update_queue_summary()
        self.latest_result_label.setText('완료한 파일은 목록에 남아 계속 확인할 수 있습니다.')

    def queue_context_menu(self, position):
        menu = QMenu(self)
        item = self.file_list_widget.itemAt(position)
        if self.converting:
            menu.addAction(tr('선택 항목 중지'), self.stop_selected_conversion).setEnabled(bool(self.selected_active_tasks()) and not self.stop_requested)
            menu.addAction(tr('전체 작업 중지'), self.stop_conversion).setEnabled(not self.stop_requested)
            menu.addSeparator()
        if item:
            menu.addAction(tr('저장 폴더 열기'), lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(item.data(PATH_ROLE)).parent))))
        menu.addAction(tr('모두 선택'), self.file_list_widget.selectAll)
        menu.addAction(tr('선택 해제'), self.file_list_widget.clearSelection)
        if not self.converting and not self.scanning:
            menu.addAction(tr('정보 다시 분석'), self.retry_file_info).setEnabled(any(
                item.data(STATE_ROLE) in ('분석 실패', '분석 중지') for item in self.file_list_widget.selectedItems()))
            menu.addAction(tr('선택 삭제'), self.remove_selected_files)
        menu.exec(self.file_list_widget.viewport().mapToGlobal(position))

    def update_file_info_panel(self, item, previous=None):
        if hasattr(self, 'queue_details_stack'):
            self.queue_details_stack.setCurrentWidget(self.info_summary_label)
        if not item:
            self.info_filename_label.setText('목록에서 파일을 선택하면 정보를 표시합니다.')
            self.info_summary_label.setText('해상도 · 용량 · 재생 시간')
        else:
            path = item.data(PATH_ROLE)
            self.info_filename_label.setLiteralText(self.fontMetrics().elidedText(Path(path).name, Qt.TextElideMode.ElideMiddle, 370))
            self.info_filename_label.setLiteralToolTip(path)
            self.info_summary_label.setText(source_summary(item.data(INFO_ROLE)))
        self.update_output_preview()

    def rebuild_preset_combo(self, preferred=''):
        blocked = self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.setPlaceholderText('사용자 정의')
        for name, (title, description, icon_name, color) in PRESET_DISPLAY.items():
            self.preset_combo.addItem(fluent_icon(icon_name, color), tr(title), 'builtin:' + name)
            self.preset_combo.setItemData(self.preset_combo.count() - 1, tr(description), Qt.ItemDataRole.ToolTipRole)
        if self.user_presets:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in self.user_presets:
                self.preset_combo.addItem(fluent_icon('save', '#7653B5'), name, 'user:' + name)
        index = self.preset_combo.findData(preferred)
        self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(blocked)

    def on_preset_selected(self, index):
        if self._is_applying_preset or self.converting or self.scanning or self.preflighting:
            return
        key = self.preset_combo.itemData(index) or ''
        if key.startswith('builtin:'):
            self.apply_preset(key[len('builtin:'):])
        elif key.startswith('user:'):
            self.restore_options(self.user_presets[key[len('user:'):]])
        else:
            self.preset_label.setText('사용자 정의')
            self.refresh_controls()
        if self.is_initialized:
            self.save_app_settings()

    def save_user_preset(self):
        if self.converting or self.scanning or self.preflighting:
            return
        values = self.get_current_settings()
        error = validate_settings(values)
        if error:
            QMessageBox.warning(self, '설정을 확인해 주세요', error)
            return
        key = self.preset_combo.currentData() or ''
        current_name = key[len('user:'):] if key.startswith('user:') else ''
        name, accepted = QInputDialog.getText(self, '사용자 프리셋 저장', '프리셋 이름 (최대 60자):', text=current_name)
        if not accepted:
            return
        name = name.strip()
        if not name or len(name) > 60 or any(ord(character) < 32 for character in name) or name in PRESETS:
            QMessageBox.warning(self, '프리셋 이름 확인', '기본 프리셋과 다른 이름을 1~60자로 입력해 주세요.')
            return
        if name in self.user_presets:
            answer = QMessageBox.question(self, '프리셋 덮어쓰기', f'“{name}”의 설정을 덮어쓸까요?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        presets = dict(self.user_presets)
        presets[name] = {key: values[key] for key in PRESET_KEYS}
        try:
            self.settings_manager.save_user_presets(presets)
        except OSError as exc:
            QMessageBox.warning(self, '프리셋 저장 실패', str(exc))
            return
        self.user_presets = presets
        self.rebuild_preset_combo('user:' + name)
        self.on_setting_changed()
        self.append_log(f'내 프리셋 저장 · {name}')

    def delete_user_preset(self):
        if self.converting or self.scanning or self.preflighting:
            return
        key = self.preset_combo.currentData() or ''
        if not key.startswith('user:'):
            return
        name = key[len('user:'):]
        answer = QMessageBox.question(self, '사용자 프리셋 삭제', f'“{name}” 프리셋을 삭제할까요? 현재 인코딩 값은 유지합니다.',
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        presets = dict(self.user_presets)
        presets.pop(name, None)
        try:
            self.settings_manager.save_user_presets(presets)
        except OSError as exc:
            QMessageBox.warning(self, '프리셋 삭제 실패', str(exc))
            return
        self.user_presets = presets
        self.rebuild_preset_combo()
        self.on_setting_changed()

    def apply_preset(self, name):
        if self.converting or self.scanning or self.preflighting:
            return
        values = dict(PRESETS[name])
        values.setdefault('suffix', self.suffix_for_codec(values['codec']))
        blocked = self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(self.preset_combo.findData('builtin:' + name))
        self.preset_combo.blockSignals(blocked)
        self.restore_options(values)

    @staticmethod
    def suffix_for_codec(codec):
        if 'HEVC' in codec:
            return '_h265'
        if 'AV1' in codec:
            return '_av1'
        if 'VP9' in codec:
            return '_vp9'
        return '_avc'

    def restore_options(self, values):
        values = normalize_bitrate_settings(values, legacy=values.get('bitrate_unit') != BITRATE_UNIT)
        self._is_applying_preset = True
        for control in self.detail_controls:
            control.blockSignals(True)
        try:
            self.select_value(self.codec_combo, values.get('codec', CODECS[0]))
            self.update_encoder_options()
            mapping = {'resolution': self.resolution_combo, 'preset_option': self.preset_option_combo,
                       'rate_control': self.rate_control_combo, 'audio_option': self.audio_option_combo,
                       'output_format': self.output_format_combo}
            for key, control in mapping.items():
                self.select_value(control, values.get(key, control.currentData()))
            self.suffix_edit.setText(values.get('suffix', self.suffix_for_codec(self.codec_combo.currentData())))
            self.quality_edit.setText(values.get('quality_value', '8000'))
            self.parallel_jobs_spinbox.setValue(values.get('parallel_jobs', 2))
            self.source_bitrate_percent_spinbox.setValue(values.get('source_bitrate_percent', 80))
            self.adaptive_quality_check.setChecked(values.get('adaptive_quality', False))
            self.keep_smaller_check.setChecked(values.get('keep_smaller', False))
            self._last_quality_mode = self.rate_control_combo.currentData() in ('CQP', 'CRF')
        finally:
            for control in self.detail_controls:
                control.blockSignals(False)
            self._is_applying_preset = False
        self.update_quality_label()
        self.on_setting_changed(persist=False)

    def update_encoder_options(self):
        mode = self.rate_control_combo.currentData()
        modes = ['VBR', 'CQP', 'CBR'] if 'GPU' in self.codec_combo.currentData() else ['VBR', 'CRF', 'CBR']
        blocked = self.rate_control_combo.blockSignals(True)
        self.rate_control_combo.clear()
        for value in modes:
            self.rate_control_combo.addItem(value, value)
        self.select_value(self.rate_control_combo, mode if mode in modes else modes[0])
        self.rate_control_combo.blockSignals(blocked)
        self.gpu_field.setEnabled('GPU' in self.codec_combo.currentData() and not self.converting)

    def on_codec_changed(self, *args):
        if self._is_applying_preset:
            return
        self.update_encoder_options()
        if self.suffix_edit.text() in ('_h265', '_av1', '_vp9', '_avc'):
            self.suffix_edit.setText(self.suffix_for_codec(self.codec_combo.currentData()))
        self.on_rate_control_changed()

    def on_rate_control_changed(self, *args):
        if self._is_applying_preset:
            return
        quality_mode = self.rate_control_combo.currentData() in ('CQP', 'CRF')
        if self.rate_control_combo.currentData() == 'CBR':
            self.adaptive_quality_check.setChecked(False)
        previous_mode = getattr(self, '_last_quality_mode', quality_mode)
        if quality_mode != previous_mode:
            self.quality_edit.setText(('28' if 'GPU' in self.codec_combo.currentData() else '23') if quality_mode else '8000')
        self._last_quality_mode = quality_mode
        self.update_quality_label()
        self.on_setting_changed()

    def update_quality_label(self):
        mode = self.rate_control_combo.currentData()
        text = f'품질 · {mode} (0~51)' if mode in ('CQP', 'CRF') else '목표 비트레이트 · kb/s'
        auto_vbr = mode == 'VBR' and self.adaptive_quality_check.isChecked()
        if self.adaptive_quality_check.isChecked() and mode in ('CQP', 'CRF'):
            text = '품질 · 영상별 자동 조절'
        self.quality_field.findChild(QLabel).setText(text)
        self.quality_edit.setAccessibleName(text)
        self.adaptive_quality_check.setText('원본별 화질 자동 조절')
        self.adaptive_quality_check.setVisible(mode in ('CQP', 'CRF'))
        self.bitrate_mode_combo.setVisible(mode == 'VBR')
        blocked = self.bitrate_mode_combo.blockSignals(True)
        self.select_value(self.bitrate_mode_combo, '원본 대비 (%)' if auto_vbr else '직접 입력 (kb/s)')
        self.bitrate_mode_combo.blockSignals(blocked)
        self.source_bitrate_percent_spinbox.setVisible(auto_vbr)
        self.quality_edit.setPlaceholderText('예: 6000' if mode in ('VBR', 'CBR') else '0~51')
        self.quality_edit.setVisible(not auto_vbr)
        self.auto_bitrate_label.setVisible(auto_vbr)
        if auto_vbr:
            item = self.file_list_widget.currentItem()
            info = item.data(INFO_ROLE) if item else {}
            try:
                target = target_bitrate_kbps(self.get_current_settings(), info)
                self.auto_bitrate_label.setText(f'목표 {target} kb/s · 원본 {round(source_video_bitrate(info) / 1000)} kb/s')
            except ValueError:
                self.auto_bitrate_label.setText(f'영상별 원본 비트레이트의 {self.source_bitrate_percent_spinbox.value()}%')

    def on_bitrate_mode_changed(self, *_):
        if not self._is_applying_preset:
            self.adaptive_quality_check.setChecked(self.bitrate_mode_combo.currentData() == '원본 대비 (%)')

    def on_setting_changed(self, *args, persist=True):
        if self._is_applying_preset:
            return
        values = self.get_current_settings()
        candidates = {'builtin:' + name: preset for name, preset in PRESETS.items()}
        candidates.update({'user:' + name: preset for name, preset in self.user_presets.items()})
        current = self.preset_combo.currentData() or ''
        order = [current] + [key for key in candidates if key != current]
        matched = next((key for key in order if key in candidates and all(values.get(field) == value for field, value in candidates[key].items())), '')
        blocked = self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(matched))
        self.preset_combo.blockSignals(blocked)
        self.update_preset_caption()
        self.delete_preset_btn.setEnabled(not self.converting and not self.scanning and matched.startswith('user:'))
        self.update_quality_label()
        self.update_output_preview()
        self.refresh_controls()
        if self.is_initialized and persist:
            self.settings_manager.save_settings(self.get_current_settings())
        if self.time_preview is not None:
            self.time_preview.schedule()

    def update_preset_caption(self):
        key = self.preset_combo.currentData() or ''
        title = key[len('user:'):] if key.startswith('user:') else tr(PRESET_DISPLAY[key[len('builtin:'):]][0]) if key else tr('사용자 정의')
        self.preset_label.setLiteralText(self.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, 150))
        self.preset_label.setLiteralToolTip(title)
        self.preset_combo.setLiteralToolTip(title)

    def get_current_settings(self):
        key = self.preset_combo.currentData() or ''
        kind, separator, name = key.partition(':')
        return {'preset': name if separator else '사용자 정의', 'preset_kind': kind, 'input_folder': self.input_path_edit.text(), 'codec': self.codec_combo.currentData(),
                'resolution': self.resolution_combo.currentData(), 'preset_option': self.preset_option_combo.currentData(),
                'rate_control': self.rate_control_combo.currentData(), 'quality_value': self.quality_edit.text().strip(),
                'bitrate_unit': BITRATE_UNIT,
                'source_bitrate_percent': self.source_bitrate_percent_spinbox.value(),
                'audio_option': self.audio_option_combo.currentData(), 'output_format': self.output_format_combo.currentData(),
                'language': get_language(), 'completion_sound': self.completion_sound_check.isChecked(),
                'estimate_size': self.estimate_size_check.isChecked(),
                'gpu_processing': self.gpu_processing_check.isChecked(), 'suffix': self.suffix_edit.text(), 'parallel_jobs': self.parallel_jobs_spinbox.value(),
                'adaptive_quality': self.adaptive_quality_check.isChecked(), 'keep_smaller': self.keep_smaller_check.isChecked()}

    def update_output_preview(self):
        item = self.file_list_widget.currentItem()
        stem = Path(item.data(PATH_ROLE)).stem if item else tr('나의 영상')
        self.output_preview_label.setLiteralText(f"{stem}{self.suffix_edit.text()}.{self.output_format_combo.currentData()}")

    def load_app_settings(self):
        values = self.settings_manager.load_settings()
        self.completion_sound_check.setChecked(values.get('completion_sound', True))
        self.estimate_size_check.setChecked(values.get('estimate_size', True))
        self.gpu_processing_check.setChecked(values.get('gpu_processing', True))
        if values.get('geometry'):
            self.restoreGeometry(values['geometry'])
        available = self.screen().availableGeometry()
        self.resize(max(self.minimumWidth(), min(self.width(), available.width())),
                    max(self.minimumHeight(), min(self.height(), available.height())))
        if not available.intersects(self.frameGeometry()):
            self.move(available.center() - self.rect().center())
        self.input_path_edit.setText(values.get('input_folder', ''))
        preferred = values.get('preset_kind', 'builtin') + ':' + values.get('preset', '')
        self.user_presets = self.settings_manager.load_user_presets()
        self.rebuild_preset_combo(preferred)
        # Restore exact saved values; never rescan a possibly huge folder on startup.
        self.restore_options(values)

    def save_app_settings(self):
        values = self.get_current_settings()
        values['geometry'] = self.saveGeometry()
        self.settings_manager.save_settings(values)

    def start_conversion(self):
        if self.converting or self.scanning or self.preflighting:
            return
        items = self.target_items()
        if not items:
            return
        settings = self.get_current_settings()
        error = validate_settings(settings)
        if error:
            QMessageBox.warning(self, '설정을 확인해 주세요', error)
            return
        for item in items:
            source = Path(item.data(PATH_ROLE))
            if source.with_name(source.stem + settings['suffix'] + '.' + settings['output_format']).exists():
                continue
            error = validate_media_settings(settings, item.data(INFO_ROLE))
            if error:
                QMessageBox.warning(self, '설정을 확인해 주세요', Path(item.data(PATH_ROLE)).name + '\n' + tr(error))
                return
        outputs = set()
        for item in items:
            source = Path(item.data(PATH_ROLE))
            output = os.path.normcase(str(source.with_name(f"{source.stem}{settings['suffix']}.{settings['output_format']}")))
            if output in outputs:
                QMessageBox.warning(self, '출력 이름 중복', '같은 폴더의 동명 파일이 같은 결과 파일을 생성합니다. 파일을 나누어 변환하거나 접미사를 변경해 주세요.')
                return
            outputs.add(output)
        self.time_preview.pause()
        self.stop_requested = False
        self._preview_pending_batch = (list(items), dict(settings))
        if self.time_preview.worker is not None:
            self.preflighting = True
            self.encoding_status_label.setText('샘플 작업을 정리한 뒤 변환을 시작합니다.')
            self.refresh_controls()
        else:
            self.begin_pending_conversion()

    def begin_pending_conversion(self):
        pending = self._preview_pending_batch
        self._preview_pending_batch = None
        if pending is None:
            return
        self.preflighting = False
        if self.stop_requested or self._close_pending:
            self.refresh_controls()
            return
        items, settings = pending
        if settings.get('estimate_size', True):
            self.start_size_estimate(items, settings)
        else:
            self._estimated_skips = 0
            self.begin_conversion(items, settings)

    def start_size_estimate(self, items, settings):
        self.preflighting = True
        self.stop_requested = False
        self._pending_batch = (list(items), dict(settings))
        self._estimated_skips = 0
        self.set_attention(False)
        self._estimate_decision = None
        self.state_badge.setText('용량 예측 중')
        self.progress_title.setText('용량 예측 중')
        self.progress_summary.setText('짧은 샘플로 예상 크기를 확인합니다.')
        self.encoding_status_label.setText('전체 변환 전에 압축 효과를 확인합니다.')
        self.progress_percent_label.setText('예측 중')
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setIndeterminate(True)
        self.estimate_worker = SizeEstimateWorker([(item.data(PATH_ROLE), item.data(INFO_ROLE)) for item in items],
                                                   settings, self.estimate_cache, self)
        self.estimate_worker.progress.connect(self.on_estimate_progress)
        self.estimate_worker.pause_on_warning = True
        self.estimate_worker.warning.connect(self.on_estimate_warning)
        self.estimate_worker.finished.connect(self.on_estimate_finished)
        self.refresh_controls()
        self.estimate_worker.start()

    def on_estimate_progress(self, path, result, completed, total):
        self.encoding_status_label.setText(f'예측 재사용 · {Path(path).name}' if result.get('cached') else f'용량 예측 · {Path(path).name}')
        self.progress_summary.setText(f'{completed} / {total}개 예측')
        if result['state'] == 'working':
            self.set_item_state(path, '용량 예측 중')
            return
        item = self.queue_items.get(path)
        if item is None:
            return
        if result.get('info'):
            item.setData(INFO_ROLE, result['info'])
        item.setData(ESTIMATE_ROLE, result)
        if result.get('estimated_seconds') is not None:
            item.setData(TIME_ESTIMATE_ROLE, result)
            self.update_time_summary()
        if result.get('key') and result['state'] in ('safe', 'risk'):
            self.estimate_cache[result['key']] = dict(result)
        self.set_item_state(path, {'risk': '용량 주의', 'unknown': '예측 실패', 'blocked': '설정 확인', 'existing': '기존 결과 있음'}.get(result['state'], '대기'))
        if result.get('estimated_bytes') is not None:
            estimate = result['estimated_bytes'] / 1048576
            original = result['source_bytes'] / 1048576
            prefix = '예측 재사용' if result.get('cached') else '용량 예측'
            self.append_log(f'{prefix} · {Path(path).name} · 원본 {original:.1f} MB → 예상 {estimate:.1f} MB')
        elif result.get('error'):
            self.append_log(f'용량 예측 실패 · {Path(path).name}\n{result["error"]}')

    def choose_estimate_action(self, problems):
        result = EstimateDialog(problems, self).exec()
        return 'continue' if result == QDialog.DialogCode.Accepted else 'skip' if result == EstimateDialog.SKIP_RISK else 'adjust'

    def on_estimate_warning(self, result):
        worker = self.estimate_worker
        if worker is None:
            return
        if self.stop_requested or self._close_pending:
            worker.respond('cancel')
            return
        self._estimate_decision = self.choose_estimate_action([result])
        worker.respond(self._estimate_decision)

    def return_to_settings(self):
        self.set_attention(True)
        self.state_badge.setText('설정 확인')
        self.progress_title.setText('설정 확인')
        self.encoding_status_label.setText('설정을 조정한 뒤 다시 시작하세요.')
        self.show_settings_dialog(category='advanced')
        self.progress_percent_label.setText('0%')

    def on_estimate_finished(self):
        worker = self.estimate_worker
        self.estimate_worker = None
        for result in worker.results:
            if result.get('key') and result['state'] in ('safe', 'risk'):
                self.estimate_cache[result['key']] = dict(result)
        self.preflighting = False
        self.overall_progress_bar.setIndeterminate(False)
        self.overall_progress_bar.setActive(False)
        pending = self._pending_batch
        self._pending_batch = None
        self.refresh_controls()
        if not pending:
            return
        items, settings = pending
        if self.stop_requested or self._close_pending or (worker.is_cancelled() and self._estimate_decision != 'adjust'):
            self.state_badge.setText('중지됨')
            self.progress_title.setText('중지됨')
            self.encoding_status_label.setText('용량 예측을 중지했습니다.')
            self.progress_percent_label.setText('0%')
            for item in items:
                if item.data(STATE_ROLE) == '용량 예측 중':
                    self.set_item_state(item.data(PATH_ROLE), '대기')
            return
        if self._estimate_decision == 'adjust':
            self.return_to_settings()
            return
        problems = [result for result in worker.results if result['state'] in ('risk', 'unknown', 'blocked')]
        if problems:
            action = self._estimate_decision or self.choose_estimate_action(problems)
            if action != 'skip' and any(result['state'] == 'blocked' for result in problems):
                self.return_to_settings()
                return
            if action == 'adjust':
                self.return_to_settings()
                return
            if action == 'skip':
                excluded = {result['path'] for result in problems}
                for path in excluded:
                    self.set_item_state(path, '예측 제외')
                self._estimated_skips = len(excluded)
                items = [item for item in items if item.data(PATH_ROLE) not in excluded]
        if not items:
            self.state_badge.setText('변환 대상 없음')
            self.progress_title.setText('변환 대상 없음')
            self.encoding_status_label.setText('주의 파일을 제외했습니다. 설정을 조정해 다시 시도하세요.')
            self.progress_summary.setText(f'예측 제외 {self._estimated_skips}개 · 인코딩하지 않았습니다.')
            self.progress_percent_label.setText('0%')
            return
        self.begin_conversion(items, settings)

    def begin_conversion(self, items, settings):
        self.set_attention(False)
        self.converting = True
        self.stop_requested = False
        self.stopping_paths.clear()
        self.results.clear()
        self.results['estimated_skip'] = self._estimated_skips
        self.task_progress = {item.data(PATH_ROLE): 0 for item in items}
        self.task_weights = {}
        for item in items:
            info = item.data(INFO_ROLE) or {}
            stream = video_stream(info)
            self.task_weights[item.data(PATH_ROLE)] = max(1, media_number(info.get('format', {}).get('duration', 0))) * max(1, media_number(stream.get('width'))) * max(1, media_number(stream.get('height')))
        self._weight_total = sum(self.task_weights.values()) or 1
        self._weighted_progress = 0.0
        self.result_input_bytes = self.result_output_bytes = 0
        self.total_files_count = len(items)
        self.completed_files_count = 0
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setActive(True)
        self.encoding_status_label.setText('인코딩 준비 중 · 원본 파일은 유지합니다.')
        self.thread_pool.setMaxThreadCount(settings['parallel_jobs'])
        self.state_badge.setText('변환 중')
        self.progress_title.setText('인코딩 진행')
        self.progress_summary.setText(f"0 / {len(items)}개 처리 · 동시 작업 {settings['parallel_jobs']}개")
        self.status_label.setText('원본은 그대로 유지됩니다. 작업 기록에서 자세한 내용을 확인하세요.')
        self.append_log(f"변환 시작 · {len(items)}개 / {settings['codec']} / {settings['output_format'].upper()}")
        self.active_tasks = []
        for item in items:
            path = item.data(PATH_ROLE)
            self.set_item_state(path, '대기')
            signals = WorkerSignals()
            signals.log.connect(self.append_log)
            signals.progress.connect(self.update_progress_log)
            signals.finished.connect(self.on_task_finished)
            self.active_tasks.append(FileConversionTask(path, settings, signals, item.data(INFO_ROLE)))
        self.refresh_controls()
        for task in self.active_tasks:
            self.thread_pool.start(task)

    def update_progress_log(self, filename, percentage):
        if not self.converting or filename not in self.task_progress or filename in self.stopping_paths:
            return
        self.set_task_progress(filename, percentage)
        self.set_item_state(filename, f'{percentage}% 변환 중')
        status = f'변환 중 · {os.path.basename(filename)} · {self.completed_files_count}/{self.total_files_count}개 처리'
        self.encoding_status_label.setText(status)
        self.encoding_status_label.setToolTip(status)

    def set_task_progress(self, filename, percentage):
        value = max(0, min(100, percentage))
        self._weighted_progress += (value - self.task_progress.get(filename, 0)) * self.task_weights.get(filename, 1)
        self.task_progress[filename] = value
        progress = round(self._weighted_progress / self._weight_total)
        self.overall_progress_bar.setValue(min(99, progress) if self.completed_files_count < self.total_files_count else progress)

    def on_task_finished(self, task, outcome):
        if task not in self.active_tasks:
            return
        self.active_tasks.remove(task)
        self.stopping_paths.discard(str(task.input_file))
        self.results[outcome] += 1
        self.completed_files_count += 1
        path = str(task.input_file)
        states = {'done': '완료', 'skipped': '기존 결과 있음', 'kept': '결과 제외', 'failed': '실패', 'stopped': '중지'}
        self.set_item_state(path, states.get(outcome, '실패'))
        if outcome == 'done':
            self.result_input_bytes += task.input_size
            self.result_output_bytes += task.output_size
        if outcome in ('done', 'kept'):
            difference = (1 - task.output_size / task.input_size) * 100 if task.input_size else 0
            item = self.queue_items.get(path)
            if item is not None:
                comparison = f'{abs(difference):.1f}% ' + ('감소' if difference >= 0 else '증가')
                metadata = source_summary(item.data(INFO_ROLE)).rsplit(' · ', 1)[0]
                item.setData(DETAIL_ROLE, f'{metadata} · 원본 {task.input_size / 1048576:.1f} MB → 결과 {task.output_size / 1048576:.1f} MB · {comparison}')
                self.update_item_text(item)
        latest = f"최근 처리 · {states.get(outcome, '실패')} · {task.input_file.name}"
        self.latest_result_label.setText(latest)
        self.latest_result_label.setToolTip(latest)
        if self.follow_results_check.isChecked():
            self.queue_details_stack.setCurrentWidget(self.latest_result_label)
        item = self.queue_items.get(path)
        if self.follow_results_check.isChecked() and item is not None:
            self.file_list_widget.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
        self.set_task_progress(path, 100 if outcome != 'stopped' else self.task_progress.get(path, 0))
        self.progress_summary.setText(f'{self.completed_files_count} / {self.total_files_count}개 처리 · 실패 {self.results["failed"]}개')
        if not self.active_tasks:
            self.conversion_finished()
        else:
            self.refresh_controls()

    def conversion_finished(self):
        self.converting = False
        self.set_attention(bool(self.results['failed'] or self.results['kept'] or self.results['stopped']))
        self.overall_progress_bar.setActive(False)
        self.state_badge.setText('중지됨' if self.stop_requested or self.results['stopped'] == self.total_files_count else
                                 '확인 필요' if self.results['failed'] or self.results['kept'] else
                                 '일부 중지' if self.results['stopped'] else '작업 완료')
        self.progress_title.setText(self.state_badge.sourceText())
        self.progress_summary.setText(f"완료 {self.results['done']} · 건너뜀 {self.results['skipped']} · 결과 제외 {self.results['kept']} · 실패 {self.results['failed']} · 중지 {self.results['stopped']}")
        if self.results['estimated_skip']:
            self.progress_summary.setText(self.progress_summary.sourceText() + f" · 예측 제외 {self.results['estimated_skip']}")
        if self.result_input_bytes:
            difference = (1 - self.result_output_bytes / self.result_input_bytes) * 100
            comparison = f'{abs(difference):.1f}% ' + ('감소' if difference >= 0 else '증가')
            self.encoding_status_label.setText(f'결과 합계 {self.result_output_bytes / 1048576:.1f} MB · 원본 대비 {comparison} · 원본은 별도 유지')
        else:
            self.encoding_status_label.setText(self.progress_summary.sourceText())
        self.status_label.setText('실패한 파일은 작업 기록을 확인하고 설정을 변경해 다시 시도하세요.' if self.results['failed']
                                  else '목록을 유지했습니다. 결과는 각 원본 파일과 같은 폴더에서 확인할 수 있습니다.')
        if self.results['failed'] or self.results['kept']:
            self.log_toggle.setChecked(True)
        self.append_log(self.progress_summary.sourceText())
        self.refresh_controls()
        if self.results['kept']:
            self.encoding_status_label.setText(f'결과 제외 {self.results["kept"]}개 · 원본보다 작아지지 않았습니다. 압축 설정을 확인하세요.')
        if not self.stop_requested and not self.results['stopped'] and self.completion_sound_check.isChecked():
            play_completion_sound()
        if not self.stop_requested and self.results['kept'] and not self.results['done']:
            self.show_batch_warning()

    def show_batch_warning(self):
        dialog = BrandDialog('저장된 결과가 없습니다', self, width=500)
        hint = label('원본보다 작지 않은 결과를 제외했습니다.\nCQ/CRF는 숫자를 높이고, 비트레이트는 낮춰 보세요.', 'muted')
        hint.setWordWrap(True)
        dialog.content.addWidget(hint)
        dialog.add_action('확인', dialog.accept, primary=True, default=True)
        dialog.finish_layout()
        dialog.exec()

    def set_attention(self, enabled):
        self.state_badge.setProperty('attention', enabled)
        self.state_badge.style().unpolish(self.state_badge)
        self.state_badge.style().polish(self.state_badge)

    def selected_active_tasks(self):
        selected = {item.data(PATH_ROLE) for item in self.file_list_widget.selectedItems()}
        return [task for task in self.active_tasks if str(task.input_file) in selected and not task.cancelled.is_set()]

    def stop_selected_conversion(self):
        if not self.converting:
            if self.preflighting or self.scanning:
                self.stop_conversion()
            return
        tasks = self.selected_active_tasks()
        if self.stop_requested or not tasks:
            return
        for task in tasks:
            path = str(task.input_file)
            self.stopping_paths.add(path)
            task.stop()
            self.set_item_state(path, '중지 중')
        message = f'선택 중지 · {len(tasks)}개 · 나머지 작업은 계속 진행합니다.'
        self.encoding_status_label.setText(message)
        self.append_log(message)
        self.refresh_controls()

    def stop_conversion(self):
        """Stop the whole batch for shutdown or an explicit Stop all action."""
        if self._preview_pending_batch is not None:
            self.stop_requested = True
            self._preview_pending_batch = None
            self.preflighting = False
            self.encoding_status_label.setText('변환 시작을 취소했습니다.')
        elif self.preflighting and self.estimate_worker:
            self.stop_requested = True
            self.estimate_worker.cancel()
            self.encoding_status_label.setText('용량 예측을 중지하고 있습니다…')
        elif self.scanning and self.scan_worker:
            self.scan_worker.cancel()
            self.status_label.setText('현재 파일 확인을 마친 뒤 검색을 중지합니다…')
        elif self.converting:
            self.stop_requested = True
            for task in self.active_tasks:
                task.stop()
            self.state_badge.setText('중지 중')
            self.status_label.setText('변환 프로세스를 종료하고 미완성 결과 파일을 정리하고 있습니다…')
        self.refresh_controls()

    def append_log(self, message):
        # File names and FFmpeg errors are plain text, never interpreted as HTML.
        self.log_entries.append(message)
        self.log_entries = self.log_entries[-1500:]
        self.log_edit.insertPlainText(tr(message) + '\n')
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def check_and_prepare_ffmpeg(self):
        if get_ffmpeg_path() and get_ffmpeg_path('ffprobe'):
            return True
        downloader = FFmpegDownloaderDialog(ffmpeg_directory(), self)
        return downloader.exec() == QDialog.DialogCode.Accepted and bool(get_ffmpeg_path() and get_ffmpeg_path('ffprobe'))

    def check_for_updates(self):
        if self._close_pending:
            return
        self.update_worker = UpdateCheckWorker(APP_VERSION)
        self.update_worker.result.connect(self.on_update_check_finished)
        self.update_worker.start()

    def on_update_check_finished(self, result):
        if result.get('update') and not self._close_pending:
            self.update_button.setText(f"{result.get('version')} 다운로드")
            self.update_button.show()
            self.append_log(f"새 버전 {result.get('version')} · https://github.com/deuxdoom/VideoBatchConverter/releases/latest")

    def show_settings_dialog(self, checked=False, category=None, help_key=None):
        if self._close_pending:
            return
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        if category:
            self.settings_dialog.select_category(category)
        self.settings_dialog.refresh_controls()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
        if help_key:
            self.settings_dialog.show_help(help_key)

    def show_about_dialog(self):
        self.show_settings_dialog(category='about')

    def confirm_exit(self, busy):
        return ConfirmExitDialog(busy, self).exec() == QDialog.DialogCode.Accepted

    def closeEvent(self, event):
        busy = self.converting or self.scanning or self.preflighting
        updating = self.update_worker is not None and self.update_worker.isRunning()
        if self.is_initialized and not self._close_pending:
            if not self.confirm_exit(busy):
                event.ignore()
                return
            self._close_pending = True
        previewing = self.time_preview is not None and self.time_preview.worker is not None
        if self.time_preview is not None:
            self.time_preview.pause()
        if busy or updating or previewing:
            self._close_pending = True
            self.stop_conversion()
            QTimer.singleShot(100, self.close)
            event.ignore()
            return
        if self.is_initialized:
            self.save_app_settings()
        self.log_dialog.reject()
        if self.settings_dialog is not None:
            self.settings_dialog.reject()
        self.thread_pool.waitForDone()
        event.accept()
