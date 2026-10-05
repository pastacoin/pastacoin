"""The Pasta Machine: a desktop wallet that is also a node.

By default it follows the public seed as a :class:`pasta.node.replica.Replica`: it keeps its
own copy of the chain, checks every block itself, and shows balances it computed. It can
instead run a private chain on this computer (a full :class:`pasta.node.Node`) and serve it
to other computers.

Launch with ``python -m pasta.frontends.desktop``. ``PASTA_HOME`` overrides where wallets and
chain copies are kept; ``PASTA_SEED`` overrides the node it follows.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import traceback
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QRunnable, QStandardPaths, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from pasta.core.errors import PastaError
from pasta.core.units import format_units, to_units
from pasta.node import Node
from pasta.node.replica import DEFAULT_SEED, Replica
from pasta.wallet import Wallet, WalletStore, confirm, send_payment

APP_NAME = "PastaMachine"
POLL_MS = 3000
LOCAL_PORT = 5000

STYLE = """
QMainWindow, QWidget#page { background: #f7f6f1; }
QWidget { font-family: 'Segoe UI', 'Helvetica Neue', Arial; font-size: 10pt; color: #1d1d1b; }
QFrame#card { background: #ffffff; border: 1px solid #dedcd3; border-radius: 6px; }
QFrame#row { border: none; border-bottom: 1px solid #ecebe4; background: transparent; }
QFrame#notice { background: #f1f0e8; border: none; border-left: 3px solid #c8562c; }
QFrame#bar { background: #ffffff; border: 1px solid #dedcd3; border-radius: 6px; }
QLabel#h { font-size: 11pt; font-weight: 600; }
QLabel#muted, QLabel#small { color: #6c6b64; }
QLabel#small { font-size: 9pt; }
QLabel#balance { font-family: Consolas, 'Courier New', monospace; font-size: 24pt; font-weight: 600; }
QLabel#mono, QLineEdit#mono { font-family: Consolas, 'Courier New', monospace; font-size: 9pt; }
QLabel#address { font-family: Consolas, 'Courier New', monospace; font-size: 9pt; background: #f4f3ec;
                 border-radius: 4px; padding: 6px; }
QLabel#stat { font-family: Consolas, 'Courier New', monospace; font-size: 15pt; font-weight: 600; }
QLabel#mint { color: #17694a; border: 1px solid #17694a; border-radius: 8px; padding: 0 6px; font-size: 9pt; }
QLabel#burn { color: #a33a1a; border: 1px solid #a33a1a; border-radius: 8px; padding: 0 6px; font-size: 9pt; }
QLabel#ok { color: #17694a; }
QLabel#bad { color: #a33a1a; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #c9c7bd; border-radius: 4px; padding: 6px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #2f6fd0; }
QPushButton { background: #ffffff; border: 1px solid #c9c7bd; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background: #f1f0e8; }
QPushButton:disabled { color: #a3a29a; }
QPushButton#primary { background: #2f6fd0; border: 1px solid #2f6fd0; color: #ffffff; font-weight: 600; padding: 7px 18px; }
QPushButton#primary:hover { background: #2760b8; }
QPushButton#primary:disabled { background: #a9c1e6; border-color: #a9c1e6; color: #ffffff; }
QTabWidget::pane { border: 1px solid #dedcd3; border-radius: 6px; background: #ffffff; top: -1px; }
QTabBar::tab { padding: 7px 16px; border: 1px solid transparent; border-bottom: none; color: #6c6b64; }
QTabBar::tab:selected { background: #ffffff; border-color: #dedcd3; color: #1d1d1b; font-weight: 600;
                        border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTableWidget { border: none; gridline-color: #ecebe4; background: #ffffff; }
QHeaderView::section { background: #ffffff; border: none; border-bottom: 1px solid #dedcd3; padding: 6px;
                       color: #6c6b64; font-size: 9pt; }
QScrollArea { border: none; background: #ffffff; }
QWidget#sheet { background: #ffffff; }
QProgressBar { border: none; background: #ecebe4; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #2f6fd0; border-radius: 3px; }
QTextBrowser { border: none; background: #ffffff; }
"""

HOW_IT_WORKS = """
<h3>How a payment becomes final</h3>
<p>PaSta has no miners. The people making payments validate each other's:</p>
<ol>
<li><b>You send.</b> This program signs the payment with your key and hands it to the network.</li>
<li><b>You validate someone else's.</b> To earn the right to be confirmed, your payment first
confirms another waiting payment from a different sender. This program does that for you as soon
as one is available.</li>
<li><b>Someone else confirms yours.</b> The next person to send, or to press Confirm, finalizes
your payment and it joins the chain. Only then does the money move.</li>
</ol>
<p>So a quiet chain is a slow chain: if nobody else is around, your payment waits. To try it
alone, make a second wallet and press Confirm from it.</p>
<h3>Where coins come from</h3>
<p>Nobody is given coins except the 10 PASTA in the first block. Everything else is minted, or
burned, by a rule that watches the size of a typical payment and nudges the supply so that size
stays at its target. Minted coins are added to payments as they are confirmed. The Network tab
shows what the rule is doing.</p>
<h3>What this computer does</h3>
<p>On the public network this program keeps its own copy of the chain and checks every block
itself: signatures, proof-of-work, balances and every mint. The balance you see is the one this
computer worked out. One node, the seed, still decides the order of transactions; that changes
when nodes learn to talk to each other.</p>
<h3>Don't buy pastacoin</h3>
<p>This is a test chain. Its coins have no value and it can be reset at any time. Your wallets
are kept in a file on this computer that is <b>not encrypted</b>.</p>
"""


# ------------------------------------------------------------------ helpers ----

def app_home() -> str:
    home = os.environ.get("PASTA_HOME")
    if not home:
        home = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~/.pastamachine")
    os.makedirs(home, exist_ok=True)
    return home


def blocks(n: int) -> str:
    return f"{n} block" if n == 1 else f"{n} blocks"


def short(address: str) -> str:
    return address if len(address) <= 14 else f"{address[:6]}…{address[-4:]}"


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:  # worker thread
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:  # noqa: BLE001 - reported to the UI thread
            if not isinstance(exc, (PastaError, ValueError)):
                traceback.print_exc()
            self.signals.failed.emit(exc)


def card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName="card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    if title:
        layout.addWidget(QLabel(title, objectName="h"))
    return frame, layout


def label(text: str = "", name: str = "", wrap: bool = False, selectable: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if selectable:
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


def clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()


# -------------------------------------------------------------- main window ----

class MainWindow(QMainWindow):
    def __init__(self, home: Optional[str] = None, seed_url: Optional[str] = None, poll: bool = True,
                 mode: Optional[str] = None) -> None:
        super().__init__()
        self.home = home or app_home()
        self.settings_path = os.path.join(self.home, "settings.json")
        self.settings = self._load_settings()
        self.store = WalletStore(os.path.join(self.home, "wallets.json"))
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)          # one network operation at a time, in order
        self._jobs: List[_Job] = []
        self._syncing = False
        self._drawn: Dict[str, Any] = {}
        self._server = None
        self.backend: Any = None

        self.setWindowTitle("The Pasta Machine")
        self.resize(1180, 760)
        self._build_ui()
        self._build_menu()

        if not self.store.wallets:
            self.store.create("My wallet")
        self._fill_wallets(self.settings.get("wallet"))

        mode = mode or ("seed" if seed_url else self.settings.get("mode", "seed"))
        url = seed_url or os.environ.get("PASTA_SEED") or self.settings.get("seed_url") or DEFAULT_SEED
        if mode == "local":
            self.use_local_chain()
        else:
            self.use_seed(url)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync)
        if poll:
            self.timer.start(POLL_MS)

    # ---------------------------------------------------------------- settings
    def _load_settings(self) -> Dict[str, Any]:
        try:
            with open(self.settings_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        with open(self.settings_path, "w", encoding="utf-8") as fh:
            json.dump(self.settings, fh, indent=1)

    # --------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        page = QWidget(objectName="page")
        self.setCentralWidget(page)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        # connection bar
        bar = QFrame(objectName="bar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 8, 12, 8)
        self.dot = label("●")
        self.conn = label("Starting…")
        self.conn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.btn_verify = QPushButton("Check the chain")
        self.btn_verify.clicked.connect(self.check_chain)
        bl.addWidget(self.dot)
        bl.addWidget(self.conn, 1)
        bl.addWidget(self.btn_verify)
        outer.addWidget(bar)

        self.banner = QFrame(objectName="notice")
        nl = QHBoxLayout(self.banner)
        nl.setContentsMargins(12, 8, 12, 8)
        self.banner_text = label("", wrap=True)
        self.banner_button = QPushButton("Start over from the seed")
        self.banner_button.clicked.connect(self.resync)
        nl.addWidget(self.banner_text, 1)
        nl.addWidget(self.banner_button)
        self.banner.hide()
        outer.addWidget(self.banner)

        body = QHBoxLayout()
        body.setSpacing(14)
        outer.addLayout(body, 1)

        # ---- left column: wallet and send
        left = QVBoxLayout()
        left.setSpacing(12)
        body.addLayout(left, 0)

        wallet_card, wl = card("Your wallet")
        wallet_card.setFixedWidth(400)
        self.wallet_box = QComboBox()
        self.wallet_box.currentIndexChanged.connect(self._wallet_changed)
        wl.addWidget(self.wallet_box)
        bal_row = QHBoxLayout()
        self.balance = label("0", "balance", selectable=True)
        bal_row.addWidget(self.balance)
        bal_row.addWidget(label("PASTA", "muted"), 0, Qt.AlignBottom)
        bal_row.addStretch(1)
        wl.addLayout(bal_row)
        self.pending_note = label("", "small")
        wl.addWidget(self.pending_note)
        self.address = label("", "address", wrap=True, selectable=True)
        wl.addWidget(self.address)
        hint = QHBoxLayout()
        hint.addWidget(label("Your address. Give it to someone so they can pay you.", "small", wrap=True), 1)
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy_address)
        hint.addWidget(copy)
        wl.addLayout(hint)
        buttons = QHBoxLayout()
        for text, slot in (("New wallet", self.new_wallet_dialog), ("Import", self.import_dialog),
                           ("Back up", self.backup_dialog)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        wl.addLayout(buttons)
        left.addWidget(wallet_card)

        send_card, sl = card("Send")
        send_card.setFixedWidth(400)
        sl.addWidget(label("To (address)", "small"))
        self.to_edit = QLineEdit(objectName="mono")
        self.to_edit.setPlaceholderText("Paste the receiver's address")
        sl.addWidget(self.to_edit)
        sl.addWidget(label("Amount (PASTA)", "small"))
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.5")
        self.amount_edit.returnPressed.connect(self.send_clicked)
        sl.addWidget(self.amount_edit)
        self.available = label("", "small")
        sl.addWidget(self.available)
        send_row = QHBoxLayout()
        self.btn_send = QPushButton("Send", objectName="primary")
        self.btn_send.clicked.connect(self.send_clicked)
        send_row.addWidget(self.btn_send)
        send_row.addStretch(1)
        sl.addLayout(send_row)
        self.send_msg = label("", "small", wrap=True)
        sl.addWidget(self.send_msg)
        left.addWidget(send_card)
        left.addStretch(1)

        # ---- right column: tabs
        self.tabs = QTabWidget()
        body.addWidget(self.tabs, 1)

        # payments tab
        pay_tab = QScrollArea()
        pay_tab.setWidgetResizable(True)
        pay_inner = QWidget(objectName="sheet")
        pay_tab.setWidget(pay_inner)
        pl = QVBoxLayout(pay_inner)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.addWidget(label("Waiting to be confirmed", "h"))
        pl.addWidget(label("Payments waiting for someone other than their sender. Confirming one costs you "
                           "nothing and finalizes it.", "small", wrap=True))
        self.confirm_list = QVBoxLayout()
        self.confirm_list.setSpacing(0)
        pl.addLayout(self.confirm_list)
        self.confirm_msg = label("", "small", wrap=True)
        pl.addWidget(self.confirm_msg)
        pl.addSpacing(10)
        pl.addWidget(label("Your payments", "h"))
        self.payments_list = QVBoxLayout()
        self.payments_list.setSpacing(0)
        pl.addLayout(self.payments_list)
        pl.addStretch(1)
        self.tabs.addTab(pay_tab, "Payments")

        # activity tab
        act_tab = QWidget()
        al = QVBoxLayout(act_tab)
        al.setContentsMargins(14, 12, 14, 12)
        al.addWidget(label("The newest blocks on the chain. One block is one transaction. Coins the stability "
                           "rule minted into a payment, or burned from it, are shown next to it.", "small", wrap=True))
        self.show_zero = QCheckBox("Also show validation-only blocks")
        self.show_zero.toggled.connect(lambda _: self.refresh(force=True))
        al.addWidget(self.show_zero)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "From", "To", "Amount", "Mint / burn", "Confirmed by"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for column in (0, 3, 4):
            self.table.horizontalHeaderItem(column).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        al.addWidget(self.table, 1)
        self.table_note = label("", "small")
        al.addWidget(self.table_note)
        self.tabs.addTab(act_tab, "Activity")

        # network tab
        net_tab = QWidget()
        nl2 = QVBoxLayout(net_tab)
        nl2.setContentsMargins(14, 12, 14, 12)
        nl2.addWidget(label("Nobody is given coins except the 10 PASTA in the first block. Everything else is "
                            "minted, or burned, by a rule that watches the size of a typical payment and nudges "
                            "the supply so that size stays at its target.", "small", wrap=True))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.stats: Dict[str, tuple[QLabel, QLabel]] = {}
        tiles = [("supply", "Supply"), ("minted", "Minted / burned"), ("target", "Target payment"),
                 ("median", "Typical payment now"), ("signal", "Signal"), ("cap", "Cap"),
                 ("budget", "This period's budget"), ("period", "Next adjustment")]
        for i, (key, title) in enumerate(tiles):
            tile, tl = card()
            tl.addWidget(label(title, "small"))
            value = label("–", "stat", selectable=True)
            note = label("", "small", wrap=True)
            tl.addWidget(value)
            tl.addWidget(note)
            if key == "period":
                self.period_bar = QProgressBar()
                self.period_bar.setTextVisible(False)
                tl.addWidget(self.period_bar)
            tl.addStretch(1)
            self.stats[key] = (value, note)
            grid.addWidget(tile, i // 4, i % 4)
        nl2.addLayout(grid)
        self.node_note = label("", "small", wrap=True)
        nl2.addWidget(self.node_note)
        nl2.addStretch(1)
        self.tabs.addTab(net_tab, "Network")

        how = QTextBrowser()
        how.setHtml(HOW_IT_WORKS)
        how.setOpenExternalLinks(True)
        self.tabs.addTab(how, "How it works")

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Network")
        self.act_public = QAction("Public network (seed.pastacoin.org)", self, checkable=True)
        self.act_public.triggered.connect(lambda: self.use_seed(DEFAULT_SEED))
        self.act_other = QAction("Another node…", self, checkable=True)
        self.act_other.triggered.connect(self.other_node_dialog)
        self.act_local = QAction("Private chain on this computer", self, checkable=True)
        self.act_local.triggered.connect(self.use_local_chain)
        self.act_serve = QAction(f"Let other computers join my private chain (port {LOCAL_PORT})", self, checkable=True)
        self.act_serve.triggered.connect(self.toggle_serve)
        for a in (self.act_public, self.act_other, self.act_local):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(self.act_serve)
        menu.addSeparator()
        menu.addAction("Start over from the seed (discard the copy on this computer)", self.resync)

        wallet_menu = self.menuBar().addMenu("&Wallet")
        wallet_menu.addAction("New wallet…", self.new_wallet_dialog)
        wallet_menu.addAction("Import from a backup file…", self.import_dialog)
        wallet_menu.addAction("Import from a private key…", self.import_key_dialog)
        wallet_menu.addAction("Back up this wallet…", self.backup_dialog)
        wallet_menu.addAction("Rename this wallet…", self.rename_dialog)
        wallet_menu.addAction("Open the folder where wallets are kept", self.open_home)

    # ----------------------------------------------------------------- network
    @property
    def is_replica(self) -> bool:
        return isinstance(self.backend, Replica)

    def _set_mode_checks(self) -> None:
        seed = self.backend.seed_url if self.is_replica else ""
        self.act_public.setChecked(self.is_replica and seed == DEFAULT_SEED)
        self.act_other.setChecked(self.is_replica and seed != DEFAULT_SEED)
        self.act_local.setChecked(not self.is_replica)
        self.act_serve.setEnabled(not self.is_replica)
        if self.is_replica and self._server:
            self._stop_server()

    def use_seed(self, url: str) -> None:
        url = url.strip().rstrip("/")
        name = re.sub(r"[^A-Za-z0-9.-]+", "_", url.split("://", 1)[-1])
        self.backend = Replica(url, os.path.join(self.home, "chains", f"{name}.json"))
        self.settings.update(mode="seed", seed_url=url)
        self._save_settings()
        self._set_mode_checks()
        self.refresh(force=True)
        self.sync()

    def use_local_chain(self) -> None:
        path = os.path.join(self.home, "private-chain.json")
        wallet = self.current_wallet()
        self.backend = Node(path, genesis_receiver=None if os.path.exists(path) else wallet.address)
        self.settings.update(mode="local")
        self._save_settings()
        self._set_mode_checks()
        self.refresh(force=True)

    def other_node_dialog(self) -> None:
        current = self.backend.seed_url if self.is_replica else "http://localhost:5000"
        url, ok = QInputDialog.getText(self, "Another node", "Address of the node to follow:", text=current)
        if ok and url.strip():
            self.use_seed(url)
        else:
            self._set_mode_checks()

    def toggle_serve(self) -> None:
        if self._server:
            self._stop_server()
        elif not self.is_replica:
            from werkzeug.serving import make_server
            try:
                self._server = make_server("0.0.0.0", LOCAL_PORT, self.backend.create_flask_app(), threaded=True)
            except OSError as exc:
                QMessageBox.warning(self, "Could not start", f"Port {LOCAL_PORT} is not available: {exc}")
                self._server = None
            else:
                threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.act_serve.setChecked(bool(self._server))
        self.refresh(force=True)

    def _stop_server(self) -> None:
        server, self._server = self._server, None
        if server:
            threading.Thread(target=server.shutdown, daemon=True).start()
        self.act_serve.setChecked(False)

    def resync(self) -> None:
        if not self.is_replica:
            return
        if QMessageBox.question(self, "Start over", "Discard the copy of the chain on this computer and download "
                                "it again from the seed? Your wallets are not touched.") != QMessageBox.Yes:
            return
        self.backend.reset()
        self.refresh(force=True)
        self.sync()

    # ------------------------------------------------------------------- async
    def run_async(self, fn: Callable[[], Any], on_done: Callable[[Any], None],
                  on_error: Optional[Callable[[Exception], None]] = None) -> None:
        job = _Job(fn)
        self._jobs.append(job)

        def finish(handler, value):
            if job in self._jobs:
                self._jobs.remove(job)
            if handler:
                handler(value)
        job.signals.done.connect(lambda v: finish(on_done, v))
        job.signals.failed.connect(lambda e: finish(on_error, e))
        self.pool.start(job)

    def sync(self) -> None:
        """Ask the seed for anything new (replica), then redraw."""
        if not self.is_replica:
            self.refresh()
            return
        if self._syncing:
            return
        self._syncing = True
        backend = self.backend

        def done(_):
            self._syncing = False
            if backend is self.backend:
                self.refresh()
        self.run_async(backend.sync, done, done)

    # ------------------------------------------------------------------ wallets
    def current_wallet(self) -> Wallet:
        i = self.wallet_box.currentIndex()
        return self.store.wallets[i if 0 <= i < len(self.store.wallets) else 0]

    def _fill_wallets(self, select: Optional[str] = None) -> None:
        self.wallet_box.blockSignals(True)
        self.wallet_box.clear()
        for w in self.store.wallets:
            self.wallet_box.addItem(w.name)
        index = next((i for i, w in enumerate(self.store.wallets) if w.address == select), 0)
        self.wallet_box.setCurrentIndex(index)
        self.wallet_box.blockSignals(False)

    def _wallet_changed(self) -> None:
        self.settings["wallet"] = self.current_wallet().address
        self._save_settings()
        self.send_msg.setText("")
        self.confirm_msg.setText("")
        if self.backend is not None:
            self.refresh(force=True)

    def name_of(self, address: str) -> str:
        if address == "GENESIS":
            return "chain start"
        w = self.store.by_address(address)
        return f"{w.name} (you)" if w else short(address)

    def copy_address(self) -> None:
        QGuiApplication.clipboard().setText(self.current_wallet().address)
        self.send_msg.setText("Address copied.")

    def add_wallet(self, name: str = "") -> Wallet:
        wallet = self.store.create(name)
        self._fill_wallets(wallet.address)
        self._wallet_changed()
        return wallet

    def new_wallet_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "New wallet", "A name for the new wallet:",
                                        text=f"Wallet {len(self.store.wallets) + 1}")
        if ok:
            self.add_wallet(name)

    def import_file(self, path: str) -> Optional[Wallet]:
        try:
            wallet = self.store.import_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not import", str(exc))
            return None
        self._fill_wallets(wallet.address)
        self._wallet_changed()
        return wallet

    def import_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import a wallet backup", "", "Wallet backup (*.json);;All files (*)")
        if path:
            self.import_file(path)

    def import_key_dialog(self) -> None:
        key, ok = QInputDialog.getText(self, "Import from a private key", "Private key:")
        if not ok or not key.strip():
            return
        try:
            wallet = self.store.import_key(key)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not import", str(exc))
            return
        self._fill_wallets(wallet.address)
        self._wallet_changed()

    def backup_dialog(self) -> None:
        wallet = self.current_wallet()
        default = re.sub(r"[^A-Za-z0-9_-]+", "-", wallet.name).strip("-") or "wallet"
        path, _ = QFileDialog.getSaveFileName(self, "Back up this wallet", f"pasta-{default}.json", "Wallet backup (*.json)")
        if path:
            self.store.export_file(wallet, path)
            QMessageBox.information(self, "Backed up", "Saved. Anyone who has this file can spend from this wallet, "
                                    "so keep it somewhere only you can reach.")

    def rename_dialog(self) -> None:
        wallet = self.current_wallet()
        name, ok = QInputDialog.getText(self, "Rename wallet", "Name:", text=wallet.name)
        if ok:
            self.store.rename(wallet, name)
            self._fill_wallets(wallet.address)
            self.refresh(force=True)

    def open_home(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.home))

    # ------------------------------------------------------------------ actions
    def send_clicked(self) -> None:
        self.do_send(self.to_edit.text(), self.amount_edit.text())

    def do_send(self, receiver: str, amount_text: str) -> None:
        wallet, backend = self.current_wallet(), self.backend
        receiver = receiver.strip()
        try:
            amount = to_units(amount_text)
        except ValueError:
            self._say(self.send_msg, "Enter an amount in PASTA, for example 0.5 (up to 8 decimal places).", bad=True)
            return
        if amount <= 0:
            self._say(self.send_msg, "Enter an amount greater than zero.", bad=True)
            return
        if not receiver:
            self._say(self.send_msg, "Paste the receiver's address.", bad=True)
            return
        if receiver == wallet.address:
            self._say(self.send_msg, "That is this wallet's own address. Pick another wallet to pay.", bad=True)
            return
        self.btn_send.setEnabled(False)
        self._say(self.send_msg, "Sending…")

        def done(result):
            self.btn_send.setEnabled(True)
            self.amount_edit.clear()
            self._say(self.send_msg, result["note"], good=True)
            self.refresh(force=True)

        def failed(exc):
            self.btn_send.setEnabled(True)
            self._say(self.send_msg, f"Not sent: {exc}", bad=True)
            self.refresh(force=True)
        self.run_async(lambda: send_payment(backend, wallet, receiver, amount), done, failed)

    def do_confirm(self, tx_id: str) -> None:
        wallet, backend = self.current_wallet(), self.backend
        self._say(self.confirm_msg, "Confirming…")

        def done(result):
            block = result["finalized"]
            what = (f"{format_units(block['amount'])} PASTA from {self.name_of(block['sender_address'])}"
                    if block["amount"] else "a validation-only transaction")
            self._say(self.confirm_msg, f"Confirmed {what}. It is on the chain now. Your own transaction "
                      "that did the confirming waits for someone else in turn.", good=True)
            self.refresh(force=True)

        def failed(exc):
            self._say(self.confirm_msg, f"Not confirmed: {exc}", bad=True)
            self.refresh(force=True)
        self.run_async(lambda: confirm(backend, wallet, tx_id), done, failed)

    def check_chain(self) -> None:
        backend = self.backend
        self.btn_verify.setEnabled(False)

        def done(problems):
            self.btn_verify.setEnabled(True)
            n = backend.status()["height"]
            if problems:
                QMessageBox.warning(self, "Chain problems", "\n".join(problems[:20]))
            else:
                QMessageBox.information(self, "Chain checked", f"All {n} blocks check out on this computer: links, "
                                        "signatures, proof-of-work, balances and every mint.")
        self.run_async(backend.verify, done, lambda exc: (self.btn_verify.setEnabled(True),
                                                          QMessageBox.warning(self, "Could not check", str(exc))))

    @staticmethod
    def _say(lab: QLabel, text: str, good: bool = False, bad: bool = False) -> None:
        lab.setObjectName("ok" if good else "bad" if bad else "small")
        lab.style().unpolish(lab)
        lab.style().polish(lab)
        lab.setText(text)

    # ------------------------------------------------------------------- redraw
    def refresh(self, force: bool = False) -> None:
        backend = self.backend
        if backend is None:
            return
        status = backend.status()
        chain = backend.get_blockchain()
        mempool = backend.get_mempool()
        wallet = self.current_wallet()
        mine = wallet.address

        # connection bar and banner
        seed = status.get("seed")
        waiting = sum(1 for t in mempool if t.get("sender_address") != "GENESIS")
        if seed:
            host = seed["url"].split("://", 1)[-1]
            if seed["online"]:
                behind = max(0, seed["height"] - status["height"])
                text = f"Following {host}  ·  {blocks(status['height'])} checked on this computer  ·  {waiting} waiting"
                if behind:
                    text += f"  ·  {behind} more to check"
                self.dot.setStyleSheet("color: #17694a;")
            else:
                text = (f"Not connected to {host}  ·  showing the {blocks(status['height'])} already on this computer"
                        f"  ·  {seed['error'] or 'connecting…'}")
                self.dot.setStyleSheet("color: #a33a1a;" if seed["error"] else "color: #b8b6ab;")
            self.conn.setText(text)
            problem = seed["diverged"] or ("The seed served a block that does not check out, and this computer "
                                           "refused it: " + "; ".join(seed["rejected"][:2]) if seed["rejected"] else "")
            self.banner_text.setText(problem)
            self.banner_button.setVisible(bool(seed["diverged"]))
            self.banner.setVisible(bool(problem))
            self.btn_send.setEnabled(seed["online"] and not self._sending())
        else:
            serving = f"  ·  other computers can join at port {LOCAL_PORT}" if self._server else ""
            self.conn.setText(f"Private chain on this computer  ·  {blocks(status['height'])}  ·  {waiting} waiting{serving}")
            self.dot.setStyleSheet("color: #2f6fd0;")
            self.banner.hide()
            self.btn_send.setEnabled(not self._sending())

        # wallet card
        balance = backend.balance_for(mine)
        pending = backend.pending_outgoing(mine)
        self.balance.setText(format_units(balance))
        self.pending_note.setText(f"{format_units(pending)} PASTA of this is committed to payments still waiting."
                                  if pending else "")
        half = (len(mine) + 1) // 2
        self.address.setText(mine[:half] + "\n" + mine[half:])      # a label cannot wrap one long word
        self.pending_note.setVisible(bool(pending))
        self.available.setText(f"Available: {format_units(balance - pending)} PASTA")

        signature = (status["height"], tuple((t.get("tx_id"), t.get("state")) for t in mempool), mine,
                     tuple(w.name for w in self.store.wallets), self.show_zero.isChecked())
        if not force and self._drawn.get("sig") == signature:
            self._draw_network(status)
            return
        self._drawn["sig"] = signature

        self._draw_confirm(mempool, mine)
        self._draw_payments(chain, mempool, mine)
        self._draw_activity(chain)
        self._draw_network(status)

    def _sending(self) -> bool:
        return self.send_msg.text() == "Sending…"

    def _row(self, title: str, detail: str, tag: Optional[QLabel] = None, button: Optional[QPushButton] = None) -> QFrame:
        row = QFrame(objectName="row")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 7, 0, 7)
        text = QVBoxLayout()
        text.setSpacing(1)
        top = QHBoxLayout()
        top.addWidget(label(title))
        if tag:
            top.addWidget(tag)
        top.addStretch(1)
        text.addLayout(top)
        text.addWidget(label(detail, "small"))
        h.addLayout(text, 1)
        if button:
            h.addWidget(button)
        return row

    def _mint_tag(self, mint: int) -> Optional[QLabel]:
        if mint > 0:
            return label(f"+{format_units(mint, 4)} minted", "mint")
        if mint < 0:
            return label(f"{format_units(mint, 4)} burned", "burn")
        return None

    def _describe(self, tx: Dict[str, Any], mine: str) -> str:
        amount = tx.get("amount", 0)
        if not amount:
            return "Validation-only transaction"
        if tx.get("sender_address") == mine:
            return f"Sent {format_units(amount)} PASTA to {self.name_of(tx.get('receiver_address', ''))}"
        return f"Received {format_units(amount)} PASTA from {self.name_of(tx.get('sender_address', ''))}"

    def _draw_confirm(self, mempool: List[Dict[str, Any]], mine: str) -> None:
        clear(self.confirm_list)
        waiting = [t for t in mempool if t.get("state") == "B" and t.get("sender_address") != "GENESIS"]
        bootstrap = [t for t in mempool if t.get("state") == "B" and t.get("sender_address") == "GENESIS"]
        if not waiting and not bootstrap:
            self.confirm_list.addWidget(label("Nothing is waiting.", "muted"))
            return
        for tx in waiting:
            amount = tx.get("amount", 0)
            what = f"{format_units(amount)} PASTA" if amount else "Validation-only transaction"
            who = f"from {self.name_of(tx['sender_address'])}"
            if amount:
                who += f" to {self.name_of(tx['receiver_address'])}"
            if tx["sender_address"] == mine:
                self.confirm_list.addWidget(self._row(what, f"{who}  ·  yours: another wallet must confirm it"))
            else:
                button = QPushButton("Confirm")
                button.clicked.connect(lambda _=False, tx_id=tx["tx_id"]: self.do_confirm(tx_id))
                self.confirm_list.addWidget(self._row(what, who, button=button))
        if bootstrap and not waiting:
            self.confirm_list.addWidget(label("Only the chain's opening entry is waiting; the first payment anyone "
                                              "sends will confirm it.", "muted", wrap=True))

    def _draw_payments(self, chain: List[Dict[str, Any]], mempool: List[Dict[str, Any]], mine: str) -> None:
        clear(self.payments_list)
        rows = 0
        for tx in reversed(mempool):
            if mine not in (tx.get("sender_address"), tx.get("receiver_address")):
                continue
            step = ("Step 1 of 3  ·  waiting for another payment to validate" if tx.get("state") == "A"
                    else "Step 2 of 3  ·  waiting for another user to confirm it")
            self.payments_list.addWidget(self._row(self._describe(tx, mine), step))
            rows += 1
        for index in range(len(chain) - 1, 0, -1):
            block = chain[index]
            if mine not in (block.get("sender_address"), block.get("receiver_address")):
                continue
            if not block.get("amount"):
                continue                    # finished validation-only transactions are just noise here
            tag = self._mint_tag(block.get("mint_amount", 0)) if block.get("receiver_address") == mine else None
            detail = f"Final  ·  block {index}  ·  confirmed by {self.name_of(block.get('validator_address') or '')}"
            self.payments_list.addWidget(self._row(self._describe(block, mine), detail, tag=tag))
            rows += 1
            if rows >= 60:
                break
        if chain and chain[0].get("receiver_address") == mine:
            self.payments_list.addWidget(self._row(f"Received {format_units(chain[0]['amount'])} PASTA at the start of the chain",
                                                   "Final  ·  block 0  ·  the only coins anyone was given"))
            rows += 1
        if not rows:
            self.payments_list.addWidget(label("No payments yet for this wallet.", "muted"))

    def _draw_activity(self, chain: List[Dict[str, Any]]) -> None:
        show_zero = self.show_zero.isChecked()
        rows = [(i, b) for i, b in enumerate(chain) if show_zero or b.get("amount") or i == 0]
        rows = list(reversed(rows))[:300]
        self.table.setRowCount(len(rows))
        for r, (i, b) in enumerate(rows):
            mint = b.get("mint_amount", 0)
            cells = [
                str(i),
                self.name_of(b.get("sender_address", "")),
                self.name_of(b.get("receiver_address", "")),
                format_units(b.get("amount", 0)) + ("   first coins" if i == 0 else ""),
                (f"+{format_units(mint, 4)}" if mint > 0 else format_units(mint, 4) if mint < 0 else ""),
                "" if i == 0 else self.name_of(b.get("validator_address") or ""),
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c in (0, 3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setFont(QFont("Consolas", 9))
                if c == 4 and mint:
                    item.setForeground(Qt.darkGreen if mint > 0 else Qt.darkRed)
                self.table.setItem(r, c, item)
        hidden = len(chain) - sum(1 for i, b in enumerate(chain) if b.get("amount") or i == 0)
        self.table_note.setText("" if show_zero or not hidden else f"{hidden} validation-only blocks not shown.")

    def _draw_network(self, status: Dict[str, Any]) -> None:
        s = status["stability"]

        def put(key: str, value: str, note: str) -> None:
            self.stats[key][0].setText(value)
            self.stats[key][1].setText(note)
        put("supply", format_units(s["supply"]), f"PASTA in existence. {format_units(s['genesis_supply'])} came from the first block.")
        put("minted", f"+{format_units(s['minted'], 4)} / −{format_units(s['burned'], 4)}", "Created and destroyed by the rule so far.")
        put("target", format_units(s["target_median"]), "PASTA: the size of a typical payment the rule aims for.")
        put("median", format_units(s["smoothed_median"], 4) if s["period"] else "–",
            "PASTA: smoothed median of recent payments." if s["period"] else "Known after the first 10 payments.")
        signal = s["signal"] * 100
        put("signal", f"{signal:+.0f} %" if s["period"] else "–",
            "Payments are smaller than the target, so the rule mints." if signal < -1 else
            "Payments are larger than the target, so the rule burns." if signal > 1 else
            "Payments are at the target." if s["period"] else "No adjustment yet.")
        put("cap", f"{s['cap_rate'] * 100:.1f} %", "of supply: the most one adjustment may mint or burn.")
        put("budget", f"{'+' if s['period_budget'] >= 0 else ''}{format_units(s['period_budget'], 4)}",
            f"{format_units(abs(s['period_remaining']), 4)} PASTA still to be "
            f"{'minted into' if s['period_budget'] >= 0 else 'burned from'} this period's payments, shared by size.")
        put("period", f"{s['payments_in_period']} of {s['period_payments']}",
            f"payments counted. {s['period']} adjustment{'' if s['period'] == 1 else 's'} so far.")
        self.period_bar.setMaximum(s["period_payments"])
        self.period_bar.setValue(s["payments_in_period"])
        self.node_note.setText("Zero-amount transactions are not counted as payments and receive no mint.  ·  "
                               f"Wallets and the chain copy are kept in {self.home}")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt name
        self.timer.stop()
        self._stop_server()
        self.pool.waitForDone(3000)
        super().closeEvent(event)


def main() -> None:  # pragma: no cover
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
