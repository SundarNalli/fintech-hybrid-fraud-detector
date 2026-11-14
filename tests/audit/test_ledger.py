import sqlite3

import pytest

from hybrid_fraud.audit.ledger import Ledger
from hybrid_fraud.audit.states import IllegalTransition
from hybrid_fraud.audit.trace import render_trace
from hybrid_fraud.core.schemas import PayoutState as S


@pytest.fixture
def ledger():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    return Ledger(conn), conn


def two_steps(led, pid="po_1"):
    led.append(pid, None, S.RECEIVED, "hot_path", [], [], 1.0)
    led.append(pid, S.RECEIVED, S.APPROVED, "hot_path", ["LOW_RISK_SCORE"], ["score 0.00"], 2.0)


def test_rows_are_written_in_order_and_the_chain_verifies(ledger):
    led, _ = ledger
    two_steps(led)
    rows = led.rows_for("po_1")
    assert [r.to_state for r in rows] == ["RECEIVED", "APPROVED"]
    assert led.verify() == (True, None)


def test_an_update_to_the_ledger_is_refused_by_the_database(ledger):
    led, conn = ledger
    two_steps(led)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE ledger SET to_state='BLOCKED' WHERE seq=2")


def test_a_delete_from_the_ledger_is_refused_by_the_database(ledger):
    led, conn = ledger
    two_steps(led)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM ledger WHERE seq=1")


def test_editing_a_row_after_dropping_the_triggers_is_caught_by_the_hash_chain(ledger):
    led, conn = ledger
    two_steps(led)
    conn.execute("DROP TRIGGER ledger_no_update")
    conn.execute("UPDATE ledger SET to_state='BLOCKED' WHERE seq=2")
    assert led.verify() == (False, 2)


def test_removing_a_row_from_the_middle_is_caught_by_the_hash_chain(ledger):
    led, conn = ledger
    two_steps(led, "po_1")
    two_steps(led, "po_2")
    conn.execute("DROP TRIGGER ledger_no_delete")
    conn.execute("DELETE FROM ledger WHERE seq=2")
    ok, bad = led.verify()
    assert not ok and bad == 3


def test_a_payout_cannot_move_backwards_and_nothing_is_written_when_it_tries(ledger):
    led, _ = ledger
    two_steps(led)
    with pytest.raises(IllegalTransition):
        led.append("po_1", S.APPROVED, S.BLOCKED, "policy_wrapper", [], [], 3.0)
    assert len(led.rows_for("po_1")) == 2


def test_the_chain_continues_after_the_ledger_is_reopened(ledger):
    led, conn = ledger
    two_steps(led, "po_1")
    reopened = Ledger(conn)
    assert reopened.head == led.head
    two_steps(reopened, "po_2")
    assert reopened.verify() == (True, None)


def test_the_trace_reads_as_plain_lines_from_the_stored_values(ledger):
    led, _ = ledger
    two_steps(led)
    text = render_trace(led.rows_for("po_1"))
    assert "new -> RECEIVED" in text and "RECEIVED -> APPROVED" in text and "score 0.00" in text
