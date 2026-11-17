"""Guard the dark-system palette and view-font failures seen on Windows."""

from PyQt6.QtCore import QItemSelectionModel, Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QAbstractItemView, QFileDialog, QTreeView

from src.source_picker import SourcePickerDialog
from src.theme import configure_theme
from tests.test_ui import wait_until


def assert_smooth_font(widget):
    font = widget.font()
    assert font.hintingPreference() == QFont.HintingPreference.PreferNoHinting
    assert font.styleStrategy() & QFont.StyleStrategy.PreferAntialias
    assert not font.styleStrategy() & QFont.StyleStrategy.NoAntialias


def test_dark_system_palette_does_not_leak_into_new_views(app):
    dark = QPalette()
    for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Window, QPalette.ColorRole.Button,
                 QPalette.ColorRole.Dark, QPalette.ColorRole.Shadow):
        dark.setColor(role, QColor('#202020'))
    app.setPalette(dark)
    configure_theme(app)
    app.processEvents()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base, QPalette.ColorRole.Button,
                     QPalette.ColorRole.Dark, QPalette.ColorRole.Shadow):
            assert app.palette().color(group, role).lightness() > 170, (group, role)
    assert app.palette().color(QPalette.ColorRole.HighlightedText).lightness() < 180


def test_popup_background_selection_and_font(window, app):
    for combo in (window.preset_combo, window.codec_combo):
        assert_smooth_font(combo)
        combo.showPopup()
        app.processEvents()
        view = combo.view()
        assert_smooth_font(view)
        assert_smooth_font(view.viewport())
        image = view.viewport().grab().toImage()
        scale = image.devicePixelRatio()
        point = view.visualRect(view.currentIndex()).topLeft()
        # Sample left of the text, inside the selected row.
        color = image.pixelColor(int((point.x() + 2) * scale), int((point.y() + 8) * scale))
        assert color.lightness() > 200, color.name()
        assert view.palette().color(QPalette.ColorRole.Text).lightness() < 150
        combo.hidePopup()


def test_file_picker_views_headers_and_mixed_selection_stay_light(window, app, tmp_path):
    folder = tmp_path / '하위 폴더'
    folder.mkdir()
    video = tmp_path / '영상.mp4'
    video.write_bytes(b'example')
    picker = SourcePickerDialog(str(tmp_path), window)
    picker.show()
    try:
        tree = picker.findChild(QTreeView, 'treeView')
        wait_until(app, lambda: tree.model().index(str(video)).isValid())
        app.processEvents()
        for view in picker.findChildren(QAbstractItemView):
            if view.isVisible():
                assert_smooth_font(view)
            assert view.palette().color(QPalette.ColorRole.Base).lightness() > 220
        assert_smooth_font(tree.header())
        image = tree.viewport().grab().toImage()
        assert image.pixelColor(image.width() // 2, image.height() - 10).lightness() > 230
        picker.setViewMode(QFileDialog.ViewMode.List)
        app.processEvents()
        for view in picker.findChildren(QAbstractItemView):
            if view.isVisible():
                assert_smooth_font(view)
        picker.setViewMode(QFileDialog.ViewMode.Detail)
        app.processEvents()
        for path in (folder, video):
            tree.selectionModel().select(tree.model().index(str(path)),
                                         QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        picker.accept()
        assert set(picker.paths) == {str(folder.resolve()), str(video.resolve())}
    finally:
        picker.close()
