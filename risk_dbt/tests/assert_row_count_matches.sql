-- Consistency check
-- Fails if the LEFT JOIN added or dropped rows
SELECT *
FROM (
    SELECT
        (SELECT COUNT(*) FROM {{ ref('risk_mart') }})               AS mart_rows,
        (SELECT COUNT(*) FROM {{ source('raw', 'application') }})   AS app_rows
)
WHERE mart_rows != app_rows