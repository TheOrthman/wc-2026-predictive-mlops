import duckdb
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss
import mlflow
import mlflow.sklearn
import joblib
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
mlflow.set_experiment("wc_2026")

def train():
    con = duckdb.connect('data/wc.duckdb')
    df = con.sql("SELECT * FROM main_mart.mart_model_features ORDER BY match_date").df()
    con.close()
    
    print(f"Loaded {len(df)} matches for training")
    print(f"Date range: {df['match_date'].min()} to {df['match_date'].max()}")
    
    features = ['home_form', 'away_form', 'home_days_rest', 'away_days_rest', 'elo_diff']
    X = df[features]
    y = df['outcome'] # 0=draw, 1=home_win, 2=away_win
    
    # Time-based split: train on old, test on recent
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    with mlflow.start_run():
        model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            objective='multi:softprob',
            num_class=3,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)
        
        acc = accuracy_score(y_test, preds)
        loss = log_loss(y_test, probs)
        
        mlflow.log_params(model.get_params())
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("log_loss", loss)
        mlflow.sklearn.log_model(model, "model")
        
        joblib.dump(model, 'ml/model.pkl')
        
        # Log to audit table for retrain.py to check
        con = duckdb.connect('data/wc.duckdb')
        con.execute("""
            CREATE TABLE IF NOT EXISTS raw.audit_log (
                run_at TIMESTAMP, 
                event VARCHAR, 
                quarantined INT, 
                updated INT, 
                retrain INT
            )
        """)
        con.sql(f"""
            INSERT INTO raw.audit_log VALUES ('{datetime.now()}', 'model_train', 0, {len(df)}, 0)
        """)
        con.close()
        
        print(f"\nModel trained")
        print(f"Test Accuracy: {acc:.3f}")
        print(f"Log Loss: {loss:.3f}")
        print(f"Model saved to ml/model.pkl")
        print(f"Features: {features}")

if __name__ == "__main__":
    train()