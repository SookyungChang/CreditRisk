SELECT
    a.SK_ID_CURR,
    a.TARGET,
    a.AMT_CREDIT,           -- new: exposure amount (used as EAD)
    COALESCE(b.n_loans, 0) AS n_loans,
    b.avg_amount,
    COALESCE(b.n_active_loans, 0) AS n_active_loans,
    a.AMT_CREDIT / NULLIF(a.AMT_INCOME_TOTAL, 0) AS credit_income_ratio,
    a.days_employed,        -- already cleaned in staging
    a.is_not_employed       -- already derived in staging
FROM {{ ref('stg_application') }} a
LEFT JOIN {{ ref('bureau_agg') }} b USING (SK_ID_CURR)