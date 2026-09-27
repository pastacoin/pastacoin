from __future__ import annotations

import typing as _t

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDockWidget, QHeaderView, QTableView

from pasta import Node

COLUMNS = ["Height", "Hash", "Sender", "Receiver", "Amount", "Mint", "Validator", "Diff"]


class BlockchainView(QDockWidget):
    """Dock widget that displays the current blockchain in a table."""

    def __init__(self, node: Node, parent: _t.Optional[object] = None) -> None:  # noqa: D401
        super().__init__("Blockchain", parent)
        self.node = node
        self.table = QTableView()
        self.table.doubleClicked.connect(self._show_details)
        self.setWidget(self.table)

        self.model = QStandardItemModel(0, len(COLUMNS))
        self.model.setHorizontalHeaderLabels(COLUMNS)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.timer = QTimer(self)
        self.timer.setInterval(2_000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.refresh)
        self.addAction(self.refresh_action)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.refresh()

    def _show_details(self, idx):
        row = idx.row()
        chain = self.node.get_blockchain()
        if row < len(chain):
            from pasta.frontends.desktop.widgets.block_details import BlockDetailsDialog
            BlockDetailsDialog(f"Block #{row}", chain[row], self).exec()

    def refresh(self):  # noqa: D401 slot
        chain = self.node.get_blockchain()
        self.model.setRowCount(len(chain))
        for idx, block in enumerate(chain):
            values = [
                str(idx),
                (block.get("block_hash") or "")[:12],
                block.get("sender_address", "")[:10],
                block.get("receiver_address", "")[:10],
                f"{block.get('amount', 0):.4f}",
                f"{block.get('mint_amount', 0):.3f}",
                (block.get("validator_address") or "")[:10],
                str(block.get("required_difficulty", 0)),
            ]
            for col, v in enumerate(values):
                self.model.setItem(idx, col, QStandardItem(v))
