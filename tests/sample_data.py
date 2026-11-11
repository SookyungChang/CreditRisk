"""Create a small synthetic risk.duckdb with the raw tables the pipeline reads.

Used by the pytest suite and by CI, which cannot download the Kaggle data.
The rows are made up; only the column names and types follow the real files.

CI usage (instead of ingest.py): uv run python tests/sample_data.py
"""
import sys

import duckdb

from credit_risk.config import config


def create_sample_db(path):
    con = duckdb.connect(str(path))
    try:
        con.execute("""
            CREATE OR REPLACE TABLE application (
                SK_ID_CURR BIGINT, TARGET BIGINT, AMT_INCOME_TOTAL DOUBLE, AMT_CREDIT DOUBLE,
                AMT_ANNUITY DOUBLE, DAYS_EMPLOYED BIGINT, NAME_INCOME_TYPE VARCHAR
            )
        """)
        con.execute("""
            INSERT INTO application VALUES
                (1, 0, 100000.0, 300000.0, 15000.0, -1200, 'Working'),
                (2, 1, 50000.0, 250000.0, 12000.0, -300, 'Working'),
                (3, 0, 80000.0, 160000.0, 9000.0, 365243, 'Pensioner'),
                (4, 1, 60000.0, 120000.0, 7000.0, 365243, 'Unemployed')
        """)
        con.execute("""
            CREATE OR REPLACE TABLE bureau (
                SK_ID_CURR BIGINT, SK_ID_BUREAU BIGINT, CREDIT_ACTIVE VARCHAR, AMT_CREDIT_SUM DOUBLE
            )
        """)
        # Applicant 3 has no bureau history; applicant 9 is not in application
        con.execute("""
            INSERT INTO bureau VALUES
                (1, 11, 'Active', 200000.0),
                (1, 12, 'Closed', 100000.0),
                (2, 21, 'Active', 50000.0),
                (4, 41, 'Closed', 80000.0),
                (9, 91, 'Active', 10000.0)
        """)
    finally:
        con.close()


def main():
    if config.DB_PATH.exists() and "--force" not in sys.argv:
        sys.exit(f"{config.DB_PATH.name} already exists; pass --force to replace its raw tables with sample data")
    create_sample_db(config.DB_PATH)
    print(f"Wrote sample application and bureau tables to {config.DB_PATH.name}")


if __name__ == "__main__":
    main()
