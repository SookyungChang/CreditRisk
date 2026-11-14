-- bureau_agg counts the non-card loans and bureau_card_agg the credit cards.
-- Together they must cover every bureau row exactly once per applicant, so a
-- change to one filter without the other (a loan counted twice or not at all)
-- fails here.
WITH bureau_rows AS (
    SELECT SK_ID_CURR, COUNT(*) AS n_rows
    FROM {{ source('raw', 'bureau') }}
    GROUP BY SK_ID_CURR
)
SELECT
    r.SK_ID_CURR,
    r.n_rows,
    COALESCE(l.n_loans, 0) AS n_loans,
    COALESCE(c.n_cards, 0) AS n_cards
FROM bureau_rows r
LEFT JOIN {{ ref('bureau_agg') }} l USING (SK_ID_CURR)
LEFT JOIN {{ ref('bureau_card_agg') }} c USING (SK_ID_CURR)
WHERE r.n_rows <> COALESCE(l.n_loans, 0) + COALESCE(c.n_cards, 0)
