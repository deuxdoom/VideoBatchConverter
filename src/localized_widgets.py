"""Small Qt adapters that retain source copy for live language switching."""

from PyQt6 import QtWidgets

from .i18n import language_manager, tr


class LocalizedProperties:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sources = {}
        language_manager().changed.connect(self.retranslate)

    def _localized(self, name, source, literal=False):
        if not hasattr(self, '_sources'):
            self._sources = {}
        self._sources[name] = (source, literal)
        getattr(super(), 'set' + name)(source if literal else tr(source))
        if hasattr(self, 'fit_wrapped_height'):
            self.fit_wrapped_height()

    def retranslate(self, *_):
        for name, (source, literal) in list(self._sources.items()):
            self._localized(name, source, literal)

    def setToolTip(self, text):
        self._localized('ToolTip', text)

    def setLiteralToolTip(self, text):
        self._localized('ToolTip', text, True)

    def setAccessibleName(self, text):
        self._localized('AccessibleName', text)

    def setWindowTitle(self, text):
        self._localized('WindowTitle', text)

    def setPlaceholderText(self, text):
        self._localized('PlaceholderText', text)


class LocalizedText(LocalizedProperties):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(self.text())

    def setText(self, text):
        self._localized('Text', text)

    def setLiteralText(self, text):
        self._localized('Text', text, True)

    def sourceText(self):
        return self._sources.get('Text', ('', False))[0]


class QLabel(LocalizedText, QtWidgets.QLabel):
    pass


class QPushButton(LocalizedText, QtWidgets.QPushButton):
    pass


class QToolButton(LocalizedText, QtWidgets.QToolButton):
    pass


class QCheckBox(LocalizedText, QtWidgets.QCheckBox):
    pass


class QLineEdit(LocalizedProperties, QtWidgets.QLineEdit):
    pass


class QComboBox(LocalizedProperties, QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A styled list delegate respects the light selection and text colors.
        # The platform's menu-style combo delegate can retain system colors.
        view = QtWidgets.QListView(self)
        view.setItemDelegate(QtWidgets.QStyledItemDelegate(view))
        self.setView(view)

    def showPopup(self):
        from .fonts import smooth_widget_fonts
        super().showPopup()
        smooth_widget_fonts(self.view().window(), descendants=True)


class QDialog(LocalizedProperties, QtWidgets.QDialog):
    pass


class QSpinBox(LocalizedProperties, QtWidgets.QSpinBox):
    pass


class QTextEdit(LocalizedProperties, QtWidgets.QTextEdit):
    pass


class QMessageBox(QtWidgets.QMessageBox):
    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        return QtWidgets.QMessageBox.information(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        return QtWidgets.QMessageBox.warning(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def question(parent, title, text, *args, **kwargs):
        return QtWidgets.QMessageBox.question(parent, tr(title), tr(text), *args, **kwargs)


class QInputDialog(QtWidgets.QInputDialog):
    @staticmethod
    def getText(parent, title, label, *args, **kwargs):
        return QtWidgets.QInputDialog.getText(parent, tr(title), tr(label), *args, **kwargs)
