"""Smoke test of the desktop app, offscreen, on a private chain (no network)."""
import os
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from pasta.frontends.desktop.app import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def settle(app, window, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if not window._jobs and not window._syncing:
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("background work did not finish")


def test_send_and_confirm_between_two_wallets(qapp, tmp_path):
    w = MainWindow(home=str(tmp_path), mode="local", poll=False)
    first = w.current_wallet()                      # created on first run; holds the private chain's genesis coins
    assert w.balance.text() == "10"
    assert "Private chain" in w.conn.text()

    second = w.add_wallet("Second")
    w._fill_wallets(first.address)
    w._wallet_changed()
    w.do_send(second.address, "2.5")
    settle(qapp, w)
    assert "waiting for another user" in w.send_msg.text()
    assert w.balance.text() == "10"                 # not final yet
    assert "2.5 PASTA of this is committed" in w.pending_note.text()

    w._fill_wallets(second.address)
    w._wallet_changed()
    waiting = next(t for t in w.backend.get_mempool() if t["state"] == "B" and t["amount"])
    w.do_confirm(waiting["tx_id"])
    settle(qapp, w)
    assert "Confirmed 2.5 PASTA" in w.confirm_msg.text()
    assert w.balance.text() == "2.5"
    assert w.table.rowCount() == 2                  # the payment and the first block; validation-only rows hidden
    assert w.backend.verify() == []

    w.do_send(first.address, "999")
    settle(qapp, w)
    assert "Not sent" in w.send_msg.text()
    w.do_send(first.address, "abc")
    assert "Enter an amount" in w.send_msg.text()
    w.close()

    again = MainWindow(home=str(tmp_path), poll=False)      # remembers the mode, the wallets and the chain
    assert "Private chain" in again.conn.text()
    assert [x.name for x in again.store.wallets] == [first.name, "Second"]
    assert again.backend.balance_for(second.address) == 250_000_000
    again.close()
