{{ config(materialized='table') }}

WITH base AS (
  SELECT 
    fixture_id,
    match_date,
    home_team,
    away_team,
    outcome,
    ROW_NUMBER() OVER (ORDER BY match_date, fixture_id) as rn
  FROM {{ ref('stg_matches') }}
  WHERE match_date >= '1990-01-01'
),

home_elo AS (
  SELECT 
    b.fixture_id,
    b.home_team,
    -- ELO proxy: win% over last 20 games scaled to 1300-1900 range
    1300 + 600 * COALESCE(
      AVG(CASE 
        WHEN b2.home_team = b.home_team AND b2.outcome = 1 THEN 1.0
        WHEN b2.away_team = b.home_team AND b2.outcome = 2 THEN 1.0
        WHEN (b2.home_team = b.home_team OR b2.away_team = b.home_team) AND b2.outcome = 0 THEN 0.5
        ELSE 0.0 
      END) OVER (
        PARTITION BY b.home_team 
        ORDER BY b.rn 
        ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
      ), 0.5
    ) as home_elo
  FROM base b
  LEFT JOIN base b2 ON b2.rn < b.rn 
    AND (b2.home_team = b.home_team OR b2.away_team = b.home_team)
),

away_elo AS (
  SELECT 
    b.fixture_id,
    b.away_team,
    1300 + 600 * COALESCE(
      AVG(CASE 
        WHEN b2.home_team = b.away_team AND b2.outcome = 1 THEN 1.0
        WHEN b2.away_team = b.away_team AND b2.outcome = 2 THEN 1.0
        WHEN (b2.home_team = b.away_team OR b2.away_team = b.away_team) AND b2.outcome = 0 THEN 0.5
        ELSE 0.0 
      END) OVER (
        PARTITION BY b.away_team 
        ORDER BY b.rn 
        ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
      ), 0.5
    ) as away_elo
  FROM base b
  LEFT JOIN base b2 ON b2.rn < b.rn 
    AND (b2.home_team = b.away_team OR b2.away_team = b.away_team)
)

SELECT 
  h.fixture_id,
  ROUND(h.home_elo, 1) as home_elo,
  ROUND(a.away_elo, 1) as away_elo,
  ROUND(h.home_elo - a.away_elo, 1) as elo_diff
FROM home_elo h
JOIN away_elo a ON h.fixture_id = a.fixture_id