-- models/kri.sql
-- Key risk indicators on top of risk_mart: one row for the whole portfolio
WITH pd_by_segment AS (
    -- Empirical PD: observed default rate per number of active bureau loans
    SELECT
        n_active_loans,
        AVG(TARGET) AS pd
    FROM {{ ref('risk_mart') }}
    GROUP BY n_active_loans
),
loans AS (
    SELECT
        m.SK_ID_CURR,
        m.TARGET,
        m.AMT_CREDIT AS ead,
        p.pd,
        0.45 AS lgd,  -- assumption: fixed LGD, not in the data
        NTILE(10) OVER (ORDER BY m.AMT_CREDIT DESC) AS ead_decile
    FROM {{ ref('risk_mart') }} m
    JOIN pd_by_segment p USING (n_active_loans)
)
SELECT
    COUNT(*) AS n_customers,
    AVG(TARGET) AS observed_default_rate,
    AVG(pd) AS avg_pd,
    SUM(ead)  AS total_ead,
    SUM(pd * lgd * ead) AS expected_loss,
    SUM(CASE WHEN ead_decile = 1 THEN ead ELSE 0 END) / SUM(ead) AS top10_concentration
    FROM loans