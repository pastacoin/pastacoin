from __future__ import annotations

import json
from typing import Any
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton
from PySide6.QtCore import Qt


class BlockDetailsDialog(QDialog):
    """Shows full JSON of a block or mempool transaction."""

    def __init__(self, title: str, data: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))

        self.text = QPlainTextEdit(json.dumps(data, indent=2))
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
