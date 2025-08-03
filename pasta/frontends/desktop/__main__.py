from __future__ import annotations

"""Minimal Pastacoin desktop GUI.

Launch with:

    python -m pasta.frontends.desktop

If PySide6 is not installed, a helpful message is printed and the program exits
cleanly so that the rest of the repository (tests, CLI, web) can run without the
GUI dependency.
"""

import sys
from typing import Optional

from pasta import Node

import threading, logging

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover – optional dependency
    print("PySide6 is not installed. Install it with 'pip install PySide6' to run the desktop GUI.")
    sys.exit(1)


class MainWindow(QMainWindow):
    def __init__(self, node: Node, parent: Optional[object] = None) -> None:  # noqa: D401
        super().__init__(parent)
        self.node = node
        self.setWindowTitle("Pastacoin Desktop (Prototype)")

        # Placeholder content
        # Placeholder central widget (will be replaced by dock panels later)
        label = QLabel("Welcome to Pasta Machine! Use the menu to create a transaction.", alignment=Qt.AlignCenter)
        self.setCentralWidget(label)

        # Menu
        menu = self.menuBar()
        view_menu = menu.addMenu("&View")
        self.action_show_chain = view_menu.addAction("Show Blockchain")
        self.action_show_mempool = view_menu.addAction("Show Mempool")
        self.action_show_chain.triggered.connect(lambda: self.blockchain_dock.show())
        self.action_show_mempool.triggered.connect(lambda: self.mempool_dock.show())

        tx_menu = menu.addMenu("&Transactions")
        new_tx_action = tx_menu.addAction("New Transaction Wizard")
        new_tx_action.triggered.connect(self.open_wizard)

        advance_b_action = tx_menu.addAction("Advance to State B…")
        advance_b_action.triggered.connect(self.open_advance_b_dialog)

        wallet_menu = menu.addMenu("&Wallet")
        gen_kp_action = wallet_menu.addAction("Generate New Keypair")
        gen_kp_action.triggered.connect(self.generate_keypair_dialog)

        # Dock widgets
        from pasta.frontends.desktop.widgets.blockchain_view import BlockchainView
        from pasta.frontends.desktop.widgets.mempool_view import MempoolView
        from pasta.frontends.desktop.widgets.logs_panel import LogsPanel

        self.blockchain_dock = BlockchainView(self.node, self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.blockchain_dock)

        self.mempool_dock = MempoolView(self.node, self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.mempool_dock)

        self.logs_dock = LogsPanel(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.logs_dock)

        self.resize(1000, 700)

        # Start REST server in background thread on an OS-random free port (optional)
        def _run_rest():
            logging.info("Starting embedded REST server on http://127.0.0.1:5000")
            try:
                self.node.start_rest_server(host="127.0.0.1", port=5000, threaded=True)
            except OSError:
                logging.warning("Port 5000 already in use; embedded REST server not started.")
        threading.Thread(target=_run_rest, daemon=True).start()

    def generate_keypair_dialog(self):
        from pasta.frontends.desktop.widgets.keypair_dialog import KeypairDialog
        dlg = KeypairDialog(self)
        dlg.exec()

    def open_advance_b_dialog(self):
        """Prompt for my/target mempool indices and invoke advance_b."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox, QMessageBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Advance Transaction to B")
        layout = QFormLayout(dlg)
        my_idx = QSpinBox()
        target_idx = QSpinBox()
        mp_len = len(self.node.get_mempool())
        for sb in (my_idx, target_idx):
            sb.setRange(0, max(0, mp_len - 1))
        layout.addRow("My tx index", my_idx)
        layout.addRow("Target tx index", target_idx)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.Accepted:
            tx = self.node.advance_b(my_idx.value(), target_idx.value())
            if tx:
                QMessageBox.information(self, "Success", "Transaction advanced to State B.")
            else:
                QMessageBox.warning(self, "Error", "Invalid indices chosen.")

    def open_wizard(self):
        from pasta.frontends.desktop.widgets.wizard import TransactionWizard
        wizard = TransactionWizard(self.node, self)
        wizard.exec()


def main() -> None:  # pragma: no cover
    app = QApplication(sys.argv)

    node = Node()  # In-process node
    window = MainWindow(node)
    window.show()

    # Optionally also start REST server on localhost:5000 so other tools can talk to it
    # Commented out for now to avoid blocking UI thread; will be moved to background thread later.
    # threading.Thread(target=node.start_rest_server, daemon=True).start()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
