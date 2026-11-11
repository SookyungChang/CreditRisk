# legacy/

Kept for reference only; nothing here is part of the pipeline.

## exploration.ipynb

The original exploration notebook that this project grew out of: first look
at the Kaggle files, the first versions of `bureau_agg` and `risk_mart`, the
first data quality checks, and the first hand-written column lineage with a
column consistency check (now `lineage/lineage.py`). Outputs are cleared so no
raw Kaggle data is published. It imports the old package name `creditRisk`
(now `credit_risk`), so it does not run as-is. To open it, install the
notebook group: `uv sync --group notebook`.

## data_quality_checks.py

The original Python data quality check (formerly `src/creditRisk/DQ.py`). It
has been **replaced by the dbt tests** in `risk_dbt/`. Run `dbt build` instead.

| Legacy check | dbt replacement |
|---|---|
| No ID duplicates | `unique` on `risk_mart.SK_ID_CURR` (`models/schema.yml`) |
| No 1000 years employed | `tests/assert_no_1000_years_employed.sql` |
| risk_mart row_count = application row_count | `tests/assert_row_count_matches.sql` |
| No `SK_ID_CURR` / `TARGET` / `n_loans` / `n_active_loans` / `is_not_employed` NULL | `not_null` on each column (`models/schema.yml`) |
