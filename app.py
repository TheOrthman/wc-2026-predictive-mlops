import streamlit as st
import duckdb
import pandas as pd
import joblib
import plotly.express as px

st.set_page_config(page_title="WC 2026 Predictor", layout="wide")

@st.cache_resource
def load_model():
    return joblib.load('ml/model.pkl')

@st.cache_data
def load_data():
    con = duckdb.connect('data/wc.duckdb', read_only=True)
    df = con.sql("SELECT * FROM main_mart.mart_model_features ORDER BY match_date DESC LIMIT 1000").df()
    con.close()
    return df

model = load_model()
df = load_data()

st.title("World Cup 2026 Predictive MLOps")
st.caption("Accuracy: 58.2% | Features: Form + Rest + ELO Rating")

tab1, tab2, tab3 = st.tabs(["Predictions", "Data Explorer", "Monitoring"])

with tab1:
    st.header("⚽ Match Outcome Predictor")
    col1, col2 = st.columns(2)
    
    teams = sorted(set(df['home_team'].unique()) | set(df['away_team'].unique()))
    
    with col1:
        home_team = st.selectbox("Home Team", teams, index=teams.index("Brazil") if "Brazil" in teams else 0)
        home_form = st.slider("Home Form (0-3 pts avg)", 0.0, 3.0, 1.5, 0.1, key="hform")
        home_rest = st.slider("Home Days Rest", 1, 14, 7, key="hrest")
        home_elo = st.slider("Home ELO Rating", 1300, 1900, 1600, key="helo", 
                             help="1500=average, 1750=elite, 1900=peak Brazil/France")
    
    with col2:
        away_team = st.selectbox("Away Team", teams, index=teams.index("Argentina") if "Argentina" in teams else 1)
        away_form = st.slider("Away Form (0-3 pts avg)", 0.0, 3.0, 1.5, 0.1, key="aform")
        away_rest = st.slider("Away Days Rest", 1, 14, 7, key="arest")
        away_elo = st.slider("Away ELO Rating", 1300, 1900, 1600, key="aelo",
                             help="1400=weak, 1500=average, 1650=strong")
    
    st.divider()
    
    if st.button("Predict", type="primary", use_container_width=True):
        elo_diff = home_elo - away_elo
        X = pd.DataFrame([[home_form, away_form, home_rest, away_rest, elo_diff]], 
                         columns=['home_form', 'away_form', 'home_days_rest', 'away_days_rest', 'elo_diff'])
        probs = model.predict_proba(X)[0]
        
        st.subheader("Prediction Results")
        st.write(f"**ELO Difference:** {elo_diff:+.0f} → {'Home' if elo_diff > 0 else 'Away'} team favored")
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"{home_team} Win", f"{probs[1]*100:.1f}%")
        col2.metric("Draw", f"{probs[0]*100:.1f}%")
        col3.metric(f"{away_team} Win", f"{probs[2]*100:.1f}%")
        
        fig = px.bar(
            x=[f"{home_team} Win", "Draw", f"{away_team} Win"], 
            y=probs*100,
            color=[f"{home_team} Win", "Draw", f"{away_team} Win"],
            color_discrete_map={
                f"{home_team} Win": "#2E86AB", 
                "Draw": "#A23B72", 
                f"{away_team} Win": "#F18F01"
            },
            labels={'x':'Outcome', 'y':'Probability %'}
        )
        fig.update_layout(showlegend=False, yaxis_range=[0,100])
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Historical Data Explorer")
    st.dataframe(df.head(50), use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Home Form Distribution")
        fig = px.histogram(df, x='home_form', nbins=30)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("ELO Difference Distribution")
        fig = px.histogram(df, x='elo_diff', nbins=30, title="ELO Diff: Home - Away")
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Model Monitoring")
    st.subheader("Feature Importance")
    importance = pd.DataFrame({
        'feature': ['home_form', 'away_form', 'home_days_rest', 'away_days_rest', 'elo_diff'],
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    fig = px.bar(importance, x='importance', y='feature', orientation='h',
                 labels={'importance':'Importance Score', 'feature':''})
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Dataset Stats")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Matches", f"{len(df):,}")
    col2.metric("Latest Match", str(df['match_date'].max())[:10])
    col3.metric("Avg ELO Diff", f"{df['elo_diff'].mean():.1f}")
    
    st.info("💡 Run `mlflow ui` in terminal to see experiment tracking")