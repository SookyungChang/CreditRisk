-- models/stg_application.sql
-- Clean raw application data; one row per application, no business logic
SELECT
    SK_ID_CURR,
    TARGET,
    AMT_INCOME_TOTAL,
    AMT_CREDIT,
    AMT_ANNUITY,
    CASE WHEN DAYS_EMPLOYED = 365243 THEN NULL ELSE DAYS_EMPLOYED END AS days_employed,
    CASE WHEN DAYS_EMPLOYED = 365243 THEN 1 ELSE 0 END AS is_not_employed
FROM {{ source('raw', 'application') }}