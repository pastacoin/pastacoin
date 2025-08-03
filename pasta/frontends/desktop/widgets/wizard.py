from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel, QLineEdit, QFormLayout, QPushButton, QMessageBox
)
from PySide6.QtCore import Signal

from pasta import Node, generate_keypair
from pasta.core.crypto import sign_message


class ActionPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Choose Action")
        self.choice: Optional[str] = None

        layout = QVBoxLayout()
        self.send_btn = QPushButton("Send PASTA (State A)")
        self.validate_b_btn = QPushButton("Validate Block (State B)")
        self.validate_c_btn = QPushButton("Finalize Block (State C)")
        layout.addWidget(self.send_btn)
        layout.addWidget(self.validate_b_btn)
        layout.addWidget(self.validate_c_btn)
        self.setLayout(layout)

        self.send_btn.clicked.connect(lambda: self._select("A"))
        self.validate_b_btn.clicked.connect(lambda: self._select("B"))
        self.validate_c_btn.clicked.connect(lambda: self._select("C"))

    def _select(self, action: str):
        self.choice = action
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: D401 override
        return self.choice is not None


class DetailsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Enter Transaction Details")
        self.sender_edit = QLineEdit()
        self.receiver_edit = QLineEdit()
        self.amount_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Sender (public key)", self.sender_edit)
        form.addRow("Receiver (public key)", self.receiver_edit)
        form.addRow("Amount (blank = 0)", self.amount_edit)
        self.setLayout(form)

        # Re-evaluation of completeness when a field changes
        for widget in (self.sender_edit, self.receiver_edit, self.amount_edit):
            widget.textChanged.connect(self.completeChanged)

    def isComplete(self):  # noqa: D401
        # A transaction is valid for creation if sender and receiver are filled.
        # Amount can be empty (treated as 0) or any non-negative number so that
        # developers can experiment with the zero-value minting path.
        if not self.sender_edit.text().strip() or not self.receiver_edit.text().strip():
            return False

        amount_txt = self.amount_edit.text().strip()
        if not amount_txt:
            return True  # empty → interpreted as 0
        try:
            return float(amount_txt) >= 0
        except ValueError:
            return False


class SummaryPage(QWizardPage):
    def __init__(self, node: Node):
        super().__init__()
        self.setTitle("Review & Submit")
        self.node = node
        self.label = QLabel()
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)

    def initializePage(self):
        sender = self.wizard().details_page.sender_edit.text()
        receiver = self.wizard().details_page.receiver_edit.text()
        amount = self.wizard().details_page.amount_edit.text()
        self.label.setText(f"Send {amount} PASTA from {sender[:8]}... to {receiver[:8]}...")

    def validatePage(self):
        # For now, just create State A transaction
        sender = self.wizard().details_page.sender_edit.text()
        receiver = self.wizard().details_page.receiver_edit.text()
        amount = float(self.wizard().details_page.amount_edit.text())
        tx = self.node.create_transaction(sender, receiver, amount)
        print("Transaction sent:", tx)
        return True


class PrivateKeyPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Sign Transaction")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        layout = QFormLayout()
        layout.addRow("Sender private key", self.key_edit)
        self.setLayout(layout)

    def isComplete(self):  # noqa: D401
        return bool(self.key_edit.text().strip())


class TransactionWizard(QWizard):
    finished_signal = Signal()

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self.node = node

        self.details_page = DetailsPage()
        self.sign_page = PrivateKeyPage()
        self.addPage(self.details_page)
        self.addPage(self.sign_page)

        self.setWindowTitle("New Transaction")
        # Rename default "Finish" button to clearer action label.
        self.setButtonText(QWizard.FinishButton, "Create")
        self.finished.connect(lambda _: self.finished_signal.emit())

    def accept(self):
        # build tx upon Finish
        sender = self.details_page.sender_edit.text()
        receiver = self.details_page.receiver_edit.text()
        # Validate and build transaction when the user clicks Create
        amount_txt = self.details_page.amount_edit.text().strip()
        if not sender or not receiver:
            QMessageBox.critical(self, "Incomplete", "Sender and Receiver must be provided.")
            return
        try:
            amount = float(amount_txt) if amount_txt else 0.0
            if amount < 0:
                raise ValueError()
        except ValueError:
            QMessageBox.critical(self, "Invalid amount", "Amount must be a non-negative number or left blank.")
            return

        try:
            tx = self.node.create_transaction(sender, receiver, amount)
        except Exception as exc:  # Catch any backend errors and surface them
            QMessageBox.critical(self, "Transaction error", str(exc))
            return

        # --- Signing -----------------------------------------------------
        priv_key = self.sign_page.key_edit.text().strip()
        if priv_key:
            msg = str(sorted(tx.items()))  # simple canonical representation
            try:
                sig = sign_message(priv_key, msg)
                tx["signature"] = sig  # same dict reference stored in node
            except Exception as exc:
                QMessageBox.critical(self, "Signing failed", str(exc))
                return

        print("Created tx (signed):", tx)
        super().accept()
