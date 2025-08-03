from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel, QLineEdit, QFormLayout, QPushButton
)
from PySide6.QtCore import Signal

from pasta import Node, generate_keypair


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
        form.addRow("Amount", self.amount_edit)
        self.setLayout(form)

    def isComplete(self):  # noqa: D401
        if not self.sender_edit.text() or not self.receiver_edit.text():
            return False
        try:
            return float(self.amount_edit.text()) > 0
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


class TransactionWizard(QWizard):
    finished_signal = Signal()

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self.node = node

        self.action_page = ActionPage()
        self.details_page = DetailsPage()
        self.summary_page = SummaryPage(node)


        self.addPage(self.action_page)
        self.addPage(self.details_page)
        self.addPage(self.summary_page)

        self.setWindowTitle("Transaction Wizard")
        self.finished.connect(lambda _: self.finished_signal.emit())
