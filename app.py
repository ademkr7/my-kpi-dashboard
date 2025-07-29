import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import time
import sqlite3
import requests
import json

# Set page configuration for full-screen TV display
st.set_page_config(layout="wide", page_title="KPI Dashboard", initial_sidebar_state="collapsed")

# Custom CSS for TV-friendly design with enhanced responsiveness and KPI titles
st.markdown(
    """
    <style>
        .stApp {
            background-color: #1a202c;
            color: white;
            font-size: 2vw;
            padding: 2%;
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .stButton>button {
            background-color: #4a90e2;
            color: white;
            font-size: 1.5vw;
            padding: 1% 2%;
            margin-bottom: 1%;
            border: none;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        .stTabs, .stExpander {
            display: none;
        }
        .stPlotlyChart {
            margin: 0.5% auto;
            max-width: 100%;
            margin-top: 1%;
        }
        .content {
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .score-label {
            text-align: center;
            color: white;
            font-size: 3vw;
            margin-top: -0.5%;
        }
        h1 {
            font-size: 3vw;
            color: #f59e0b;
            text-align: center;
            margin: 0;
            padding: 1% 2%;
            background-color: rgba(245, 158, 11, 0.1);
            border-bottom: 0.3vw solid #f59e0b;
        }
        hr {
            border: 0.2vw solid #f59e0b;
            margin: 1% 0;
        }
        .kpi-title {
            background-color: #1e90ff;
            color: white;
            font-size: 1.2vw;
            text-align: center;
            padding: 0.5% 1%;
            margin-bottom: 0.5%;
            border-radius: 5px 5px 0 0;
        }
        .subcategory-band {
            background-color: #1e90ff;
            color: white;
            font-size: 1.2vw;
            text-align: center;
            padding: 0.5% 1%;
            margin-bottom: 0.5%;
            border-radius: 5px 5px 0 0;
        }
        .error-message {
            font-size: 2vw;
            color: #ff4444;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 1%;
            border-radius: 5px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Database setup
def init_db():
    conn = sqlite3.connect("kpi_database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS kpis
                 (kpi_name TEXT, rate REAL, target REAL, poids REAL, obj REAL, real REAL, score REAL, timestamp TEXT)''')
    c.execute("PRAGMA table_info(kpis)")
    columns = [info[1] for info in c.fetchall()]
    if 'score' not in columns:
        c.execute("ALTER TABLE kpis ADD COLUMN score REAL")
    conn.commit()
    return conn

def save_to_db(kpi_data):
    conn = init_db()
    c = conn.cursor()
    for kpi in kpi_data:
        score = kpi[6] if len(kpi) > 6 else None
        c.execute("INSERT OR REPLACE INTO kpis (kpi_name, rate, target, poids, obj, real, score, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (kpi[0], kpi[1], kpi[2], kpi[3], kpi[4], kpi[5], score, time.ctime()))
    conn.commit()
    conn.close()

# API simulation
API_URL = os.getenv("API_URL", "http://localhost:8501/api/kpis")
@st.cache_data(ttl=10)
def fetch_kpi_data():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        kpi_data = [(item["kpi_name"], item["rate"], item["target"], item["poids"], item["obj"], item["real"], item.get("score"))
                    for item in data]
        if not kpi_data:
            st.markdown("<div class='error-message'>API returned no data.</div>", unsafe_allow_html=True)
        save_to_db(kpi_data)
        return kpi_data
    except requests.exceptions.RequestException as e:
        st.markdown(f"<div class='error-message'>API Error: {str(e)}</div>", unsafe_allow_html=True)
        st.markdown("<div class='error-message'>Failed to fetch data from API. Using local JSON file as fallback.</div>", unsafe_allow_html=True)
        json_file = os.path.join(os.path.dirname(__file__), "kpi_data.json")
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            required_columns = ["Objectifs", "Taux de réalisation", "OBJECTIF 2025", "poids", "Réalisation 2025", "score", "Column2", "Column3"]
            df = pd.DataFrame(data)
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.markdown(f"<div class='error-message'>Missing required columns in JSON: {', '.join(missing_columns)}</div>", unsafe_allow_html=True)
                return []
            df = df[required_columns]
            df = df.dropna(subset=["poids"])
            df["Taux de réalisation"] = pd.to_numeric(df["Taux de réalisation"], errors="coerce") * 100
            kpi_data = [(row["Objectifs"], row["Taux de réalisation"], row["OBJECTIF 2025"], row["poids"], row["OBJECTIF 2025"], row["Réalisation 2025"], row["score"])
                        for _, row in df.iterrows() if pd.notna(row["Objectifs"])]
            save_to_db(kpi_data)
            return kpi_data
        else:
            st.markdown(f"<div class='error-message'>kpi_data.json not found at {json_file}. Please add it and rerun the app.</div>", unsafe_allow_html=True)
            return []

# Initialize data
json_file = os.path.join(os.path.dirname(__file__), "kpi_data.json")
if "df" not in st.session_state:
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        required_columns = ["Objectifs", "Taux de réalisation", "OBJECTIF 2025", "poids", "Réalisation 2025", "score", "Column2", "Column3"]
        df = pd.DataFrame(data)
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.markdown(f"<div class='error-message'>Missing required columns in JSON: {', '.join(missing_columns)}</div>", unsafe_allow_html=True)
            st.stop()
        df = df[required_columns]
        st.session_state.df = df
    else:
        st.markdown(f"<div class='error-message'>kpi_data.json not found at {json_file}. Please add it and rerun the app.</div>", unsafe_allow_html=True)
        st.stop()

# Clean and prepare data
if "df" in st.session_state:
    df = st.session_state.df
    df = df.dropna(subset=["poids"])
    df["Taux de réalisation"] = pd.to_numeric(df["Taux de réalisation"], errors="coerce") * 100
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["OBJECTIF 2025"] = pd.to_numeric(df["OBJECTIF 2025"], errors="coerce")
    df["Réalisation 2025"] = pd.to_numeric(df["Réalisation 2025"], errors="coerce")
    df["poids"] = pd.to_numeric(df["poids"], errors="coerce")

    # Manual refresh button
    if st.button("Refresh Data", help="Update graphs with the latest JSON data", key="refresh_button"):
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            required_columns = ["Objectifs", "Taux de réalisation", "OBJECTIF 2025", "poids", "Réalisation 2025", "score", "Column2", "Column3"]
            df = pd.DataFrame(data)
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.markdown(f"<div class='error-message'>Missing required columns in JSON: {', '.join(missing_columns)}</div>", unsafe_allow_html=True)
                st.stop()
            df = df[required_columns]
            st.session_state.df = df
            st.rerun()

    # Fetch KPI data
    kpi_data = fetch_kpi_data()
    if not kpi_data and os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        required_columns = ["Objectifs", "Taux de réalisation", "OBJECTIF 2025", "poids", "Réalisation 2025", "score", "Column2", "Column3"]
        df = pd.DataFrame(data)
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.markdown(f"<div class='error-message'>Missing required columns in JSON: {', '.join(missing_columns)}</div>", unsafe_allow_html=True)
            kpi_data = []
        else:
            df = df[required_columns]
            kpi_data = [(row["Objectifs"], row["Taux de réalisation"], row["OBJECTIF 2025"], row["poids"], row["OBJECTIF 2025"], row["Réalisation 2025"], row["score"])
                        for _, row in df.iterrows() if pd.notna(row["Objectifs"])]
            save_to_db(kpi_data)

    # Dynamic dashboard layout with row spanning
    st.markdown("<div class='content'>", unsafe_allow_html=True)
    st.markdown("<h1>Tableau de bord des Indicateurs Clés de Performance (KPIs)</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    current_group = None
    group_positions = []  # Store (row_idx, col_idx, group_title) for each group start
    max_cols = 6
    rows = [st.columns(max_cols)]  # Initialize with first row
    row_idx = 0
    col_idx = 0

    for idx, (kpi_name, rate, target, poids, obj, real, score) in enumerate(kpi_data[:17]):
        # Split KPI name at the hyphen
        parts = kpi_name.split(" - ", 1)  # Split at the first hyphen
        group_title = parts[0] if len(parts) > 0 else kpi_name
        subcategory = parts[1] if len(parts) > 1 else kpi_name

        gauge_value = min((score / poids * 100) if poids != 0 and score is not None else 0, 100)
        color = "#17b248" if gauge_value >= 80 else '#ffa500' if gauge_value >= 50 else '#dc143c'

        # Start a new group
        if current_group != group_title:
            if current_group is not None:
                # Store the position of the previous group's start
                group_positions.append((group_start_idx // max_cols, group_start_idx % max_cols, current_group))
            current_group = group_title
            group_start_idx = idx

        # Manage row and column indices
        if col_idx >= max_cols:
            row_idx += 1
            while len(rows) <= row_idx:
                rows.append(st.columns(max_cols))
            col_idx = 0

        with rows[row_idx][col_idx]:
            st.markdown(f"<div class='subcategory-band'>{subcategory}</div>", unsafe_allow_html=True)
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=gauge_value,
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={'shape': "angular",
                       'axis': {'range': [0, 100], 'tickvals': [0, 100], 'ticktext': ['0%', '100%']},
                       'bar': {'color': color, 'thickness': 0.3},
                       'bgcolor': "white",
                       'borderwidth': 2,
                       'bordercolor': "#2d3748"},
                number={'valueformat': ".1f", 'suffix': "%", 'font': {'size': 20, 'color': 'black', 'family': 'Arial, sans-serif', 'weight': 'bold'}},
            ))
            fig.add_annotation(
                text=f"{score * 100:.1f}%" if score is not None else "0%",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="black", family="Arial, sans-serif", weight="bold")
            )
            fig.update_layout(
                height=150,
                width=130,
                margin=dict(l=5, r=5, t=20, b=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )
            st.plotly_chart(fig)

        col_idx += 1

    # Handle the last group
    if current_group is not None:
        group_positions.append((group_start_idx // max_cols, group_start_idx % max_cols, current_group))

    # Add regional score dynamically
    if len(rows) > 2 and 5 < max_cols:  # Ensure regional score fits in the last row, column 5
        with rows[2][5]:
            st.markdown("<div class='kpi-title'>Score de la Région</div>", unsafe_allow_html=True)
            fig_score = go.Figure(go.Indicator(
                mode="gauge+number",
                value=90.33,
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={'shape': "angular",
                       'axis': {'range': [0, 100], 'visible': False},
                       'bar': {'color': "#f59e0b", 'thickness': 0.6},
                       'bgcolor': "white",
                       'borderwidth': 2,
                       'bordercolor': "#2c5bac"},
                number={'valueformat': ".2f", 'suffix': "%", 'font': {'size': 20, 'color': 'black', 'family': 'Arial, sans-serif', 'weight': 'bold'}}
            ))
            fig_score.update_layout(
                height=150,
                width=130,
                margin=dict(l=5, r=5, t=20, b=10),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )
            st.plotly_chart(fig_score)

    st.markdown("</div>", unsafe_allow_html=True)