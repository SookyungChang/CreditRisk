"""Download the Home Credit data from Kaggle and load the raw tables into DuckDB.

Step 1 of the pipeline: ingest.py -> dbt build -> explore.py
"""
import os

import duckdb
import kagglehub
from dotenv import load_dotenv

from credit_risk.config import config

COMPETITION = "home-credit-default-risk"

# CSV file -> raw table name (declared as dbt sources in risk_dbt/models/sources.yml)
RAW_TABLES = {
    "application_train.csv": "application",
    "bureau.csv": "bureau",
}


def create_table_from_csv(con, csv_path, table_name):
    con.sql(f"""
    CREATE OR REPLACE TABLE {table_name} AS
    SELECT * FROM read_csv_auto('{csv_path}')
    """)
    n_rows = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchall()[0][0]
    print(f"{table_name}: {n_rows:,} rows")


def main():
    load_dotenv()  # Kaggle credentials (KAGGLE_USERNAME, KAGGLE_KEY) from .env
    path = kagglehub.competition_download(COMPETITION)
    print("Path to competition files:", path)

    con = duckdb.connect(str(config.DB_PATH))
    try:
        for filename, table_name in RAW_TABLES.items():
            create_table_from_csv(con, os.path.join(path, filename), table_name)
    finally:
        con.close()


if __name__ == "__main__":
    main()
