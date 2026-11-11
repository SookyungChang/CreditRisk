SELECT
    SK_ID_CURR,
    COUNT(*) AS n_loans,
    AVG(AMT_CREDIT_SUM) AS avg_amount,
    SUM(CASE WHEN CREDIT_ACTIVE = 'Active' THEN 1 ELSE 0 END) AS n_active_loans
FROM {{ source('raw', 'bureau') }}
GROUP BY SK_ID_CURR