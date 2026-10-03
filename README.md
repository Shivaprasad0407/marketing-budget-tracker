# Marketing Budget Tracker

A Streamlit app that tracks marketing spend against budget on an accrual basis, shows month-end accruals and prepaid expenses, and flags data problems before they reach a report. All numbers come from SQL (DuckDB).

**All data is synthetic.** Every vendor, amount and invoice is invented by `data/generate_data.py`. The app shows the workflow, not any real company's numbers.

## What the app shows

1. **Headline:** budget, actual and variance for January to September 2026.
2. **Budget vs actual per month**, and **variance by channel** with an adjustable flag.
3. **Accruals and prepaids at each month end** (the balance sheet view).
4. **Data checks:** costs booked to the wrong cost centre, duplicate invoices, and finished services still not invoiced after 60 days.

## Accounting rules

- Cost goes to the P&L over the **service period**, split evenly by month. The invoice date does not move the P&L.
- Service used but not invoiced at month end is an **accrual**.
- Invoice received but service not used yet is a **prepaid expense**, released month by month.
- Simplified on purpose: no daily proration for mid-month services, no VAT, no FX.

## What the data shows

- Spend is 2.5% under budget year to date. Paid Social is the only channel over budget, driven by May to July. Influencer is about 32% under.
- Prepaid: two annual influencer contracts (144,000 paid in January) fall by 12,000 a month, from 132,000 at the end of January to 36,000 at the end of September.
- Accrual: mostly the current month's spend, because invoices arrive 5 to 25 days after month end. At the end of September it also includes two August invoices and two Brand invoices from May and June that are overdue.
- Checks find 3 cost centre errors, 1 duplicate invoice and 2 overdue invoices.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
streamlit run app.py
pytest -q
```

## Files

- `app.py`: the Streamlit page.
- `tracker/logic.py`: all SQL in one place (spreading costs over months, budget vs actual, month-end balances, data checks).
- `tests/test_logic.py`: checks that spreading keeps every euro, that the contract releases in 12 equal parts, the month-end balances, and that every planted issue is found.
- `data/`: the three CSV files and the generator.

## Stack

Python, SQL (DuckDB), pandas, Streamlit, pytest.
