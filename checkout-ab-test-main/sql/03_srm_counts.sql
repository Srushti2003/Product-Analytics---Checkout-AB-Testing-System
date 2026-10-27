-- Sample-ratio-mismatch inputs: users per arm, before and after cleaning.
-- The chi-square test itself runs in Python (src/abtest/stats.py::srm_test).

SELECT 'raw (bots included, conflicts dropped)' AS population, variant, COUNT(*) AS users
FROM (
    SELECT user_id, MIN(variant) AS variant
    FROM assignments
    GROUP BY user_id
    HAVING COUNT(DISTINCT variant) = 1
)
GROUP BY variant

UNION ALL

SELECT 'clean (analysis population)', variant, COUNT(*)
FROM clean_assignments
GROUP BY variant;
