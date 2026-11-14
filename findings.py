"""Does n_active_loans = 0 hide two different populations?

risk_mart sets n_active_loans to 0 both for applicants whose bureau loans are
all closed and, through COALESCE, for applicants with no bureau record at all.
This script splits the 0 group by bureau history and compares the default
rates (mean TARGET) of the two groups.

Run after dbt build, from the project root: uv run python findings.py
"""
import math

import duckdb

from credit_risk.config import config

Z_95 = 1.959964  # two-sided 95% quantile of the standard normal
MIN_COUNT = 5  # defaults and non-defaults per group the normal approximation needs

# Applicants with n_active_loans = 0, split by what the bureau knows about them
ZERO_ACTIVE_GROUPS = """
    WITH bureau_history AS (
        SELECT SK_ID_CURR, BOOL_AND(CREDIT_ACTIVE = 'Closed') AS all_closed
        FROM bureau
        GROUP BY SK_ID_CURR
    )
    SELECT
        CASE
            WHEN m.n_loans = 0 THEN 'no bureau record'
            WHEN h.all_closed THEN 'all loans closed'
            ELSE 'sold or bad debt'  -- no active loan, but not every loan is closed
        END AS bureau_history,
        COUNT(*) AS customers,
        SUM(m.TARGET) AS defaults,
        ROUND(100 * AVG(m.TARGET), 2) AS default_rate_pct
    FROM risk_mart m
    LEFT JOIN bureau_history h USING (SK_ID_CURR)
    WHERE m.n_active_loans = 0
    GROUP BY bureau_history
    ORDER BY CASE bureau_history
        WHEN 'no bureau record' THEN 1 WHEN 'all loans closed' THEN 2 ELSE 3 END
"""


def print_segment_context(con):
    """Show what kri sees: one PD for the whole n_active_loans = 0 segment."""
    customers, rate, zero_customers, zero_rate = con.execute("""
        SELECT
            COUNT(*), AVG(TARGET),
            COUNT(*) FILTER (WHERE n_active_loans = 0),
            AVG(TARGET) FILTER (WHERE n_active_loans = 0)
        FROM risk_mart
    """).fetchall()[0]
    print(f"Portfolio default rate: {rate:.2%} ({customers:,} applicants)")
    if zero_customers:
        print(f"n_active_loans = 0 segment: {zero_rate:.2%} ({zero_customers:,} applicants), "
              "a single PD in kri")
    print()


def compare_rates(name_a, a, name_b, b):
    """Print the gap between two groups' default rates, given (customers, defaults) each."""
    (n_a, defaults_a), (n_b, defaults_b) = a, b
    rate_a, rate_b = defaults_a / n_a, defaults_b / n_b
    diff = rate_a - rate_b
    print(f"{name_a} vs {name_b}")
    print(f"  default rate    {rate_a:.2%} vs {rate_b:.2%}")
    if min(defaults_a, n_a - defaults_a, defaults_b, n_b - defaults_b) < MIN_COUNT:
        print(f"  too few applicants for a test (needs {MIN_COUNT}+ defaults and non-defaults per group)")
        return

    se = math.sqrt(rate_a * (1 - rate_a) / n_a + rate_b * (1 - rate_b) / n_b)
    low, high = diff - Z_95 * se, diff + Z_95 * se
    print(f"  difference      {100 * diff:+.2f} pp (95% CI {100 * low:+.2f} to {100 * high:+.2f} pp)")
    if rate_b > 0:
        print(f"  relative risk   {rate_a / rate_b:.2f}x")

    # Two-proportion z-test, H0: both groups share one default rate
    pooled = (defaults_a + defaults_b) / (n_a + n_b)
    z = diff / math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    p = math.erfc(abs(z) / math.sqrt(2))
    print(f"  z-test          z = {z:.1f}, p = {p:.1e}" if p > 0 else f"  z-test          z = {z:.1f}, p < 1e-300")


def compare_zero_active_groups(con):
    print("n_active_loans = 0: all loans closed, or no bureau record at all?")
    print(con.sql(ZERO_ACTIVE_GROUPS))
    groups = {name: (customers, defaults)
              for name, customers, defaults, _ in con.execute(ZERO_ACTIVE_GROUPS).fetchall()}

    missing = {"no bureau record", "all loans closed"} - groups.keys()
    if missing:
        print(f"No applicants in: {', '.join(sorted(missing))}; nothing to compare")
        return
    compare_rates("No bureau record", groups["no bureau record"],
                  "all loans closed", groups["all loans closed"])


def main():
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        print_segment_context(con)
        compare_zero_active_groups(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
