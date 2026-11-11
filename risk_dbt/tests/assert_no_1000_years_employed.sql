-- Fails if any sentinel value (365243) survived cleaning
SELECT *
FROM {{ ref('risk_mart') }}
WHERE days_employed = 365243