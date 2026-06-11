{{ config(materialized='view') }}

WITH hist AS (
  SELECT
    ROW_NUMBER() OVER (ORDER BY date) as fixture_id,
    date::TIMESTAMP as match_date,
    home_team,
    away_team,
    home_goals,
    away_goals,
    CASE 
      WHEN home_goals > away_goals THEN 1
      WHEN home_goals = away_goals THEN 0 
      ELSE 2 
    END as outcome,
    'historical' as data_source
  FROM {{ source('raw', 'historical_matches') }}
  WHERE home_goals IS NOT NULL 
    AND away_goals IS NOT NULL
    AND date >= '1990-01-01'
),

live AS (
  SELECT
    CAST(fixture_id AS BIGINT) as fixture_id,
    date as match_date,
    home_team,
    away_team,
    home_goals,
    away_goals,
    CASE 
      WHEN home_goals > away_goals THEN 1
      WHEN home_goals = away_goals THEN 0 
      ELSE 2 
    END as outcome,
    'live_2022' as data_source
  FROM {{ source('raw', 'live_matches') }}
  WHERE status = 'FT'
    AND home_goals IS NOT NULL 
    AND away_goals IS NOT NULL
)

SELECT * FROM hist
UNION ALL
SELECT * FROM live