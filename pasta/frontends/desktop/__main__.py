from __future__ import annotations

"""The Pasta Machine: minimal PySide6 desktop node.

Launch with ``python -m pasta.frontends.desktop``. Set ``PASTA_STORAGE`` to a file
path to persist the chain between runs.
"""

import logging
import os
import sys
import threading
from typing import Optional

from pasta import Node, PastaError
from pasta.core.units import format_units
from pasta.node import open_node

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
except ImportError:  # pragma: no cover - optional dependency
    print("PySide6 is not installed. Install it with 'pip install PySide6' to run the desktop GUI.")
    sys.exit(1)


class MainWindow(QMainWindow):
    def __init__(self, node: Node, parent: Optional[object] = None, start_rest: bool = True) -> None:
        super().__init__(parent)
        self.node = node
        self.setWindowTitle("The Pasta Machine")

        label = QLabel("Welcome to The Pasta Machine. Use the Transactions menu to send and validate.",
                       alignment=Qt.AlignCenter)
        self.setCentralWidget(label)

        menu = self.menuBar()
        tx_menu = menu.addMenu("&Transactions")
        tx_menu.addAction("New Transaction...").triggered.connect(self.open_wizard)
        tx_menu.addAction("Validate (A -> B, finalize a target)...").triggered.connect(self.open_validate_dialog)
        tx_menu.addAction("Verify chain").triggered.connect(self.verify_chain)

        wallet_menu = menu.addMenu("&Wallet")
        wallet_menu.addAction("Generate New Keypair").triggered.connect(self.generate_keypair_dialog)
        wallet_menu.addAction("Check Balance...").triggered.connect(self.check_balance_dialog)

        from pasta.frontends.desktop.widgets.blockchain_view import BlockchainView
        from pasta.frontends.desktop.widgets.logs_panel import LogsPanel
        from pasta.frontends.desktop.widgets.mempool_view import MempoolView

        self.blockchain_dock = BlockchainView(self.node, self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.blockchain_dock)
        self.mempool_dock = MempoolView(self.node, self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.mempool_dock)
        self.logs_dock = LogsPanel(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.logs_dock)
        self.resize(1100, 700)

        if start_rest:
            def _run_rest():
                logging.info("Starting embedded REST server on http://127.0.0.1:5000")
                try:
                    self.node.start_rest_server(host="127.0.0.1", port=5000, threaded=True)
                except OSError:
                    logging.warning("Port 5000 already in use; embedded REST server not started.")
            threading.Thread(target=_run_rest, daemon=True).start()

    # ------------------------------------------------------------------ actions
    def generate_keypair_dialog(self):
        from pasta.frontends.desktop.widgets.keypair_dialog import KeypairDialog
        KeypairDialog(self).exec()

    def open_wizard(self):
        from pasta.frontends.desktop.widgets.wizard import TransactionWizard
        TransactionWizard(self.node, self).exec()

    def open_validate_dialog(self):
        """Pick one of my State-A transactions and an eligible State-B target."""
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QMessageBox

        mempool = self.node.get_mempool()
        mine = [t for t in mempool if t["state"] == "A"]
        targets = [t for t in mempool if t["state"] == "B"]
        if not mine or not targets:
            QMessageBox.information(self, "Nothing to do",
                                    "Need at least one State A transaction and one State B target.")
            return

        def label(t):
            return f"{t['tx_id'][:10]}  {t['sender_address'][:8]} -> {t['receiver_address'][:8]}  {format_units(t['amount'])}"

        dlg = QDialog(self)
        dlg.setWindowTitle("Validate")
        layout = QFormLayout(dlg)
        my_box, target_box = QComboBox(), QComboBox()
        for t in mine:
            my_box.addItem(label(t), t["tx_id"])
        for t in targets:
            target_box.addItem(label(t), t["tx_id"])
        layout.addRow("My transaction (State A)", my_box)
        layout.addRow("Target to finalize (State B)", target_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            result = self.node.validate(my_box.currentData(), target_box.currentData())
        except PastaError as exc:
            QMessageBox.warning(self, "Rejected", str(exc))
            return
        fin = result["finalized"]
        logging.info("Finalized %s (difficulty %s)", fin["block_hash"][:16], fin["required_difficulty"])
        QMessageBox.information(self, "Done",
                                f"Your transaction is in State B.\nFinalized block {fin['block_hash'][:16]}...")

    def verify_chain(self):
        from PySide6.QtWidgets import QMessageBox
        problems = self.node.verify()
        if problems:
            QMessageBox.warning(self, "Chain problems", "\n".join(problems))
        else:
            QMessageBox.information(self, "Chain OK", f"{len(self.node.get_blockchain())} blocks verified.")

    def check_balance_dialog(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Check Balance")
        form = QFormLayout(dlg)
        addr_edit = QLineEdit()
        form.addRow("Address", addr_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            address = addr_edit.text().strip()
            if not address:
                QMessageBox.warning(self, "Missing", "Please enter an address")
                return
            bal = self.node.balance_for(address)
            pending = self.node.pending_outgoing(address)
            QMessageBox.information(self, "Balance",
                                    f"{address[:12]}...: {format_units(bal)} PASTA "
                                    f"(pending outgoing {format_units(pending)})")


def main() -> None:  # pragma: no cover
    app = QApplication(sys.argv)
    node, new_key = open_node(os.environ.get("PASTA_STORAGE") or None,
                              os.environ.get("PASTA_GENESIS_ADDRESS") or None)
    window = MainWindow(node)
    window.show()
    if new_key:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            window, "New chain started",
            "This is a new chain. Its genesis coins (10 PASTA) belong to this key. Save it now; "
            "it is not stored anywhere.\n\n"
            f"Address:\n{new_key['public_key']}\n\nPrivate key:\n{new_key['private_key']}")
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
