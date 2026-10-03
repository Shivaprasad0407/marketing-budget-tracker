"""Checks that the accounting logic gives the numbers it should."""
import pytest

from tracker.logic import (ACCRUALS_PREPAIDS, BY_CHANNEL, CHECK_COST_CENTRE,
                           CHECK_DUPLICATES, CHECK_OVERDUE, MONTHLY, connect, run)


@pytest.fixture(scope="module")
def con():
    return connect()


def test_spreading_keeps_every_euro(con):
    # Spreading costs over months must not create or lose money.
    rec = con.execute("SELECT SUM(recognised_eur) FROM recognised").fetchone()[0]
    spend = con.execute("SELECT SUM(amount_eur) FROM spend").fetchone()[0]
    assert rec == pytest.approx(spend, abs=0.01)


def test_annual_contract_is_twelve_equal_parts(con):
    rows = con.execute("""
        SELECT recognised_eur FROM recognised WHERE line_id = 'L0217'""").fetchall()
    assert len(rows) == 12
    assert all(v == pytest.approx(8000) for (v,) in rows)


def test_month_end_balances(con):
    acc = run(con, ACCRUALS_PREPAIDS)
    assert len(acc) == 9                                   # January to September
    assert acc["prepaid_eur"].iloc[0] == 132_000           # 144,000 minus January
    assert acc["prepaid_eur"].iloc[-1] == 36_000           # three months left
    assert acc["prepaid_eur"].diff().dropna().eq(-12_000).all()
    assert acc["accrual_eur"].iloc[0] == 365_429
    assert acc["accrual_eur"].iloc[-1] == 483_285


def test_budget_vs_actual(con):
    m = run(con, MONTHLY)
    assert len(m) == 9
    assert m["actual_eur"].sum() == pytest.approx(3_472_873, abs=1)


def test_paid_social_is_the_biggest_overspend(con):
    ch = run(con, BY_CHANNEL)
    assert ch.iloc[0]["channel"] == "Paid Social"


def test_planted_issues_are_found(con):
    assert len(run(con, CHECK_COST_CENTRE)) == 3
    assert len(run(con, CHECK_DUPLICATES)) == 1
    assert len(run(con, CHECK_OVERDUE)) == 2
