-- Reconciliation check of the PD calculation in kri.
-- PD per segment is that segment's observed default rate, so its
-- customer-weighted average must equal the portfolio default rate.
-- Fails if the two drift apart beyond floating-point noise.
SELECT *
FROM {{ ref('kri') }}
WHERE ABS(avg_pd - observed_default_rate) > 1e-9
