from __future__ import annotations

import logging
import typing as _t

from PySide6.QtWidgets import QDockWidget, QTextEdit
from PySide6.QtCore import Qt


class QTextEditHandler(logging.Handler):
    """Logging handler that appends messages to a QTextEdit."""

    def __init__(self, widget: QTextEdit):
        super().__init__()
        self.widget = widget

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.widget.append(msg)


class LogsPanel(QDockWidget):
    def __init__(self, parent: _t.Optional[object] = None):
        super().__init__("Logs", parent)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.setWidget(self.text)
        from PySide6.QtGui import QTextOption
        self.text.setWordWrapMode(QTextOption.NoWrap)

        # Hook into root logger
        handler = QTextEditHandler(self.text)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        self.setAllowedAreas(Qt.BottomDockWidgetArea)
