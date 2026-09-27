from __future__ import annotations

import typing as _t

from PySide6.QtCore import QTimer
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDockWidget, QHeaderView, QTableView

from pasta import Node

COLUMNS = ["tx_id", "State", "Sender", "Receiver", "Amount", "Mint"]


class MempoolView(QDockWidget):
    """Dock widget that shows the current mempool."""

    def __init__(self, node: Node, parent: _t.Optional[object] = None):
        super().__init__("Mempool", parent)
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
        self.refresh()

    def _show_details(self, idx):
        row = idx.row()
        mp = self.node.get_mempool()
        if row < len(mp):
            from pasta.frontends.desktop.widgets.block_details import BlockDetailsDialog
            BlockDetailsDialog(f"Mempool TX {mp[row]['tx_id'][:12]}", mp[row], self).exec()

    def refresh(self):
        mp = self.node.get_mempool()
        self.model.setRowCount(len(mp))
        for idx, tx in enumerate(mp):
            values = [
                tx["tx_id"][:12],
                tx.get("state", ""),
                tx.get("sender_address", "")[:10],
                tx.get("receiver_address", "")[:10],
                f"{tx.get('amount', 0):.4f}",
                f"{tx.get('mint_amount', 0):.3f}",
            ]
            for col, v in enumerate(values):
                self.model.setItem(idx, col, QStandardItem(v))
