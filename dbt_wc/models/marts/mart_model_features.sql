{{ config(materialized='table') }}

WITH base AS (
  SELECT * FROM {{ ref('stg_matches') }}
),

form_calc AS (
  SELECT
    fixture_id,
    match_date,
    home_team,
    away_team,
    outcome,
    data_source,
    -- Home form: last 5 games
    AVG(CASE 
      WHEN lag_outcome = 1 AND lag_team = home_team THEN 3.0
      WHEN lag_outcome = 2 AND lag_team = home_team THEN 3.0
      WHEN lag_outcome = 0 AND lag_team = home_team THEN 1.0
      ELSE 0.0 
    END) OVER (
      PARTITION BY home_team 
      ORDER BY match_date 
      ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
    ) as home_form,
    
    -- Away form: last 5 games  
    AVG(CASE 
      WHEN lag_outcome = 1 AND lag_team = away_team THEN 3.0
      WHEN lag_outcome = 2 AND lag_team = away_team THEN 3.0
      WHEN lag_outcome = 0 AND lag_team = away_team THEN 1.0
      ELSE 0.0 
    END) OVER (
      PARTITION BY away_team 
      ORDER BY match_date 
      ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
    ) as away_form,
    
    DATE_DIFF('day', 
      LAG(match_date) OVER (PARTITION BY home_team ORDER BY match_date), 
      match_date
    ) as home_days_rest,
    
    DATE_DIFF('day', 
      LAG(match_date) OVER (PARTITION BY away_team ORDER BY match_date), 
      match_date
    ) as away_days_rest
  FROM (
    SELECT 
      b.*,
      LAG(b.outcome) OVER (PARTITION BY CASE WHEN team = b.home_team THEN b.home_team ELSE b.away_team END ORDER BY b.match_date) as lag_outcome,
      LAG(CASE WHEN team = b.home_team THEN b.home_team ELSE b.away_team END) OVER (PARTITION BY team ORDER BY b.match_date) as lag_team
    FROM base b
    CROSS JOIN UNNEST([b.home_team, b.away_team]) AS t(team)
  )
),

with_elo AS (
  SELECT 
    f.fixture_id,
    f.match_date,
    f.home_team,
    f.away_team,
    f.home_form,
    f.away_form,
    f.home_days_rest,
    f.away_days_rest,
    f.outcome,
    f.data_source,
    e.elo_diff
  FROM form_calc f
  LEFT JOIN {{ ref('mart_elo_ratings') }} e ON f.fixture_id = e.fixture_id
  QUALIFY ROW_NUMBER() OVER (PARTITION BY f.fixture_id ORDER BY f.home_team) = 1
)

SELECT 
  fixture_id,
  match_date,
  home_team,
  away_team,
  COALESCE(home_form, 1.5) as home_form,
  COALESCE(away_form, 1.5) as away_form,
  COALESCE(home_days_rest, 7) as home_days_rest,
  COALESCE(away_days_rest, 7) as away_days_rest,
  COALESCE(elo_diff, 0) as elo_diff,
  outcome,
  data_source
FROM with_elo
WHERE match_date >= '1995-01-01'