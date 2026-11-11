"""Exploratory questions on the Home Credit data.

Step 3 of the pipeline: ingest.py -> dbt build -> explore.py
Reads the raw tables (application, bureau) and the dbt-built risk_mart.
"""
import duckdb

from credit_risk.config import config


def check_class_imbalance(con):
    print("How imbalanced is the target?")
    print(con.sql("""
        SELECT TARGET, COUNT(*) AS n,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM application
        GROUP BY TARGET
        """))


def check_days_employed_placeholder(con):
    print("What does DAYS_EMPLOYED = 365243 mean?")
    print(con.sql("""
    SELECT
      MIN(AMT_INCOME_TOTAL) AS min_income,
      SUM(CASE WHEN AMT_INCOME_TOTAL IS NULL THEN 1 ELSE 0 END) AS null_income,
      MIN(DAYS_EMPLOYED) AS min_days_employed,
      MAX(DAYS_EMPLOYED) AS max_days_employed
    FROM application
    """))
    print(con.sql("""
    SELECT
        NAME_INCOME_TYPE,
        COUNT(*) AS num_rows
    FROM application
    WHERE DAYS_EMPLOYED = 365243
    GROUP BY NAME_INCOME_TYPE
    """))


def check_bureau_coverage(con):
    print("How many applicants have a bureau history?")
    print(con.sql("""
        SELECT
        COUNT(*) AS applicants,
        COUNT(b.SK_ID_CURR) AS with_bureau_history
        FROM application a
        LEFT JOIN (SELECT DISTINCT SK_ID_CURR FROM bureau) b
        USING (SK_ID_CURR)
        """))


def check_default_rate_by_active_loans(con):
    print("What is the default rate by number of active loans?")
    print(con.sql("""
        SELECT
        n_active_loans,
        COUNT(*) AS customers,
        ROUND(AVG(TARGET) * 100, 1) AS default_rate_pct
        FROM risk_mart
        GROUP BY n_active_loans
        ORDER BY n_active_loans
        LIMIT 8
        """))


def main():
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        check_class_imbalance(con)
        check_days_employed_placeholder(con)
        check_bureau_coverage(con)
        check_default_rate_by_active_loans(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
