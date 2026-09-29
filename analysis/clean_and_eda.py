"""
Mamaearth Returns & Growth Intelligence Pipeline
Part 2: Python/Pandas Data Wrangling & EDA

Runs directly against data/orders.csv, data/customers.csv, data/products.csv
(the same raw source files Part 1 loads into SQLite) -- this is an
independent pandas pipeline, not a read of the SQL database, so it can be run
before or after Part 1.

Run: python analysis/clean_and_eda.py
Writes narrator/findings.json at the end (Part 3, Task 1).
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NARRATOR = ROOT / "narrator"


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
# Task 1: Load and inspect
# ---------------------------------------------------------------------------
section("TASK 1: Load and inspect")

orders = pd.read_csv(DATA / "orders.csv")
customers = pd.read_csv(DATA / "customers.csv")
products = pd.read_csv(DATA / "products.csv")

print("orders.shape  :", orders.shape)
print("customers.shape:", customers.shape)
print("products.shape :", products.shape)
assert orders.shape == (180, 9), "orders.csv should load as 180 rows x 9 columns before cleaning"


# ---------------------------------------------------------------------------
# Task 2: Standardize payment_method casing
# ---------------------------------------------------------------------------
section("TASK 2: Standardize payment_method casing")

raw_values = sorted(orders["payment_method"].unique().tolist())
print(f"Raw distinct payment_method values ({len(raw_values)}):", raw_values)
assert len(raw_values) == 7

orders["payment_method"] = orders["payment_method"].str.strip().str.upper()

clean_values = sorted(orders["payment_method"].unique().tolist())
print(f"Cleaned distinct payment_method values ({len(clean_values)}):", clean_values)
print("Counts after cleaning:")
print(orders["payment_method"].value_counts())
assert len(clean_values) == 3


# ---------------------------------------------------------------------------
# Task 3: Remove duplicate orders
# ---------------------------------------------------------------------------
section("TASK 3: Remove duplicate orders")

natural_key = [
    "customer_id", "product_id", "order_date", "quantity",
    "discount_pct", "payment_method", "rating", "returned",
]
dup_mask = orders.duplicated(subset=natural_key, keep="first")
dropped_ids = orders.loc[dup_mask, "order_id"].tolist()

print(f"Duplicate rows flagged: {dup_mask.sum()}")
print("Dropped order_id values:", dropped_ids)

orders_clean = orders.loc[~dup_mask].reset_index(drop=True).copy()
print("orders_clean.shape:", orders_clean.shape)

assert dup_mask.sum() == 5
assert dropped_ids == ["O0176", "O0177", "O0178", "O0179", "O0180"]
assert orders_clean.shape == (175, 9)


# ---------------------------------------------------------------------------
# Task 4: Impute missing values
# ---------------------------------------------------------------------------
section("TASK 4: Impute missing values")

discount_missing = orders_clean["discount_pct"].isnull().sum()
rating_missing = orders_clean["rating"].isnull().sum()
print(f"discount_pct missing (pre-impute, deduplicated frame): {discount_missing}")
print(f"rating missing (pre-impute, deduplicated frame): {rating_missing}")

median_rating = orders_clean["rating"].median()
print(f"Median non-null rating (deduplicated frame): {median_rating}")

orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(median_rating)

null_check = orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict()
print("Null counts after imputing:", null_check)

assert discount_missing == 12
assert rating_missing == 15
assert median_rating == 3.0
assert null_check == {"discount_pct": 0, "rating": 0}


# ---------------------------------------------------------------------------
# Task 5: Merge and reconcile against Part 1
# ---------------------------------------------------------------------------
section("TASK 5: Merge and reconcile against Part 1")

merged = orders_clean.merge(products, on="product_id").merge(customers, on="customer_id")
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)

cleaned_total_revenue = round(merged["order_value"].sum(), 2)
raw_total_revenue = 99860.20  # Part 1, Report (a), run against the raw 180-row load
delta = round(raw_total_revenue - cleaned_total_revenue, 2)

print(f"Total order_value across {len(merged)} cleaned rows: {cleaned_total_revenue}")
print(f"Part 1 raw total_revenue (Report a, 180 rows): {raw_total_revenue}")
print(f"Delta (raw - cleaned): {delta}")

# Independent check: sum order_value of just the 5 dropped rows.
dropped_rows = orders.loc[dup_mask].merge(products, on="product_id")
dropped_rows["order_value"] = dropped_rows["quantity"] * dropped_rows["price"] * (
    1 - dropped_rows["discount_pct"].fillna(0) / 100
)
dropped_total = round(dropped_rows["order_value"].sum(), 2)
print(f"Independent check -- combined order_value of the 5 dropped duplicate rows: {dropped_total}")

print(
    "\nReconciliation note: the cleaned total revenue (Rs.{:.2f}) is Rs.{:.2f} lower than "
    "Part 1's raw total (Rs.{:.2f}), and that entire delta is attributable to the 5 duplicate "
    "orders removed in Task 3 (O0176-O0180), whose combined order_value sums to Rs.{:.2f} -- "
    "matching the delta to the cent. It is not attributable to the discount_pct/rating "
    "imputation in Task 4: filling discount_pct with 0 only affects rows that already had no "
    "discount applied (order_value math is unchanged for a NULL treated as 0%, same as the "
    "COALESCE in Part 1), and filling rating with the median never touches order_value at all, "
    "since rating does not appear in the revenue formula.".format(
        cleaned_total_revenue, delta, raw_total_revenue, dropped_total
    )
)

assert cleaned_total_revenue == 97358.30
assert delta == 2501.90
assert dropped_total == 2501.90


# ---------------------------------------------------------------------------
# Task 6: IQR outlier detection on quantity
# ---------------------------------------------------------------------------
section("TASK 6: IQR outlier detection on quantity")

Q1 = merged["quantity"].quantile(0.25)
Q3 = merged["quantity"].quantile(0.75)
IQR = Q3 - Q1
lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

print(f"Q1={Q1}, Q3={Q3}, IQR={IQR}, lower={lower_bound}, upper={upper_bound}")

merged["is_outlier"] = (merged["quantity"] < lower_bound) | (merged["quantity"] > upper_bound)
outliers = merged.loc[merged["is_outlier"], ["order_id", "quantity", "order_date"]]
print(f"Outlier rows ({merged['is_outlier'].sum()}):")
print(outliers.to_string(index=False))

assert (Q1, Q3, IQR, lower_bound, upper_bound) == (1.0, 2.0, 1.0, -0.5, 3.5)
assert set(outliers["order_id"]) == {"O0011", "O0098"}
# Outliers are flagged, not dropped -- Task 9/10 use the is_outlier column.


# ---------------------------------------------------------------------------
# Task 7: Hypothesis - does COD have a higher return rate?
# ---------------------------------------------------------------------------
section("TASK 7: Hypothesis - COD has a higher return rate than Card/UPI")

print("Hypothesis: Cash-on-Delivery (COD) orders are returned more often than "
      "Card or UPI orders, because COD removes the pre-purchase commitment a "
      "paid-upfront order carries.")

payment_stats = orders_clean.groupby("payment_method")["returned"].agg(["count", "mean"])
payment_stats["return_rate_pct"] = (payment_stats["mean"] * 100).round(1)
print(payment_stats)

rates = payment_stats["return_rate_pct"].to_dict()
print(f"\nReturn rates -> CARD: {rates['CARD']}%, COD: {rates['COD']}%, UPI: {rates['UPI']}%")
print("Verdict: Confirmed -- COD's return rate is roughly 3x Card's and ~2.4x UPI's.")

assert rates == {"CARD": 14.7, "COD": 44.4, "UPI": 18.9}


# ---------------------------------------------------------------------------
# Task 8: Multi-level segmentation
# ---------------------------------------------------------------------------
section("TASK 8: Multi-level segmentation (payment_method x city_tier)")

segment_stats = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
segment_stats["return_rate_pct"] = (segment_stats["mean"] * 100).round(1)
print(segment_stats)

cod_tier1 = segment_stats.loc[("COD", 1), "return_rate_pct"]
cod_tier2 = segment_stats.loc[("COD", 2), "return_rate_pct"]
cod_tier1_n = int(segment_stats.loc[("COD", 1), "count"])
cod_tier2_n = int(segment_stats.loc[("COD", 2), "count"])

highest_row = segment_stats["return_rate_pct"].idxmax()
highest_rate = segment_stats["return_rate_pct"].max()

print(
    f"\nHighest-risk segment: payment_method={highest_row[0]}, city_tier={highest_row[1]} "
    f"at {highest_rate}%."
)
print(
    f"COD is NOT uniform across tiers: Tier-1 COD is {cod_tier1_n} orders at {cod_tier1}%, "
    f"versus Tier-2 COD at {cod_tier2_n} orders at {cod_tier2}% -- the blended COD rate of "
    f"44.4% from Task 7 hides that the real problem is concentrated in Tier-2 cities."
)

assert highest_row == ("COD", 2)
assert highest_rate == 54.5
assert (cod_tier1_n, cod_tier1) == (32, 37.5)
assert (cod_tier2_n, cod_tier2) == (22, 54.5)


# ---------------------------------------------------------------------------
# Task 9: Correlation analysis
# ---------------------------------------------------------------------------
section("TASK 9: Correlation analysis")

corr = merged[["rating", "returned", "discount_pct", "quantity"]].corr()
print(corr.round(4))


def band(r):
    a = abs(r)
    if a < 0.20:
        return "negligible"
    if a < 0.40:
        return "weak"
    if a < 0.70:
        return "moderate"
    return "strong"


pairs = [
    ("rating", "returned"), ("rating", "discount_pct"), ("rating", "quantity"),
    ("returned", "discount_pct"), ("returned", "quantity"), ("discount_pct", "quantity"),
]
print("\nPairwise correlation-strength bands (0-0.19 negligible / 0.2-0.39 weak / "
      "0.4-0.69 moderate / 0.7-1.0 strong):")
for a, b in pairs:
    r = corr.loc[a, b]
    print(f"  {a} vs {b}: r={r:.4f} -> {band(r)}")
    assert band(r) == "negligible", f"expected all six pairs negligible, got {a}-{b}={r}"

discount_returned_r = corr.loc["discount_pct", "returned"]
print(
    f"\nHypothesis 'higher discounts reduce returns': discount_pct vs returned "
    f"correlation = {discount_returned_r:.2f} -> Busted (negligible, and the wrong sign "
    f"to support the hypothesis anyway)."
)
assert round(discount_returned_r, 2) == -0.09


# ---------------------------------------------------------------------------
# Task 10: Outlier-corrected time series
# ---------------------------------------------------------------------------
section("TASK 10: Outlier-corrected time series")

merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)

monthly_with_outliers = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_corrected = (
    merged.loc[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
)

print("Monthly total order_value INCLUDING the 2 Task-6 outlier orders:")
print(monthly_with_outliers)
print("\nMonthly total order_value EXCLUDING the 2 Task-6 outlier orders (outlier-corrected):")
print(monthly_corrected)

apparent_peak_month = monthly_with_outliers.idxmax()
apparent_peak_value = monthly_with_outliers.max()
true_peak_month = monthly_corrected.idxmax()
true_peak_value = monthly_corrected.max()
jan_corrected = monthly_corrected["2026-01"]

print(
    f"\nJanuary ({apparent_peak_month}) appears highest at Rs.{apparent_peak_value} only because "
    f"the two Task-6 bulk-quantity outlier orders both landed in January -- O0011 (qty 25) on "
    f"2026-01-28 and O0098 (qty 30) on 2026-01-10. Strip those two orders out and January drops "
    f"to Rs.{jan_corrected}, while {true_peak_month} becomes the genuine peak month at "
    f"Rs.{true_peak_value}. This is exactly why Task 6 (outlier detection) had to run before "
    f"Task 10, not after: doing the time series first would have reported the wrong peak month."
)

assert apparent_peak_month == "2026-01" and apparent_peak_value == 29582.10
assert true_peak_month == "2026-03" and true_peak_value == 20318.90
assert jan_corrected == 11637.10


# ---------------------------------------------------------------------------
# Part 3, Task 1: export verified findings for the GenAI narrator layer
# ---------------------------------------------------------------------------
section("Exporting narrator/findings.json (Part 3, Task 1)")

findings = {
    "cleaned_total_revenue_inr": cleaned_total_revenue,
    "raw_total_revenue_inr": raw_total_revenue,
    "duplicate_reconciliation_delta_inr": delta,
    "return_rate_by_payment": {
        "COD": rates["COD"],
        "CARD": rates["CARD"],
        "UPI": rates["UPI"],
    },
    "highest_risk_segment": {
        "payment_method": highest_row[0],
        "city_tier": int(highest_row[1]),
        "return_rate_pct": float(highest_rate),
    },
    "true_peak_month": {
        "month": true_peak_month,
        "revenue_inr": float(true_peak_value),
    },
    "outlier_inflated_month": {
        "month": apparent_peak_month,
        "apparent_revenue_inr": float(apparent_peak_value),
        "corrected_revenue_inr": float(jan_corrected),
    },
}

NARRATOR.mkdir(exist_ok=True)
with open(NARRATOR / "findings.json", "w", encoding="utf-8") as f:
    json.dump(findings, f, indent=2)

print(json.dumps(findings, indent=2))
print(f"\nWrote {NARRATOR / 'findings.json'}")

print("\nAll Part 2 assertions passed -- every printed number matches the brief exactly.")
