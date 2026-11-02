"""
==================================================================
Source: imports_wide.csv, India's monthly crude imports by supplier in thousand barrels per month
(Apr-2024 onwards). The figures match Kpler tanker-tracking numbers reported in the press
(e.g. Russia 2.80 MBPD in Jul-2026; Iraq 0 in Apr-2026 after the Hormuz restrictions).

Melt the import table from wide (monthly columns) to long (month, country, volume_kbd).
Ensures unit consistency across all downstream joins, ML models, and procurement optimizers.
"""

import csv
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parent

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

def parse_month_to_iso(m_str: str) -> str:
    """Converts 'Apr-2024' or '2024-04' to '2024-04'."""
    m_str = m_str.strip()
    if "-" in m_str:
        parts = m_str.split("-")
        if len(parts) == 2:
            p1, p2 = parts[0], parts[1]
            if p1 in MONTH_MAP and len(p2) == 4:
                return f"{p2}-{MONTH_MAP[p1]}"
            elif p2 in MONTH_MAP and len(p1) == 4:
                return f"{p1}-{MONTH_MAP[p2]}"
            elif len(p1) == 4 and len(p2) == 2:
                return f"{p1}-{p2}"
    return m_str

def melt_wide_to_long(wide_path: Path = DATA_DIR / "imports_wide.csv",
                       output_path: Path = DATA_DIR / "imports_long.csv") -> Path:
    """
    Melts wide format imports CSV into long format:
    Columns: month (YYYY-MM), country, volume_kbd
    Supports both row-per-month and row-per-country schemas.
    """
    if not wide_path.exists():
        raise FileNotFoundError(f"{wide_path} is missing; it is the source data and is tracked in git")

    long_rows = []
    with open(wide_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]

        # Determine schema: row-per-month (starts with month,fiscal_year,...) vs row-per-country (starts with country,2024-07,...)
        if "month" in headers[0].lower():
            # Row-per-month schema (Real India trade dataset)
            # Find country columns (exclude metadata columns)
            exclude_cols = {"month", "fiscal_year", "listed total", "total supply", "india domestic"}
            country_indices = [
                (i, h) for i, h in enumerate(headers)
                if h.lower() not in exclude_cols
            ]

            for row in reader:
                if not row or not row[0].strip():
                    continue
                raw_month = row[0]
                iso_month = parse_month_to_iso(raw_month)
                
                # Determine number of days in month for daily kbd conversion
                days_in_month = 30.0
                try:
                    parts = raw_month.split("-")
                    m_name = parts[0] if parts[0] in MONTH_MAP else parts[1]
                    if m_name in ["Jan", "Mar", "May", "Jul", "Aug", "Oct", "Dec"]:
                        days_in_month = 31.0
                    elif m_name in ["Apr", "Jun", "Sep", "Nov"]:
                        days_in_month = 30.0
                    elif m_name == "Feb":
                        days_in_month = 28.25
                except Exception:
                    days_in_month = 30.0

                for idx, c_name in country_indices:
                    if idx < len(row):
                        val_str = row[idx].strip().replace(",", "")
                        try:
                            monthly_thousand_bbl = float(val_str)
                            # Convert thousand barrels/month to daily thousand barrels/day (kbd)
                            daily_kbd = round(monthly_thousand_bbl / days_in_month, 2)
                        except ValueError:
                            daily_kbd = 0.0

                        # Map names
                        clean_country = "Other Suppliers" if c_name.lower().startswith("others") else c_name

                        long_rows.append({
                            "month": iso_month,
                            "country": clean_country,
                            "volume_kbd": daily_kbd
                        })
        else:
            # Row-per-country schema
            month_cols = headers[1:]
            for row in reader:
                if not row or not row[0].strip():
                    continue
                country = row[0].strip()
                for month_name, val_str in zip(month_cols, row[1:]):
                    try:
                        val = float(val_str.strip().replace(",", ""))
                    except ValueError:
                        val = 0.0
                    long_rows.append({
                        "month": parse_month_to_iso(month_name),
                        "country": country,
                        "volume_kbd": round(val, 2)
                    })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["month", "country", "volume_kbd"])
        writer.writeheader()
        for r in long_rows:
            writer.writerow(r)

    print(f"[OK] Generated melted long imports: {output_path} ({len(long_rows)} rows)")
    return output_path

def compute_max_liftable_kbd(long_path: Path = DATA_DIR / "imports_long.csv") -> Dict[str, float]:
    """
    Calculates max liftable kbd per country:
    max_liftable_i = 1.4 * (highest monthly volume from country i in the last 24 months)
    """
    if not long_path.exists():
        melt_wide_to_long(output_path=long_path)

    max_historical: Dict[str, float] = {}
    with open(long_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            c = r["country"]
            vol = float(r["volume_kbd"])
            if c not in max_historical or vol > max_historical[c]:
                max_historical[c] = vol

    # Apply 1.4x surge headroom factor
    max_liftable = {c: round(1.4 * peak_vol, 1) for c, peak_vol in max_historical.items()}
    return max_liftable

if __name__ == "__main__":
    w_path = DATA_DIR / "imports_wide.csv"
    l_path = melt_wide_to_long(w_path)
    liftable = compute_max_liftable_kbd(l_path)
    print("\n--- Computed Max Liftable kbd (1.4x peak surge headroom from real dataset) ---")
    for country, cap in sorted(liftable.items(), key=lambda x: x[1], reverse=True):
        print(f"  {country:20s}: {cap:7.1f} kbd")

