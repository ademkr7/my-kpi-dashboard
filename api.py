from flask import Flask, jsonify, request
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect("kpi_database.db")
    c = conn.cursor()
    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS kpis
                 (kpi_name TEXT, rate REAL, target REAL, poids REAL, obj REAL, real REAL, score REAL, timestamp TEXT)''')
    # Check if score column exists, add if missing
    c.execute("PRAGMA table_info(kpis)")
    columns = [info[1] for info in c.fetchall()]
    if 'score' not in columns:
        c.execute("ALTER TABLE kpis ADD COLUMN score REAL")
    conn.commit()
    return conn

# Initialize database with JSON data
def load_initial_data(json_file):
    if not os.path.exists(json_file):
        print(f"Error: JSON file not found at {json_file}")
        return False
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        df = df.dropna(subset=["poids"])
        # Convert numeric columns
        df["Taux de réalisation"] = pd.to_numeric(df["Taux de réalisation"], errors="coerce") * 100
        df["OBJECTIF 2025"] = pd.to_numeric(df["OBJECTIF 2025"], errors="coerce")
        df["Réalisation 2025"] = pd.to_numeric(df["Réalisation 2025"], errors="coerce")
        df["poids"] = pd.to_numeric(df["poids"], errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        
        # Handle missing Objectifs by using Column2 and Column3
        df["Objectifs"] = df.apply(
            lambda row: f"{row['Column2'] if pd.notna(row.get('Column2')) else 'Unknown'} - {row['Column3'] if pd.notna(row.get('Column3')) else 'Unknown'}" 
            if pd.isna(row.get("Objectifs")) else row["Objectifs"], axis=1
        )
        
        required_columns = ["Objectifs", "Taux de réalisation", "OBJECTIF 2025", "poids", "Réalisation 2025", "score"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Error: Missing required columns in JSON: {', '.join(missing_columns)}")
            return False

        conn = init_db()
        c = conn.cursor()
        c.execute("DELETE FROM kpis")  # Clear existing data
        for _, row in df.iterrows():
            if pd.notna(row["Objectifs"]):
                c.execute("INSERT INTO kpis (kpi_name, rate, target, poids, obj, real, score, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (row["Objectifs"], row["Taux de réalisation"], row["OBJECTIF 2025"], row["poids"],
                           row["OBJECTIF 2025"], row["Réalisation 2025"], row["score"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        print(f"Loaded {len(df)} records from {json_file} into database")
        return True
    except Exception as e:
        print(f"Error loading JSON data: {str(e)}")
        return False

# Load initial data from JSON file
json_file = os.path.join(os.path.dirname(__file__), "kpi_data.json")
if os.path.exists(json_file):
    load_initial_data(json_file)
else:
    print(f"Warning: JSON file not found at {json_file}. API will rely on existing database data.")

# API Endpoints
@app.route('/api/kpis', methods=['GET'])
def get_kpis():
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT kpi_name, rate, target, poids, obj, real, score FROM kpis ORDER BY timestamp DESC LIMIT 16")
    data = c.fetchall()
    conn.close()
    return jsonify([{
        "kpi_name": row[0],
        "rate": row[1],
        "target": row[2],
        "poids": row[3],
        "obj": row[4],
        "real": row[5],
        "score": row[6]
    } for row in data])

@app.route('/api/kpis', methods=['POST'])
def update_kpis():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"error": "Invalid data format, expected a list of KPI records"}), 400
    
    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM kpis")  # Replace all data (adjust as needed for incremental updates)
    for item in data:
        c.execute("INSERT INTO kpis (kpi_name, rate, target, poids, obj, real, score, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (item.get("kpi_name"), item.get("rate"), item.get("target"), item.get("poids"),
                   item.get("obj"), item.get("real"), item.get("score"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"message": "KPI data updated successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8501)