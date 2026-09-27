from __future__ import annotations

import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLineEdit, QMessageBox, QWizard, QWizardPage

from pasta import Node, PastaError
from pasta.core.crypto import public_key_for, sign_transaction


class DetailsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Transaction details")
        self.setSubTitle("The sender address is derived from the private key on the next page.")
        self.receiver_edit = QLineEdit()
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0 = zero-value (may mint during bootstrap)")
        form = QFormLayout()
        form.addRow("Receiver address", self.receiver_edit)
        form.addRow("Amount", self.amount_edit)
        self.setLayout(form)
        for widget in (self.receiver_edit, self.amount_edit):
            widget.textChanged.connect(self.completeChanged)

    def amount(self) -> float:
        txt = self.amount_edit.text().strip()
        return float(txt) if txt else 0.0

    def isComplete(self):  # noqa: D401
        if not self.receiver_edit.text().strip():
            return False
        try:
            return self.amount() >= 0
        except ValueError:
            return False


class PrivateKeyPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Sign")
        self.setSubTitle("Your private key never leaves this machine; only the signature is stored.")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        layout = QFormLayout()
        layout.addRow("Sender private key", self.key_edit)
        self.setLayout(layout)
        self.key_edit.textChanged.connect(self.completeChanged)

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
        self.setButtonText(QWizard.FinishButton, "Sign and submit")
        self.finished.connect(lambda _: self.finished_signal.emit())

    def accept(self):
        receiver = self.details_page.receiver_edit.text().strip()
        try:
            amount = self.details_page.amount()
        except ValueError:
            QMessageBox.critical(self, "Invalid amount", "Amount must be a non-negative number or blank.")
            return
        priv = self.sign_page.key_edit.text().strip()
        try:
            sender = public_key_for(priv)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Bad private key", str(exc))
            return
        ts = int(time.time())
        try:
            sig = sign_transaction(priv, sender, receiver, amount, ts)
            tx = self.node.create_transaction(sender, receiver, amount, timestamp=ts, signature=sig)
        except PastaError as exc:
            QMessageBox.critical(self, "Rejected by node", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(
            self,
            "Transaction created",
            f"State A. tx_id {tx['tx_id'][:16]}...\nMint: {tx['mint_amount']}\n\n"
            "Use Transactions > Validate to move it to State B.",
        )
        super().accept()
