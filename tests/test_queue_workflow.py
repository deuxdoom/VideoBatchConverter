from pathlib import Path
import threading

from PyQt6.QtCore import QItemSelectionModel, QPoint, Qt
from PyQt6.QtGui import QFontDatabase, QFontInfo
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QPushButton, QTreeView

from src.fonts import PRIMARY_FONT
from src.profiles import PRESETS
from src.source_picker import SourcePickerDialog
from src.ui_mainwindow import PATH_ROLE, STATE_ROLE
from src.worker import FileConversionTask, get_media_info
from tests.test_ui import wait_until


def test_empty_click_opens_combined_picker_and_imports(window, app, sample_video, monkeypatch):
    from src import ui_mainwindow
    opened = []
    class Picker:
        paths = [str(sample_video)]
        def __init__(self, directory, parent):
            opened.append(directory)
        def exec(self):
            return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ui_mainwindow, 'SourcePickerDialog', Picker)
    QTest.mouseClick(window.empty_state, Qt.MouseButton.LeftButton)
    wait_until(app, lambda: not window.scanning)
    assert len(opened) == 1
    assert window.file_list_widget.count() == 1
    # Blank area below existing rows also opens the same chooser.
    QTest.mouseClick(window.file_list_widget.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(30, window.file_list_widget.viewport().height() - 10))
    wait_until(app, lambda: not window.scanning)
    assert len(opened) == 2
    assert window.file_list_widget.count() == 1
    window.converting = True
    window.add_sources()
    assert len(opened) == 2
    window.converting = False


def test_combined_picker_selects_actual_file_and_folder(app, tmp_path):
    folder = tmp_path / '하위 폴더'
    folder.mkdir()
    video = tmp_path / '영상.mp4'
    video.write_bytes(b'example')
    picker = SourcePickerDialog(str(tmp_path))
    picker.show()
    view = picker.findChild(QTreeView, 'treeView')
    wait_until(app, lambda: view.model().index(str(video)).isValid())
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    view.selectionModel().clearSelection()
    for path in (folder, video):
        view.selectionModel().select(view.model().index(str(path)), flags)
    QTest.mouseClick(picker.add_button, Qt.MouseButton.LeftButton)
    assert picker.result() == QDialog.DialogCode.Accepted
    assert set(picker.paths) == {str(folder.resolve()), str(video.resolve())}
    picker.close()


def test_combined_picker_can_add_current_folder(app, tmp_path):
    picker = SourcePickerDialog(str(tmp_path))
    picker.show()
    app.processEvents()
    button = next(button for button in picker.findChildren(QPushButton) if button.text() == '현재 폴더 추가')
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert picker.paths == [str(tmp_path.resolve())]
    assert picker.result() == QDialog.DialogCode.Accepted
    picker.close()


def test_queue_height_and_width_prioritize_batch_review(window, app):
    for index in range(250):
        window.add_scanned_file(f'F:/Temp/VideoBatchConverter/list-{index:03d}.mp4', {'streams': [], 'format': {}})
    window.resize(1240, 850)
    app.processEvents()
    assert window.queue_panel.width() > window.sidebar.width() * 1.8
    assert window.file_list_widget.viewport().height() >= 350
    first_row = window.file_list_widget.visualItemRect(window.file_list_widget.item(0))
    assert first_row.height() <= 66
    assert window.file_list_widget.mapTo(window.queue_panel, QPoint()).y() <= 110
    assert not window.queue_details_stack.isVisible()
    before = window.file_list_widget.height()
    window.log_toggle.setChecked(True)
    window.show_settings_dialog(category='advanced')
    app.processEvents()
    assert window.file_list_widget.height() == before
    window.resize(1000, 680)
    app.processEvents()
    assert window.queue_panel.geometry().bottom() == window.sidebar.geometry().bottom()


def test_batch_completion_keeps_selection_and_follows_latest(window, app, sample_video):
    for index in range(12):
        source = sample_video.parent / f'batch-{index:02d}.mp4'
        source.write_bytes(sample_video.read_bytes())
        window.add_scanned_file(str(source), {'streams': [], 'format': {}})
    window.file_list_widget.setCurrentRow(0)
    selected = window.file_list_widget.selectedItems()[0].data(PATH_ROLE)
    window.restore_options(dict(PRESETS[next(iter(PRESETS))], codec='AVC (H.264) - CPU', rate_control='CRF',
                                quality_value='20', suffix='_batch', output_format='mkv', adaptive_quality=False, keep_smaller=False, parallel_jobs=2))
    window.start_conversion()
    wait_until(app, lambda: not window.converting, timeout=25)
    assert window.results['done'] == 12
    assert window.queue_states['완료'] == 12
    assert window.queue_states['대기'] == 0
    assert window.queue_states['진행'] == 0
    assert '완료 12' in window.queue_summary_label.text()
    assert window.file_list_widget.selectedItems()[0].data(PATH_ROLE) == selected
    assert all(window.file_list_widget.item(index).data(STATE_ROLE) == '완료' for index in range(12))
    assert '완료' in window.latest_result_label.text()
    assert window.file_list_widget.verticalScrollBar().value() > 0


def test_stop_selected_running_and_queued_tasks_keeps_other_encoding(window, app, sample_video, monkeypatch):
    paths = []
    for index in range(3):
        path = sample_video.parent / f'selected-stop-{index}.mp4'
        path.write_bytes(sample_video.read_bytes())
        paths.append(str(path.resolve()))
        window.add_scanned_file(paths[-1], get_media_info(path))
    entered = set()
    release = threading.Event()
    original = FileConversionTask.execute
    def gated_execute(task, command, duration):
        entered.add(str(task.input_file))
        while not release.wait(.01):
            if task.cancelled.is_set():
                return 1, []
        return original(task, command, duration)
    monkeypatch.setattr(FileConversionTask, 'execute', gated_execute)
    window.restore_options(dict(PRESETS['1080p'], codec='AVC (H.264) - CPU', rate_control='CRF',
                                quality_value='20', parallel_jobs=2, suffix='_selected_stop', keep_smaller=False))
    window.start_conversion()
    try:
        wait_until(app, lambda: len(entered) == 2)
        window.file_list_widget.clearSelection()
        assert not window.stop_button.isEnabled()
        window.stop_selected_conversion()
        assert not any(task.cancelled.is_set() for task in window.active_tasks)
        window.queue_items[paths[0]].setSelected(True)
        window.queue_items[paths[2]].setSelected(True)
        assert window.stop_button.isEnabled()
        window.stop_button.click()
        assert not window.stop_requested
        assert all(task.cancelled.is_set() == (str(task.input_file) != paths[1]) for task in window.active_tasks)
        wait_until(app, lambda: window.results['stopped'] == 2)
        assert window.converting and not window.start_button.isEnabled()
        assert paths[2] not in entered, 'A cancelled queued item must never start FFmpeg'
    finally:
        release.set()
    wait_until(app, lambda: not window.converting)
    assert window.results['done'] == 1 and window.results['stopped'] == 2
    assert window.queue_items[paths[1]].data(STATE_ROLE) == '완료'
    assert window.state_badge.text() == '일부 중지'
    assert not list(sample_video.parent.glob('*.partial*'))
    assert sample_video.parent.joinpath('selected-stop-1_selected_stop.mp4').exists()


def test_bundled_font_is_resolved_without_stretching(window, app):
    assert PRIMARY_FONT in QFontDatabase.families()
    assert QFontInfo(window.font()).family() == PRIMARY_FONT
    assert app.font().stretch() == 100


def test_wrapped_summary_reserves_space_for_every_line(window, app):
    window.resize(1000, 680)
    window.progress_summary.setText('완료 123 · 건너뜀 12 · 원본 유지 123 · 실패 2 · 중지 0')
    app.processEvents()
    summary = window.progress_summary
    assert summary.height() >= summary.heightForWidth(summary.width())
    assert summary.mapTo(window, QPoint()).y() + summary.height() <= window.overall_progress_bar.mapTo(window, QPoint()).y()
