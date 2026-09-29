"""
Mamaearth Returns & Growth Intelligence Pipeline
Part 2, Task 11: Visualizations

Re-derives the cleaned data from the raw CSVs (same logic as clean_and_eda.py)
so this script can be run on its own and always regenerates identical PNGs
from the raw source files -- no manual editing of intermediate output.

Run: python analysis/visualize.py   (after analysis/clean_and_eda.py)
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VIZ = ROOT / "visualizations"
VIZ.mkdir(exist_ok=True)

orders = pd.read_csv(DATA / "orders.csv")
customers = pd.read_csv(DATA / "customers.csv")
products = pd.read_csv(DATA / "products.csv")

orders["payment_method"] = orders["payment_method"].str.strip().str.upper()

natural_key = [
    "customer_id", "product_id", "order_date", "quantity",
    "discount_pct", "payment_method", "rating", "returned",
]
orders_clean = orders.loc[~orders.duplicated(subset=natural_key, keep="first")].reset_index(drop=True).copy()

median_rating = orders_clean["rating"].median()
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(median_rating)

merged = orders_clean.merge(products, on="product_id").merge(customers, on="customer_id")
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)

Q1 = merged["quantity"].quantile(0.25)
Q3 = merged["quantity"].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR
merged["is_outlier"] = (merged["quantity"] < lower_bound) | (merged["quantity"] > upper_bound)

merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)

# ---------------------------------------------------------------------------
# Chart 1: return rate by (cleaned) payment_method, descending, labeled bars.
# ---------------------------------------------------------------------------
payment_stats = orders_clean.groupby("payment_method")["returned"].mean().mul(100).round(1)
payment_stats = payment_stats.sort_values(ascending=False)

card_rate = payment_stats["CARD"]
cod_rate = payment_stats["COD"]
multiple = round(cod_rate / card_rate, 1)

fig, ax = plt.subplots(figsize=(7, 5))
colors = ["#d62728" if m == "COD" else "#1f77b4" for m in payment_stats.index]
bars = ax.bar(payment_stats.index, payment_stats.values, color=colors)
for bar, val in zip(bars, payment_stats.values):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.8, f"{val}%",
            ha="center", va="bottom", fontweight="bold")

ax.set_ylabel("Return rate (%)")
ax.set_xlabel("Payment method")
ax.set_title(f"COD Returns at {cod_rate}% — {multiple}x Card")
ax.set_ylim(0, max(payment_stats.values) * 1.2)
fig.tight_layout()
fig.savefig(VIZ / "return_rate_by_payment.png", dpi=150)
plt.close(fig)
print(f"Wrote {VIZ / 'return_rate_by_payment.png'}")

# ---------------------------------------------------------------------------
# Chart 2: outlier-corrected monthly revenue trend, line chart.
# ---------------------------------------------------------------------------
monthly_corrected = merged.loc[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
peak_month = monthly_corrected.idxmax()
peak_value = monthly_corrected.max()

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(monthly_corrected.index, monthly_corrected.values, marker="o", color="#2ca02c", linewidth=2)
peak_idx = list(monthly_corrected.index).index(peak_month)
ax.scatter([peak_month], [peak_value], color="#d62728", zorder=5, s=80)
ax.annotate(f"Peak: Rs.{peak_value:,.0f}", xy=(peak_month, peak_value),
            xytext=(0, 12), textcoords="offset points", ha="center", fontweight="bold")

ax.set_xlabel("Month")
ax.set_ylabel("Revenue (INR)")
ax.set_title(f"Outlier-Corrected Monthly Revenue — {peak_month} Is the True Peak")
ax.set_ylim(0, peak_value * 1.18)
fig.tight_layout()
fig.savefig(VIZ / "monthly_revenue_trend.png", dpi=150)
plt.close(fig)
print(f"Wrote {VIZ / 'monthly_revenue_trend.png'}")
