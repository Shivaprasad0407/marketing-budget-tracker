"""Generate the SYNTHETIC dataset for the Marketing Budget Tracker.

Every number here is invented. Nothing comes from any real company.
Run from the repo root:  python data/generate_data.py

Outputs three CSV files in data/:
  budget.csv       monthly budget per market and channel, Jan to Dec 2026
  spend.csv        cost lines (orders and invoices) with service periods
  channel_map.csv  which cost centre each channel should be booked to

A few problems are planted on purpose so the data checks have something
to find: misallocated cost centres, a duplicate invoice, invoices that
are overdue, and an annual contract paid up front (a prepaid expense).
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
OUT = Path(__file__).resolve().parent
YEAR = 2026
AS_OF = date(2026, 9, 30)

MARKETS = ["DE", "NL", "IT", "FR"]
MARKET_WEIGHT = {"DE": 0.40, "NL": 0.20, "IT": 0.22, "FR": 0.18}

# channel: (cost centre, annual budget for all markets in EUR, typical vendors)
CHANNELS = {
    "Paid Search": ("CC-4110 Performance", 1_800_000, ["SearchAds Co", "QueryMedia"]),
    "Paid Social": ("CC-4110 Performance", 1_400_000, ["SocialReach", "FeedAds"]),
    "Affiliate": ("CC-4120 Partnerships", 600_000, ["AffiliNet Partners", "CashbackHub"]),
    "Influencer": ("CC-4120 Partnerships", 480_000, ["CreatorLab", "Studio Nord"]),
    "CRM and Email": ("CC-4130 CRM", 300_000, ["MailFlow", "PushPilot"]),
    "Brand and OOH": ("CC-4200 Brand", 900_000, ["CityPoster", "BrandWorks Agency"]),
}

# Seasonality index per month (sums to 12). Home and living peaks in Q4.
SEASON = [0.85, 0.80, 0.95, 0.95, 0.90, 0.80, 0.75, 0.80, 1.00, 1.15, 1.30, 1.55]


def month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def month_end(y: int, m: int) -> date:
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return nxt - timedelta(days=1)


def build_budget() -> list[dict]:
    rows = []
    for ch, (_cc, annual, _v) in CHANNELS.items():
        for mk in MARKETS:
            for m in range(1, 13):
                amt = annual * MARKET_WEIGHT[mk] * SEASON[m - 1] / 12
                rows.append({"month": month_start(YEAR, m).isoformat(), "market": mk,
                             "channel": ch, "budget_eur": round(amt, 2)})
    return rows


def build_spend(rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    inv_counter = 10_000

    def add(vendor, channel, market, cc, s, e, amount, inv_date, invoice_no=None):
        nonlocal inv_counter
        if invoice_no is None and inv_date is not None:
            inv_counter += 1
            invoice_no = f"INV-{inv_counter}"
        rows.append({
            "line_id": f"L{len(rows) + 1:04d}",
            "vendor": vendor, "invoice_no": invoice_no or "",
            "channel": channel, "market": market, "cost_center_booked": cc,
            "service_start": s.isoformat(), "service_end": e.isoformat(),
            "amount_eur": round(amount, 2),
            "invoice_date": inv_date.isoformat() if inv_date else "",
        })

    # Regular monthly spend, Jan to Sep (closed months).
    for ch, (cc, annual, vendors) in CHANNELS.items():
        for mk in MARKETS:
            for m in range(1, 10):
                planned = annual * MARKET_WEIGHT[mk] * SEASON[m - 1] / 12
                # Influencer runs mostly on the annual contract below.
                if ch == "Influencer":
                    planned *= 0.35
                drift = rng.uniform(0.82, 1.12)
                if ch == "Paid Social" and m in (5, 6, 7):
                    drift = rng.uniform(1.18, 1.32)  # summer overspend to find
                amt = planned * drift
                s, e = month_start(YEAR, m), month_end(YEAR, m)
                # Invoices usually arrive 5 to 25 days after month end.
                inv = e + timedelta(days=rng.randint(5, 25))
                # Recent months: some invoices are not in yet (accrual needed).
                if m == 9 and rng.random() < 0.55:
                    inv = None
                if m == 8 and rng.random() < 0.10:
                    inv = None
                if inv is not None and inv > AS_OF:
                    inv = None
                add(rng.choice(vendors), ch, mk, cc, s, e, amt, inv)

    # Annual influencer framework contract, invoiced and paid up front in January.
    # In the P&L it must be spread over 12 months (prepaid expense).
    for mk, amt in (("DE", 96_000), ("IT", 48_000)):
        add("CreatorLab", "Influencer", mk, "CC-4120 Partnerships",
            date(YEAR, 1, 1), date(YEAR, 12, 31), amt, date(YEAR, 1, 12))

    # Planted issue 1: misallocated cost centres (booked to Brand instead of Performance).
    for idx in rng.sample(range(len(rows)), 60):
        r = rows[idx]
        if r["channel"] in ("Paid Search", "Paid Social") and r["invoice_no"]:
            r["cost_center_booked"] = "CC-4200 Brand"
            if sum(x["cost_center_booked"] == "CC-4200 Brand" and x["channel"] in ("Paid Search", "Paid Social") for x in rows) >= 3:
                break

    # Planted issue 2: one invoice entered twice.
    dup_src = next(r for r in rows if r["channel"] == "Affiliate" and r["market"] == "NL"
                   and r["service_start"] == f"{YEAR}-06-01")
    dup = dict(dup_src)
    dup["line_id"] = f"L{len(rows) + 1:04d}"
    rows.append(dup)

    # Planted issue 3: services delivered long ago, still no invoice.
    for r in rows:
        if r["channel"] == "Brand and OOH" and r["market"] == "FR" and r["service_start"] in (f"{YEAR}-05-01", f"{YEAR}-06-01"):
            r["invoice_no"], r["invoice_date"] = "", ""

    return rows


def main() -> None:
    rng = random.Random(SEED)
    budget = build_budget()
    spend = build_spend(rng)
    cmap = [{"channel": ch, "expected_cost_center": cc} for ch, (cc, _a, _v) in CHANNELS.items()]
    for name, rows in (("budget.csv", budget), ("spend.csv", spend), ("channel_map.csv", cmap)):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
