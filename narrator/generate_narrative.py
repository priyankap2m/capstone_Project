"""
Mamaearth Returns & Growth Intelligence Pipeline
Part 3: GenAI-Powered Insight Narrator

Turns narrator/findings.json (written by analysis/clean_and_eda.py, Part 3
Task 1) into a Situation-Complication-Resolution business narrative.

Two paths, same return shape:
  - generate_scr_narrative(findings)          -> calls the Gemini API
  - generate_scr_narrative_offline(findings)  -> deterministic template, no
                                                  network, no API key

Run: python narrator/generate_narrative.py
  - With GEMINI_API_KEY set in the environment: calls Gemini and falls back
    to the offline path automatically if the call errors.
  - With no key set at all: goes straight to the offline path. Zero network
    access and zero API spend are required for this script to run and pass
    the numeric accuracy checklist.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINDINGS_PATH = ROOT / "findings.json"
SAMPLE_OUTPUT_PATH = ROOT / "sample_output.txt"

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and "
    "finance heads. Write a business narrative structured into exactly three "
    "labeled sections, in this order: 'Situation', 'Complication', "
    "'Resolution'. Every number you state must come from the findings "
    "supplied in the user message and must appear with the exact same value "
    "given there -- never invent, round differently, or estimate a "
    "statistic that was not supplied. Keep the tone plain and actionable, "
    "suitable for a non-technical operations or finance audience, and keep "
    "the whole narrative to roughly 250 words."
)


def _month_name(yyyy_mm: str) -> str:
    """'2026-03' -> 'March 2026'. Findings store month as YYYY-MM; the
    narrative needs the human-readable month name too, since the numeric
    accuracy checklist requires the literal month name alongside the figure."""
    return datetime.strptime(yyyy_mm, "%Y-%m").strftime("%B %Y")


def _build_user_prompt(findings: dict) -> str:
    """Builds the Gemini `contents` prompt by interpolating findings -- never
    hardcoding numbers into the template, so a different findings.json
    produces a different narrative without touching this function."""
    rr = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    return (
        "Write the SCR business narrative from these verified findings "
        "(all figures are in INR unless stated as a percentage):\n\n"
        f"- Cleaned total revenue after removing duplicate orders: "
        f"Rs.{findings['cleaned_total_revenue_inr']:,}\n"
        f"- Raw total revenue before cleaning: Rs.{findings['raw_total_revenue_inr']:,}\n"
        f"- Revenue lost to duplicate double-submitted orders (the "
        f"reconciliation delta between raw and cleaned revenue): "
        f"Rs.{findings['duplicate_reconciliation_delta_inr']:,}\n"
        f"- Return rate by payment method: COD {rr['COD']}%, CARD {rr['CARD']}%, "
        f"UPI {rr['UPI']}%\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in "
        f"city_tier {seg['city_tier']} cities, with a {seg['return_rate_pct']}% "
        f"return rate\n"
        f"- True peak revenue month once bulk-order outliers are removed: "
        f"{_month_name(peak['month'])} ({peak['month']}) at Rs.{peak['revenue_inr']:,}\n"
        f"- Outlier-inflated month: {_month_name(inflated['month'])} "
        f"({inflated['month']}) appeared to lead at "
        f"Rs.{inflated['apparent_revenue_inr']:,} but corrects down to "
        f"Rs.{inflated['corrected_revenue_inr']:,} once the two bulk-quantity "
        f"outlier orders are excluded\n\n"
        "Situation: state the headline revenue picture. Complication: name "
        "the two problems (COD's return-rate concentration in Tier-2 cities, "
        "and the duplicate-order revenue leak). Resolution: recommend "
        "concrete next steps ops and finance can act on this quarter. "
        f"Always name the true peak month by its month name ({_month_name(peak['month'])}), "
        "not just its numeric YYYY-MM form."
    )


def generate_scr_narrative(findings: dict) -> dict:
    """Calls the Gemini API to produce the SCR narrative. Returns a
    structured dict in both the success and failure branch -- the caller
    must never receive a raw exception."""
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in the environment")

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=_build_user_prompt(findings),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                # Deterministic on purpose: this is a factual business report
                # that must reproduce the same verified numbers every time,
                # not a creative-writing task where sampling variety helps.
                temperature=0.0,
                max_output_tokens=500,
                http_options=types.HttpOptions(timeout=30_000),  # ms; >= the taught 10s minimum
            ),
        )

        return {
            "status": "success",
            "narrative": response.text,
            "tokens": getattr(response.usage_metadata, "total_token_count", None),
        }
    except Exception as err:  # noqa: BLE001 - deliberately broad: never leak a raw exception
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative_offline(findings: dict) -> dict:
    """Fully deterministic, keyless, offline fallback. Same return-dict
    shape as generate_scr_narrative, so callers never need to branch on
    which path produced the narrative."""
    rr = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]
    peak_name = _month_name(peak["month"])
    inflated_name = _month_name(inflated["month"])

    narrative = f"""Situation
Mamaearth closed the period with Rs.{findings['cleaned_total_revenue_inr']:,} in verified revenue after data cleaning, down from a raw, uncleaned figure of Rs.{findings['raw_total_revenue_inr']:,}. Payment-method mix is healthy on the surface: CARD ({rr['CARD']}%) and UPI ({rr['UPI']}%) both show manageable return rates, while {peak_name} ({peak['month']}) is the genuine best month of the period at Rs.{peak['revenue_inr']:,} once bulk-order noise is removed.

Complication
Two issues are quietly eating into that picture. First, COD orders return at {rr['COD']}%, and that risk is not spread evenly: {seg['payment_method']} orders from city_tier {seg['city_tier']} cities alone return at {seg['return_rate_pct']}%, well above the blended COD average -- the real exposure is concentrated, not uniform. Second, a double-submit bug generated duplicate orders that inflated the raw revenue figure by Rs.{findings['duplicate_reconciliation_delta_inr']:,} before cleaning caught them. A third distortion is timing: {inflated_name} ({inflated['month']}) looked like the top month at an apparent Rs.{inflated['apparent_revenue_inr']:,}, but that figure collapses to Rs.{inflated['corrected_revenue_inr']:,} once two outsized bulk orders are excluded -- the true peak is {peak_name}, not {inflated_name}.

Resolution
Ops should prioritize a COD review specifically for city_tier {seg['city_tier']} markets -- deposit-on-delivery, address verification, or COD caps for repeat-return customers in those cities -- rather than a blanket COD policy change, since city_tier 1 COD risk is materially lower. Engineering should patch the checkout double-submit bug that produced the Rs.{findings['duplicate_reconciliation_delta_inr']:,} duplicate-order leak, and finance should treat {peak_name}'s Rs.{peak['revenue_inr']:,} as the real demand baseline for forecasting, not the outlier-inflated {inflated_name} number, to avoid over-committing inventory or marketing spend against a phantom peak."""

    return {"status": "success", "narrative": narrative, "tokens": None}


def check_numeric_accuracy(narrative: str, findings: dict) -> bool:
    """Prints a pass/fail line for each of the five required figures and
    returns True only if all five are present (substring match, after
    normalizing thousands-separator commas so '97,358.30' and '97358.3'
    both count)."""

    def norm(s: str) -> str:
        return re.sub(r",", "", s)

    normalized_narrative = norm(narrative)

    checks = [
        ("cleaned total revenue (97358.3)", "97358.3"),
        ("COD return rate (44.4)", "44.4"),
        ("COD + Tier-2 highest-risk segment (54.5)", "54.5"),
        ("duplicate reconciliation delta (2501.9)", "2501.9"),
        ("true peak revenue (20318.9)", "20318.9"),
    ]

    all_pass = True
    for label, needle in checks:
        found = needle in normalized_narrative
        print(f"  [{'PASS' if found else 'FAIL'}] {label}")
        all_pass = all_pass and found

    peak_month_word = _month_name(findings["true_peak_month"]["month"]).split()[0]
    peak_month_found = peak_month_word in narrative
    print(f"  [{'PASS' if peak_month_found else 'FAIL'}] true peak month named ('{peak_month_word}')")
    all_pass = all_pass and peak_month_found

    return all_pass


def main():
    with open(FINDINGS_PATH, encoding="utf-8") as f:
        findings = json.load(f)

    result = generate_scr_narrative(findings)
    path_used = "online (Gemini)"

    if result["status"] == "error":
        print(f"Gemini call unavailable ({result['message']}) -- falling back to offline narrator.")
        result = generate_scr_narrative_offline(findings)
        path_used = "offline (keyless fallback)"

    print(f"\n=== SCR Narrative ({path_used}) ===\n")
    print(result["narrative"])

    print(f"\n=== Numeric accuracy checklist ({path_used}) ===")
    passed = check_numeric_accuracy(result["narrative"], findings)
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")

    with open(SAMPLE_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"Path used: {path_used}\n\n{result['narrative']}\n")
    print(f"\nWrote {SAMPLE_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
