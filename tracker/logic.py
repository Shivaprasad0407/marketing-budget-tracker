"""All the SQL for the Marketing Budget Tracker, in one place.

app.py shows the results. This file does the work, so the tests can
check the numbers without starting Streamlit.

Accounting rules (simplified on purpose):
  * Cost goes to the P&L over the SERVICE period, split evenly by month.
    The invoice date does not move the P&L (accrual basis).
  * Service used, invoice not received yet at month end  -> ACCRUAL.
  * Invoice received, service not used yet at month end  -> PREPAID.
"""
from pathlib import Path

import duckdb

DATA = Path(__file__).resolve().parent.parent / "data"
LAST_CLOSED_MONTH = "2026-09-01"   # September 2026 is the last closed month


def _date(col: str) -> str:
    """Read a date written as 2026-01-31 or as 31-01-2026 (Excel re-saves CSVs that way)."""
    return (f"COALESCE(TRY_STRPTIME({col}, '%Y-%m-%d'), "
            f"TRY_STRPTIME({col}, '%d-%m-%Y'))::DATE")


def connect() -> duckdb.DuckDBPyConnection:
    """Load the three CSV files into an in-memory DuckDB database."""
    con = duckdb.connect()
    con.execute(f"""
        CREATE TABLE spend AS
        SELECT line_id, vendor, NULLIF(invoice_no, '') AS invoice_no,
               channel, market, cost_center_booked,
               {_date('service_start')} AS service_start,
               {_date('service_end')}   AS service_end,
               CAST(amount_eur AS DOUBLE) AS amount_eur,
               {_date("NULLIF(invoice_date, '')")} AS invoice_date
        FROM read_csv('{(DATA / 'spend.csv').as_posix()}', all_varchar = true)
    """)
    con.execute(f"""
        CREATE TABLE budget AS
        SELECT {_date('month')} AS month, market, channel,
               CAST(budget_eur AS DOUBLE) AS budget_eur
        FROM read_csv('{(DATA / 'budget.csv').as_posix()}', all_varchar = true)
    """)
    con.execute(f"""
        CREATE TABLE channel_map AS
        SELECT * FROM read_csv_auto('{(DATA / 'channel_map.csv').as_posix()}')
    """)
    # Step 1: spread every cost line evenly over the months of its service period.
    con.execute("""
        CREATE TABLE recognised AS
        SELECT s.line_id, s.channel, s.market,
               CAST(m.month AS DATE) AS month,
               s.amount_eur / (date_diff('month', s.service_start, s.service_end) + 1) AS recognised_eur
        FROM spend s,
             range(date_trunc('month', s.service_start),
                   date_trunc('month', s.service_end) + INTERVAL 1 MONTH,
                   INTERVAL 1 MONTH) AS m(month)
    """)
    return con


# ---------------------------------------------------------------- budget vs actual
MONTHLY = f"""
WITH actual AS (
    SELECT month, SUM(recognised_eur) AS actual_eur
    FROM recognised
    GROUP BY month
),
plan AS (
    SELECT month, SUM(budget_eur) AS budget_eur
    FROM budget
    GROUP BY month
)
SELECT p.month, p.budget_eur, COALESCE(a.actual_eur, 0) AS actual_eur
FROM plan p
LEFT JOIN actual a USING (month)
WHERE p.month <= DATE '{LAST_CLOSED_MONTH}'
ORDER BY p.month
"""

BY_CHANNEL = f"""
WITH actual AS (
    SELECT channel, SUM(recognised_eur) AS actual_eur
    FROM recognised
    WHERE month <= DATE '{LAST_CLOSED_MONTH}'
    GROUP BY channel
),
plan AS (
    SELECT channel, SUM(budget_eur) AS budget_eur
    FROM budget
    WHERE month <= DATE '{LAST_CLOSED_MONTH}'
    GROUP BY channel
)
SELECT p.channel, p.budget_eur, a.actual_eur,
       a.actual_eur - p.budget_eur                  AS variance_eur,
       (a.actual_eur - p.budget_eur) / p.budget_eur AS variance_pct
FROM plan p
LEFT JOIN actual a USING (channel)
ORDER BY variance_eur DESC
"""

# ---------------------------------------------------------------- balance sheet view
ACCRUALS_PREPAIDS = f"""
WITH month_ends AS (
    SELECT CAST(m AS DATE) AS month
    FROM range(DATE '2026-01-01', DATE '{LAST_CLOSED_MONTH}' + INTERVAL 1 MONTH, INTERVAL 1 MONTH) AS t(m)
),
per_line AS (                       -- every line at every month end
    SELECT me.month, s.line_id, s.amount_eur, s.invoice_date,
           COALESCE(SUM(r.recognised_eur), 0) AS rec_to_date
    FROM month_ends me
    CROSS JOIN spend s
    LEFT JOIN recognised r
           ON r.line_id = s.line_id
          AND r.month <= me.month   -- used up TO DATE, not just this month
    GROUP BY me.month, s.line_id, s.amount_eur, s.invoice_date
)
SELECT last_day(month) AS month_end,
       ROUND(SUM(CASE WHEN invoice_date IS NULL OR invoice_date > last_day(month)
                      THEN rec_to_date ELSE 0 END), 0) AS accrual_eur,
       ROUND(SUM(CASE WHEN invoice_date <= last_day(month)
                      THEN amount_eur - rec_to_date ELSE 0 END), 0) AS prepaid_eur
FROM per_line
GROUP BY month
ORDER BY month
"""

# ---------------------------------------------------------------- data checks
CHECK_COST_CENTRE = """
-- Booked to a different cost centre than the channel should use.
SELECT s.line_id, s.vendor, s.channel, s.market,
       s.cost_center_booked, c.expected_cost_center, s.amount_eur
FROM spend s
JOIN channel_map c USING (channel)
WHERE s.cost_center_booked <> c.expected_cost_center
ORDER BY s.amount_eur DESC
"""

CHECK_DUPLICATES = """
-- Same vendor and same invoice number entered more than once.
SELECT vendor, invoice_no, COUNT(*) AS times_entered,
       SUM(amount_eur) AS total_eur,
       string_agg(line_id, ', ') AS line_ids
FROM spend
WHERE invoice_no IS NOT NULL
GROUP BY vendor, invoice_no
HAVING COUNT(*) > 1
"""

CHECK_OVERDUE = f"""
-- Service ended more than 60 days before the close date, still no invoice.
SELECT line_id, vendor, channel, market, service_end, amount_eur,
       date_diff('day', service_end, last_day(DATE '{LAST_CLOSED_MONTH}')) AS days_without_invoice
FROM spend
WHERE invoice_date IS NULL
  AND date_diff('day', service_end, last_day(DATE '{LAST_CLOSED_MONTH}')) > 60
ORDER BY days_without_invoice DESC
"""


def run(con: duckdb.DuckDBPyConnection, sql: str):
    """Run one query and return a pandas DataFrame."""
    return con.execute(sql).df()
