"""Marketing Budget Tracker (Streamlit). Synthetic data only.

Run:  streamlit run app.py
"""
import streamlit as st

from tracker.logic import (ACCRUALS_PREPAIDS, BY_CHANNEL, CHECK_COST_CENTRE,
                           CHECK_DUPLICATES, CHECK_OVERDUE, MONTHLY, connect, run)

st.set_page_config(page_title="Marketing Budget Tracker", layout="wide")
st.title("Marketing Budget Tracker")
st.info("Built on synthetic data. Every vendor, amount and invoice is invented. "
        "It shows the workflow, not any real company's numbers.")

con = connect()
EUR = st.column_config.NumberColumn(format="localized")
PCT = st.column_config.NumberColumn(format="percent")

# ---------------------------------------------------------------- 1. headline
monthly = run(con, MONTHLY)
budget, actual = monthly["budget_eur"].sum(), monthly["actual_eur"].sum()

st.header("January to September 2026")
c1, c2, c3 = st.columns(3)
c1.metric("Budget YTD", f"EUR {budget:,.0f}")
c2.metric("Actual YTD (accrual basis)", f"EUR {actual:,.0f}")
c3.metric("Variance", f"EUR {actual - budget:,.0f}", f"{(actual - budget) / budget:+.1%}",
          delta_color="inverse")

# ---------------------------------------------------------------- 2. budget vs actual
st.subheader("Budget vs actual per month")
monthly["month"] = monthly["month"].dt.strftime("%Y-%m")   # 2026-01 sorts correctly as text
monthly = monthly.rename(columns={"budget_eur": "Budget", "actual_eur": "Actual"})
st.bar_chart(monthly, x="month", y=["Budget", "Actual"], stack=False,
             color=["#9aa5b1", "#2e86de"], x_label="Month", y_label="EUR")

st.subheader("Variance by channel, year to date")
threshold = st.slider("Flag channels more than this far off budget (%)", 5, 30, 10)
by_ch = run(con, BY_CHANNEL)
by_ch["flag"] = by_ch["variance_pct"].abs() > threshold / 100
st.dataframe(by_ch, hide_index=True, column_config={
    "channel": "Channel", "budget_eur": st.column_config.NumberColumn("Budget (EUR)", format="localized"),
    "actual_eur": st.column_config.NumberColumn("Actual (EUR)", format="localized"),
    "variance_eur": st.column_config.NumberColumn("Variance (EUR)", format="localized"),
    "variance_pct": st.column_config.NumberColumn("Variance %", format="percent"),
    "flag": st.column_config.CheckboxColumn(f"Over {threshold}%")})
st.caption("Positive variance = overspend. Paid Social is over budget because of May to July "
           "(about 70,000 over in those three months). Influencer is about 32% under budget: monthly "
           "campaign spend is far below plan, and the two annual contracts add only 12,000 a month.")

# ---------------------------------------------------------------- 3. accruals and prepaids
st.subheader("Accruals and prepaids at month end")
acc = run(con, ACCRUALS_PREPAIDS)
acc["month_end"] = acc["month_end"].dt.strftime("%Y-%m-%d")
acc = acc.rename(columns={"month_end": "Month end",
                          "accrual_eur": "Accrual (EUR)",
                          "prepaid_eur": "Prepaid (EUR)"})
st.line_chart(acc, x="Month end", y=["Accrual (EUR)", "Prepaid (EUR)"],
              color=["#e67e22", "#2e86de"])
st.dataframe(acc, hide_index=True, column_config={"Accrual (EUR)": EUR, "Prepaid (EUR)": EUR})
st.caption("Accrual = service used, invoice not received yet. Invoices arrive 5 to 25 days after "
           "month end, so each month's own spend is accrued at its month end. "
           "Prepaid = invoice received, service not used yet: two annual influencer contracts "
           "(144,000 paid in January), released 12,000 a month.")

# ---------------------------------------------------------------- 4. data checks
st.subheader("Data checks")
cc, dup, late = run(con, CHECK_COST_CENTRE), run(con, CHECK_DUPLICATES), run(con, CHECK_OVERDUE)
k1, k2, k3 = st.columns(3)
k1.metric("Wrong cost centre", len(cc), help="Booked to a cost centre the channel should not use")
k2.metric("Duplicate invoices", len(dup), help="Same vendor and invoice number entered twice")
k3.metric("Invoices overdue (60+ days)", len(late), help="Service ended, still no invoice. Chase the vendor.")

st.markdown("**Booked to the wrong cost centre**")
st.dataframe(cc, hide_index=True, column_config={"amount_eur": EUR})
st.markdown("**Entered twice**")
st.dataframe(dup, hide_index=True, column_config={"total_eur": EUR})
st.markdown("**Service finished more than 60 days ago, still no invoice**")
st.dataframe(late, hide_index=True, column_config={"amount_eur": EUR})

st.caption("Simplifications: costs split evenly by month (no daily proration), no VAT, no FX. "
           "All SQL is in tracker/logic.py.")
