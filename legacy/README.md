# legacy/

`data_quality_checks.py` is the original Python data quality check (formerly
`src/creditRisk/DQ.py`). It has been **replaced by the dbt tests** in
`risk_dbt/` and is no longer part of the pipeline. Run `dbt build` instead.

| Legacy check | dbt replacement |
|---|---|
| No ID duplicates | `unique` on `risk_mart.SK_ID_CURR` (`models/schema.yml`) |
| No 1000 years employed | `tests/assert_no_1000_years_employed.sql` |
| risk_mart row_count = application row_count | `tests/assert_row_count_matches.sql` |
| No `SK_ID_CURR` / `TARGET` / `n_loans` / `n_active_loans` / `is_not_employed` NULL | `not_null` on each column (`models/schema.yml`) |
