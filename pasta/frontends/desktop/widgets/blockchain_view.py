from __future__ import annotations

import typing as _t

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDockWidget, QTableView, QHeaderView

from pasta import Node


class BlockchainView(QDockWidget):
    """Dock widget that displays the current blockchain in a table."""

    def __init__(self, node: Node, parent: _t.Optional[object] = None) -> None:  # noqa: D401
        super().__init__("Blockchain", parent)
        self.node = node
        self.table = QTableView()
        self.table.doubleClicked.connect(self._show_details)
        self.setWidget(self.table)

        self.model = QStandardItemModel(0, 4)
        self.model.setHorizontalHeaderLabels(["Height", "Hash", "Sender", "Receiver"])
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Refresh timer
        self.timer = QTimer(self)
        self.timer.setInterval(2_000)  # 2 seconds
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

        # Manual refresh action (context menu)
        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.refresh)
        self.addAction(self.refresh_action)
        from PySide6.QtCore import Qt
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

        self.refresh()

    # ------------------------------------------------------------------
    def _show_details(self, idx):
        row = idx.row()
        chain = self.node.get_blockchain()
        if row < len(chain):
            from pasta.frontends.desktop.widgets.block_details import BlockDetailsDialog
            dlg = BlockDetailsDialog(f"Block #{row}", chain[row], self)
            dlg.exec()

    def refresh(self):  # noqa: D401 slot
        chain = self.node.get_blockchain()
        self.model.setRowCount(len(chain))
        for idx, block in enumerate(chain):
            self.model.setItem(idx, 0, QStandardItem(str(idx)))
            self.model.setItem(idx, 1, QStandardItem(block.get("block_hash", "")[:10]))
            self.model.setItem(idx, 2, QStandardItem(block.get("sender_address", "")[:10]))
            self.model.setItem(idx, 3, QStandardItem(block.get("receiver_address", "")[:10]))
