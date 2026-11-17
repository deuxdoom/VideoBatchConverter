"""One chooser that adds files and folders together without extra prompts."""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QListView, QPushButton, QTreeView

from .worker import VIDEO_EXTENSIONS
from .i18n import tr
from .localized_widgets import QPushButton
from .fonts import smooth_widget_fonts


class SourceFileDialog(QFileDialog):
    """Apply fonts after Qt has created and polished the standard chooser views."""

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.prepare_fonts)

    def prepare_fonts(self):
        smooth_widget_fonts(self, descendants=True)


class SourcePickerDialog(SourceFileDialog):
    def __init__(self, directory='', parent=None):
        super().__init__(parent, tr('파일 또는 폴더 추가'), directory)
        self.paths = []
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.FileMode.ExistingFiles)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setNameFilter(tr('동영상 및 폴더 (' + ' '.join('*' + ext for ext in sorted(VIDEO_EXTENSIONS)) + ')'))
        self.setMinimumSize(760, 480)
        self.setLabelText(QFileDialog.DialogLabel.FileName, tr('선택 항목:'))
        self.setLabelText(QFileDialog.DialogLabel.Reject, tr('취소'))
        self.setToolTip(tr('파일과 폴더를 함께 선택할 수 있습니다. 폴더를 더블클릭하면 내부로 이동합니다.'))
        for view_name, view_type in (('listView', QListView), ('treeView', QTreeView)):
            view = self.findChild(view_type, view_name)
            if view:
                view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        buttons = self.findChild(QDialogButtonBox)
        for button in buttons.buttons():
            if buttons.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole:
                button.hide()
                button.setDefault(False)
                button.setAutoDefault(False)
        self.add_button = QPushButton('선택 항목 추가')
        self.add_button.setDefault(True)
        self.add_button.clicked.connect(self.accept)
        buttons.addButton(self.add_button, QDialogButtonBox.ButtonRole.ActionRole)
        current_folder = QPushButton('현재 폴더 추가')
        current_folder.clicked.connect(self.add_current_folder)
        buttons.addButton(current_folder, QDialogButtonBox.ButtonRole.ActionRole)

    def accept(self):
        candidates = self.selectedFiles()
        # Read actual selected rows as QFileDialog's filename edit can omit folders.
        for view_name, view_type in (('treeView', QTreeView), ('listView', QListView)):
            view = self.findChild(view_type, view_name)
            if view and view.isVisible() and view.selectionModel():
                selected = view.selectionModel().selectedRows(0) if isinstance(view, QTreeView) else view.selectionModel().selectedIndexes()
                paths = [index.data(int(Qt.ItemDataRole.UserRole) + 1) for index in selected]
                paths = [path for path in paths if isinstance(path, str)]
                if paths:
                    candidates = paths
                    break
        self.accept_paths(candidates)

    def accept_paths(self, paths):
        self.paths = list(dict.fromkeys(str(Path(path).resolve()) for path in paths
                                       if Path(path).is_dir() or Path(path).is_file() and Path(path).suffix.lower() in VIDEO_EXTENSIONS))
        if self.paths:
            QDialog.accept(self)

    def add_current_folder(self):
        self.accept_paths([self.directory().absolutePath()])
