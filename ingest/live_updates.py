import duckdb
import requests
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DUCKDB_PATH", "data/wc.duckdb")
API_KEY = os.getenv("API_FOOTBALL_KEY")

def fetch_live_fixtures():
    """Fetch today's + tomorrow's fixtures. Quarantine failures."""
    con = duckdb.connect(DB_PATH)
    
    if not API_KEY:
        print("No API key. Skipping live updates.")
        return 0
    
    headers = {"x-apisports-key": API_KEY}
    base = "https://v3.football.api-sports.io"
    
    # Get fixtures for next 7 days - adjust league/season for 2026 when it starts
    resp = requests.get(
        f"{base}/fixtures",
        headers=headers,
        params={"league": 1, "season": 2026, "next": 7},
        timeout=15
    )
    
    updated = 0
    quarantined = 0
    
    if resp.status_code == 200:
        data = resp.json()
        for match in data.get("response", []):
            try:
                fixture_id = str(match["fixture"]["id"])
                status = match["fixture"]["status"]["short"]
                
                # Only store finished matches for training
                if status!= "FT":
                    continue
                
                con.execute("""
                    INSERT OR REPLACE INTO raw.live_matches VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, [
                    fixture_id,
                    match["fixture"]["date"],
                    match["teams"]["home"]["id"],
                    match["teams"]["away"]["id"],
                    match["teams"]["home"]["name"],
                    match["teams"]["away"]["name"],
                    match["goals"]["home"],
                    match["goals"]["away"],
                    status,
                    "FIFA World Cup 2026",
                    datetime.now(),
                    str(match)
                ])
                updated += 1
                
            except Exception as e:
                # Quarantine bad records
                con.execute("""
                    INSERT INTO raw.quarantine VALUES (?,?,?,?,?)
                """, [
                    match.get("fixture", {}).get("id", "unknown"),
                    "parse_error",
                    str(match),
                    datetime.now(),
                    False
                ])
                quarantined += 1
    
    con.sql(f"""
        INSERT INTO audit_log VALUES ('{datetime.now()}', 'live_update', 0, {updated}, 1)
    """)
    con.close()
    
    print(f"Updated: {updated} matches, Quarantined: {quarantined}")
    return updated

if __name__ == "__main__":
    fetch_live_fixtures()