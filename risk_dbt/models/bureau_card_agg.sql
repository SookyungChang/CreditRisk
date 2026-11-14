-- Credit cards per applicant: the bureau rows that bureau_agg excludes.
-- Only counts are kept, because AMT_CREDIT_SUM has no consistent meaning for
-- cards (often 0 or the limit).
SELECT
    SK_ID_CURR,
    COUNT(*) AS n_cards,
    SUM(CASE WHEN CREDIT_ACTIVE = 'Active' THEN 1 ELSE 0 END) AS n_active_cards
FROM {{ source('raw', 'bureau') }}
WHERE CREDIT_TYPE = 'Credit card'  -- the complement of the filter in bureau_agg
GROUP BY SK_ID_CURR
