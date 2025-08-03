from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtGui import QClipboard
from PySide6.QtCore import Qt

from pasta import generate_keypair


class KeypairDialog(QDialog):
    """Dialog that generates and displays a new ECDSA keypair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Keypair")
        self.setModal(True)
        self.resize(500, 250)

        priv_pub = generate_keypair()
        private_key = priv_pub["private_key"]
        public_key = priv_pub["public_key"]

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Private Key (keep secret):"))
        self.priv_edit = QPlainTextEdit(private_key)
        self.priv_edit.setReadOnly(True)
        self.priv_edit.setMaximumHeight(60)
        layout.addWidget(self.priv_edit)

        layout.addWidget(QLabel("Public Key / Address:"))
        self.pub_edit = QPlainTextEdit(public_key)
        self.pub_edit.setReadOnly(True)
        self.pub_edit.setMaximumHeight(60)
        layout.addWidget(self.pub_edit)

        btn_layout = QHBoxLayout()
        copy_priv = QPushButton("Copy Private")
        copy_pub = QPushButton("Copy Public")
        close_btn = QPushButton("Close")
        btn_layout.addWidget(copy_priv)
        btn_layout.addWidget(copy_pub)
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        copy_priv.clicked.connect(lambda: self._copy(self.priv_edit.toPlainText()))
        copy_pub.clicked.connect(lambda: self._copy(self.pub_edit.toPlainText()))
        close_btn.clicked.connect(self.accept)

    def _copy(self, text: str):
        cb: QClipboard = self.clipboard()
        cb.setText(text, mode=QClipboard.Clipboard)
        QMessageBox.information(self, "Copied", "Text copied to clipboard.")
