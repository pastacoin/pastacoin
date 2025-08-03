from __future__ import annotations

import typing as _t

from PySide6.QtCore import QTimer
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QDockWidget, QTableView, QHeaderView

from pasta import Node


class MempoolView(QDockWidget):
    """Dock widget that shows current mempool."""

    def __init__(self, node: Node, parent: _t.Optional[object] = None):
        super().__init__("Mempool", parent)
        self.node = node
        self.table = QTableView()
        self.table.doubleClicked.connect(self._show_details)
        self.setWidget(self.table)

        self.model = QStandardItemModel(0, 3)
        self.model.setHorizontalHeaderLabels(["Index", "Signature", "State"])
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
            dlg = BlockDetailsDialog(f"Mempool TX #{row}", mp[row], self)
            dlg.exec()

    def refresh(self):
        mp = self.node.get_mempool()
        self.model.setRowCount(len(mp))
        for idx, tx in enumerate(mp):
            self.model.setItem(idx, 0, QStandardItem(str(idx)))
            self.model.setItem(idx, 1, QStandardItem(str(tx.get("signature", ""))[:10]))
            self.model.setItem(idx, 2, QStandardItem(tx.get("state", "")))
