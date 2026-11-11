"""LEGACY: replaced by the dbt tests in risk_dbt/ (run with `dbt build`).

Kept for reference only; not part of the pipeline. See legacy/README.md.
"""
checks = {
        "No ID duplicates":
            "SELECT COUNT(*) - COUNT(DISTINCT SK_ID_CURR) FROM risk_mart",
        "No 1000 years employed":
            "SELECT COUNT(*) FROM risk_mart WHERE days_employed = 365243",
        "risk_mart row_count = application row_count":
            "SELECT (SELECT COUNT(*) FROM risk_mart) - (SELECT COUNT(*) FROM application)"
    }

not_null_cols = ["SK_ID_CURR", "TARGET", "n_loans", "n_active_loans", "is_not_employed"]

for col in not_null_cols:
    checks[f"No {col} NULL"] = f"SELECT COUNT(*) FROM risk_mart WHERE {col} IS NULL"

def data_quality_checks(con):
    for name, query in checks.items():
        violations = con.sql(query).fetchall()[0][0]
        status = "✅ PASS" if violations == 0 else f"❌ FAIL ({violations})"
        print(f"{status}  {name}")
