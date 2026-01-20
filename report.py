import argparse
import numpy as np
import pandas as pd

SOURCE_TZ = "America/New_York"   # EST/ET -> UTC conversion (handles DST)
OUT_DATE_FMT = "%Y/%m/%d"        # required output format


def parse_est_to_utc(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Parses a datetime column in Eastern Time (e.g. '12/31/18 19:00') and converts to UTC.
    Adds:
      - dt_utc  : UTC datetime
      - date_utc: UTC day bucket
      - hour_utc: UTC hour bucket (used only if --hourly)
    """
    dt = pd.to_datetime(df[col], format="%m/%d/%y %H:%M", errors="raise")
    dt = dt.dt.tz_localize(SOURCE_TZ, ambiguous="infer", nonexistent="shift_forward").dt.tz_convert("UTC")

    out = df.copy()
    out["dt_utc"] = dt
    out["date_utc"] = out["dt_utc"].dt.floor("D")  # UTC day bucket
    out["hour_utc"] = out["dt_utc"].dt.floor("h")  # UTC hour bucket
    return out


def safe_div(a, b):
    """
    Safe element-wise division:
    - returns NaN where denominator is 0
    - avoids numpy runtime warnings
    """
    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    out = np.full_like(a, np.nan, dtype="float64")
    mask = b != 0
    out[mask] = a[mask] / b[mask]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cost", default="cost_1.csv")
    p.add_argument("--revenue", default="revenue_1.csv")
    p.add_argument("--date-from", dest="date_from", required=True, help="YYYY-MM-DD (UTC day)")
    p.add_argument("--date-to", dest="date_to", required=True, help="YYYY-MM-DD (UTC day)")
    p.add_argument("--out", default="report.csv")
    p.add_argument("--hourly", action="store_true", help="Add optional hourly columns")
    args = p.parse_args()

    # 1) Load CSVs
    cost = pd.read_csv(args.cost, dtype={"campaign_id": "string", "campaign_name": "string"})
    rev = pd.read_csv(args.revenue, dtype={"campaign_id": "string"})

    # 2) Numeric casting
    cost["clicks"] = pd.to_numeric(cost["clicks"], errors="coerce").fillna(0.0)
    cost["cost"] = pd.to_numeric(cost["cost"], errors="coerce").fillna(0.0)
    rev["revenue"] = pd.to_numeric(rev["revenue"], errors="coerce").fillna(0.0)

    # 3) EST -> UTC
    cost = parse_est_to_utc(cost, "data_date")
    rev = parse_est_to_utc(rev, "data_date")

    # 4) Filter by date_from/date_to (UTC days, inclusive)
    d_from = pd.Timestamp(args.date_from, tz="UTC").floor("D")
    d_to = pd.Timestamp(args.date_to, tz="UTC").floor("D")

    cost = cost[(cost["date_utc"] >= d_from) & (cost["date_utc"] <= d_to)]
    rev = rev[(rev["date_utc"] >= d_from) & (rev["date_utc"] <= d_to)]

    # 5) Aggregate daily per campaign
    cost_daily = (
        cost.groupby(["date_utc", "campaign_id"], as_index=False)
        .agg(
            # Match SQL's MIN(campaign_name) and keep output deterministic regardless of input row order.
            campaign_name=("campaign_name", "min"),
            total_cost=("cost", "sum"),
            total_clicks=("clicks", "sum"),
        )
    )

    rev_daily = (
        rev.groupby(["date_utc", "campaign_id"], as_index=False)
        .agg(total_revenue=("revenue", "sum"))
    )

    # 6) Outer join
    report = pd.merge(cost_daily, rev_daily, on=["date_utc", "campaign_id"], how="outer")

    report["campaign_name"] = report["campaign_name"].fillna("")
    report["total_cost"] = report["total_cost"].fillna(0.0)
    report["total_clicks"] = report["total_clicks"].fillna(0.0)
    report["total_revenue"] = report["total_revenue"].fillna(0.0)

    # 7) Calculations
    report["total_profit"] = report["total_revenue"] - report["total_cost"]

    report["avg_cpc"] = safe_div(report["total_cost"], report["total_clicks"])

    uv = safe_div(report["total_revenue"], report["total_clicks"])
    cpc = safe_div(report["total_cost"], report["total_clicks"])
    report["total_roi"] = safe_div(uv, cpc)

    # 8) Optional hourly columns
    if args.hourly:
        cost_h = cost.groupby(["date_utc", "hour_utc", "campaign_id"], as_index=False).agg(cost=("cost", "sum"))
        rev_h = rev.groupby(["date_utc", "hour_utc", "campaign_id"], as_index=False).agg(revenue=("revenue", "sum"))

        h = pd.merge(cost_h, rev_h, on=["date_utc", "hour_utc", "campaign_id"], how="outer").fillna(0.0)
        h["profit"] = h["revenue"] - h["cost"]

        pos_hours = (
            h[h["profit"] > 0]
            .groupby(["date_utc", "campaign_id"])
            .size()
            .reset_index(name="positive_profit_hours")
        )

        avg_hourly_rev = (
            h.groupby(["date_utc", "campaign_id"], as_index=False)
            .agg(hourly_avg_revenue=("revenue", "mean"))
        )

        report = report.merge(pos_hours, on=["date_utc", "campaign_id"], how="left")
        report = report.merge(avg_hourly_rev, on=["date_utc", "campaign_id"], how="left")
        report["positive_profit_hours"] = report["positive_profit_hours"].fillna(0).astype(int)
        report["hourly_avg_revenue"] = report["hourly_avg_revenue"].fillna(0.0)

    # 9) Output columns/order
    report["date"] = report["date_utc"].dt.strftime(OUT_DATE_FMT)

    cols = [
        "date",
        "campaign_id",
        "campaign_name",
        "total_revenue",
        "total_cost",
        "total_profit",
        "total_clicks",
        "total_roi",
        "avg_cpc",
    ]
    if args.hourly:
        cols += ["hourly_avg_revenue", "positive_profit_hours"]

    report = report[cols].sort_values(["date", "campaign_id"]).reset_index(drop=True)

    report.to_csv(args.out, index=False)
    # Avoid non-ASCII output to keep Windows consoles (non-UTF8 code pages) happy.
    print(f"Wrote {args.out} ({len(report)} rows)")


if __name__ == "__main__":
    main()
