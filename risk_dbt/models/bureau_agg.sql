-- Credit cards are excluded: a card line is not comparable to an installment
-- loan, and its AMT_CREDIT_SUM has no consistent meaning (often 0 or the limit).
-- Applicants with only credit cards in the bureau therefore get no row here.
SELECT
    SK_ID_CURR,
    COUNT(*) AS n_loans,
    AVG(AMT_CREDIT_SUM) AS avg_amount,
    SUM(CASE WHEN CREDIT_ACTIVE = 'Active' THEN 1 ELSE 0 END) AS n_active_loans
FROM {{ source('raw', 'bureau') }}
WHERE CREDIT_TYPE IS DISTINCT FROM 'Credit card'  -- keeps loans of unknown type
GROUP BY SK_ID_CURR
