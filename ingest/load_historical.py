import pandas as pd
import duckdb
import requests
from typing import Generator
import time
import os
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DUCKDB_PATH", "data/wc.duckdb")

def download_kaggle_wc_history() -> pd.DataFrame:
    url = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
    print("Downloading historical matches 1930-2018...")
    df = pd.read_csv(url)
    wc_df = df[df['tournament'].str.contains('FIFA World Cup', na=False)].copy()
    wc_df['date'] = pd.to_datetime(wc_df['date'])
    print(f"Found {len(wc_df)} historical World Cup matches")
    return wc_df

def stream_api_football_2022() -> Generator[dict, None, None]:
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key or api_key == "your_key_here":
        print("Warning: API_FOOTBALL_KEY not set. Skipping 2022 API data.")
        return
        
    headers = {"x-apisports-key": api_key}
    base = "https://v3.football.api-sports.io"
    
    print("Fetching 2022 Qatar World Cup from API-Football...")
    total = 0
    for page in range(1, 5):
        try:
            resp = requests.get(
                f"{base}/fixtures",
                headers=headers,
                params={"league": 1, "season": 2022, "page": page},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            
            if not data["response"]:
                print(f"Page {page}: No more results")
                break
                
            for match in data["response"]:
                total += 1
                yield {
                    "fixture_id": str(match["fixture"]["id"]),
                    "date": match["fixture"]["date"],
                    "status": match["fixture"]["status"]["short"],
                    "home_team_id": match["teams"]["home"]["id"],
                    "away_team_id": match["teams"]["away"]["id"],
                    "home_team": match["teams"]["home"]["name"],
                    "away_team": match["teams"]["away"]["name"],
                    "home_goals": match["goals"]["home"],
                    "away_goals": match["goals"]["away"],
                    "tournament": "FIFA World Cup 2022",
                    "raw_json": str(match)
                }
            print(f"Page {page}: Got {len(data['response'])} matches, total: {total}")
            time.sleep(1)
        except Exception as e:
            print(f"API error on page {page}: {e}")
            break
    print(f"API fetch complete. Total 2022 matches: {total}")

def init_db():
    con = duckdb.connect(DB_PATH)
    print(f"Initializing DuckDB at {DB_PATH}")
    
    con.sql("""
        CREATE SCHEMA IF NOT EXISTS raw;
        CREATE TABLE IF NOT EXISTS raw.historical_matches (
            date TIMESTAMP, home_team VARCHAR, away_team VARCHAR,
            home_goals INT, away_goals INT, tournament VARCHAR,
            city VARCHAR, country VARCHAR
        );
        CREATE TABLE IF NOT EXISTS raw.live_matches (
            fixture_id VARCHAR PRIMARY KEY, date TIMESTAMP, 
            home_team_id INT, away_team_id INT, home_team VARCHAR,
            away_team VARCHAR, home_goals INT, away_goals INT, 
            status VARCHAR, tournament VARCHAR, updated_at TIMESTAMP, 
            raw_json JSON
        );
    """)
    
    # Load 1930-2018 - only if table empty
    existing_hist = con.sql("SELECT COUNT(*) FROM raw.historical_matches").fetchone()[0]
    if existing_hist == 0:
        hist_df = download_kaggle_wc_history()
        con.register('hist_df', hist_df)
        con.sql("INSERT INTO raw.historical_matches SELECT date, home_team, away_team, home_score, away_score, tournament, city, country FROM hist_df")
        print(f"Inserted {len(hist_df)} historical matches")
    else:
        print(f"Historical table already has {existing_hist} matches, skipping")
    
    # Load 2022 - truncate and reload
    con.sql("DELETE FROM raw.live_matches WHERE tournament = 'FIFA World Cup 2022'")
    count = 0
    start_time = time.time()
    
    for match in stream_api_football_2022():
        con.execute("""
            INSERT INTO raw.live_matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, [
            match['fixture_id'], match['date'], match['home_team_id'], 
            match['away_team_id'], match['home_team'], match['away_team'],
            match['home_goals'], match['away_goals'], match['status'], 
            match['tournament'], pd.Timestamp.now(), match['raw_json']
        ])
        count += 1
    
    con.commit()
    duration = time.time() - start_time
    
    total_hist = con.sql("SELECT COUNT(*) FROM raw.historical_matches").fetchone()[0]
    total_2022 = con.sql("SELECT COUNT(*) FROM raw.live_matches WHERE tournament = 'FIFA World Cup 2022'").fetchone()[0]
    
    print(f"\nHistorical: {total_hist} matches")
    print(f"2022 Qatar: {total_2022} matches")
    print(f"2022 load time: {duration:.1f}s")
    print(f"DB ready at {DB_PATH}")
    con.close()

if __name__ == "__main__":
    init_db()