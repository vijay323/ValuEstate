from flask import Flask, render_template, request
import joblib
import pandas as pd
import sqlite3
import os
import matplotlib.pyplot as plt
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)

# Load model
model = joblib.load("model/pune_house_price_model.pkl")
columns = joblib.load("model/model_columns.pkl")

def predict_price(location, sqft, bath, bhk):
    x = pd.DataFrame(columns=columns)
    x.loc[0] = 0
    
    x.loc[0, 'total_sqft'] = sqft
    x.loc[0, 'bath'] = bath
    x.loc[0, 'bhk'] = bhk
    
    loc_col = "site_location_" + location
    if loc_col in columns:
        x.loc[0, loc_col] = 1
    
    return model.predict(x)[0]

def price_recommendation(listed_price, predicted_price):
    difference = listed_price - predicted_price
    percentage_diff = (difference / predicted_price) * 100
    
    if percentage_diff < -10:
        return "Underpriced"
    elif percentage_diff > 10:
        return "Overpriced"
    else:
        return "Fairly Priced"

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    recommendation = None

    if request.method == "POST":
        location = request.form["location"]
        sqft = float(request.form["sqft"])
        bath = int(request.form["bath"])
        bhk = int(request.form["bhk"])
        listed_price = float(request.form["listed_price"])

        predicted_price = predict_price(location, sqft, bath, bhk)
        result = round(predicted_price, 2)
        recommendation = price_recommendation(listed_price, predicted_price)

    # Connect DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ---- Filters (GET params) ----
    q_location = request.args.get("location", "").strip()
    q_bhk = request.args.get("bhk", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort", "new")

    sql = "SELECT * FROM properties WHERE 1=1"
    params = []

    if q_location:
        sql += " AND location = ?"
        params.append(q_location)

    if q_bhk:
        sql += " AND bhk = ?"
        params.append(int(q_bhk))

    if min_price:
        sql += " AND listed_price >= ?"
        params.append(float(min_price))

    if max_price:
        sql += " AND listed_price <= ?"
        params.append(float(max_price))

    if sort_by == "price_asc":
        sql += " ORDER BY listed_price ASC"
    elif sort_by == "price_desc":
        sql += " ORDER BY listed_price DESC"
    else:
        sql += " ORDER BY id DESC"

    cursor.execute(sql, params)
    db_properties = cursor.fetchall()
    conn.close()

    # AI Analysis for each property
    analyzed_properties = []
    for p in db_properties:
        predicted_price = predict_price(p["location"], p["sqft"], p["bath"], p["bhk"])
        rec = price_recommendation(p["listed_price"], predicted_price)

        analyzed_properties.append({
    "id": p["id"],   # ⭐ ADD THIS LINE
    "location": p["location"],
    "sqft": p["sqft"],
    "bath": p["bath"],
    "bhk": p["bhk"],
    "listed_price": p["listed_price"],
    "predicted_price": round(predicted_price, 2),
    "recommendation": rec
})
            
        

    locations = sorted(set([p["location"] for p in db_properties]))

    return render_template(
        "home.html",
        result=result,
        recommendation=recommendation,
        properties=analyzed_properties,
        locations=locations,
        q_location=q_location,
        q_bhk=q_bhk,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by
    )

@app.route("/property/<int:pid>")
def property_detail(pid):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM properties WHERE id = ?", (pid,))
    p = cur.fetchone()
    conn.close()

    if p is None:
        return "Property not found", 404

    predicted_price = predict_price(p["location"], p["sqft"], p["bath"], p["bhk"])
    rec = price_recommendation(p["listed_price"], predicted_price)

    property_data = {
        "id": p["id"],
        "location": p["location"],
        "sqft": p["sqft"],
        "bath": p["bath"],
        "bhk": p["bhk"],
        "listed_price": p["listed_price"],
        "predicted_price": round(predicted_price, 2),
        "recommendation": rec
    }

    return render_template("property.html", p=property_data)

@app.route("/dashboard")
def dashboard():
    charts_dir = os.path.join(BASE_DIR, "static", "charts")
    os.makedirs(charts_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM properties")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "No properties found in database", 404

    data = []
    for r in rows:
        pred = predict_price(r["location"], r["sqft"], r["bath"], r["bhk"])
        rec = price_recommendation(r["listed_price"], pred)
        data.append({
            "location": r["location"],
            "bhk": r["bhk"],
            "listed_price": float(r["listed_price"]),
            "recommendation": rec
        })

    df_dash = pd.DataFrame(data)

    # 1) Top 10 locations by avg listed price
    loc_avg = df_dash.groupby("location")["listed_price"].mean().sort_values(ascending=False).head(10)
    plt.figure()
    loc_avg.sort_values().plot(kind="barh")
    plt.xlabel("Avg Listed Price (Lakhs)")
    plt.ylabel("Location")
    plt.title("Top 10 Locations by Avg Listed Price")
    chart1 = os.path.join(charts_dir, "loc_avg.png")
    plt.tight_layout()
    plt.savefig(chart1)
    plt.close()

    # 2) BHK vs avg listed price
    bhk_avg = df_dash.groupby("bhk")["listed_price"].mean().sort_index()
    plt.figure()
    bhk_avg.plot(kind="bar")
    plt.xlabel("BHK")
    plt.ylabel("Avg Listed Price (Lakhs)")
    plt.title("BHK vs Avg Listed Price")
    chart2 = os.path.join(charts_dir, "bhk_avg.png")
    plt.tight_layout()
    plt.savefig(chart2)
    plt.close()

    # 3) Recommendation counts
    rec_counts = df_dash["recommendation"].value_counts()
    plt.figure()
    rec_counts.plot(kind="bar")
    plt.xlabel("Recommendation")
    plt.ylabel("Count")
    plt.title("AI Recommendation Distribution")
    chart3 = os.path.join(charts_dir, "rec_counts.png")
    plt.tight_layout()
    plt.savefig(chart3)
    plt.close()

    # cache-buster so browser updates images
    ver = str(int(__import__("time").time()))

    return render_template(
        "dashboard.html",
        ver=ver,
        total=len(df_dash),
        under=int(rec_counts.get("Underpriced", 0)),
        fair=int(rec_counts.get("Fairly Priced", 0)),
        over=int(rec_counts.get("Overpriced", 0))
    )


if __name__ == "__main__":
    app.run(debug=True)
