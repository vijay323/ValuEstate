from flask import Flask, render_template, request, redirect, url_for
from flask import session
import joblib
import pandas as pd
from datetime import datetime
import sqlite3
from werkzeug.utils import secure_filename
import os
import matplotlib.pyplot as plt
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

def investment_score(listed_price, predicted_price):
    listed_price = float(listed_price)
    predicted_price = float(predicted_price)
    if predicted_price <= 0:
        return 50
    diff_ratio = (predicted_price - listed_price) / predicted_price  # +ve means underpriced
    score = 50 + (diff_ratio * 200)  # 10% underpriced => +20
    if score < 0:
        score = 0
    if score > 100:
        score = 100
    return int(round(score))

def deal_rating(listed_price, predicted_price):
    listed_price = float(listed_price)
    predicted_price = float(predicted_price)
    if predicted_price <= 0:
        return "Fair"
    ratio = listed_price / predicted_price
    if ratio <= 0.90:
        return "Excellent"
    if ratio <= 0.97:
        return "Good"
    if ratio <= 1.10:
        return "Fair"
    return "Overpriced"

def deal_class(rating):
    return {
        "Excellent": "deal-excellent",
        "Good": "deal-good",
        "Fair": "deal-fair",
        "Overpriced": "deal-overpriced"
    }.get(rating, "deal-fair")

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def risk_meter(listed_price, predicted_price, sqft, bhk, bath):
    listed_price = float(listed_price)
    predicted_price = float(predicted_price) if float(predicted_price) > 0 else listed_price
    sqft = float(sqft)
    bhk = int(bhk)
    bath = int(bath)

    ratio = listed_price / predicted_price if predicted_price > 0 else 1.0
    risk = 0

    if ratio > 1.20:
        risk += 45
    elif ratio > 1.10:
        risk += 30
    elif ratio < 0.85:
        risk += 18

    if sqft <= 0:
        risk += 20
    else:
        sqft_per_bhk = sqft / max(1, bhk)
        if sqft_per_bhk < 300:
            risk += 20
        elif sqft_per_bhk < 400:
            risk += 12

    if bath > bhk + 2:
        risk += 12

    return int(clamp(risk, 0, 100))

def risk_label(risk):
    if risk <= 20:
        return ("Low", "risk-low")
    if risk <= 50:
        return ("Medium", "risk-med")
    return ("High", "risk-high")

def anomaly_flags(listed_price, predicted_price, sqft, bhk, bath):
    listed_price = float(listed_price)
    predicted_price = float(predicted_price) if float(predicted_price) > 0 else listed_price
    sqft = float(sqft)
    bhk = int(bhk)
    bath = int(bath)

    flags = []
    ratio = listed_price / predicted_price if predicted_price > 0 else 1.0

    if ratio > 1.25:
        flags.append("Significantly above AI fair value")
    if ratio < 0.80:
        flags.append("Unusually below AI fair value")
    if sqft > 0 and (sqft / max(1, bhk)) < 300:
        flags.append("Low area per bedroom")
    if bath > bhk + 2:
        flags.append("Unusual bath count vs BHK")

    return flags[:3]

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

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    q = request.args.get("q", "").strip()
    q_location = request.args.get("location", "").strip()
    q_bhk = request.args.get("bhk", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort", "new")
    page = int(request.args.get("page", 1))
    per_page = 9
    offset = (page - 1) * per_page

    sql = "SELECT * FROM properties WHERE 1=1"
    params = []

    if q:
        sql += " AND location LIKE ?"
        params.append(f"%{q}%")

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

    count_sql = "SELECT COUNT(*) FROM (" + sql + ")"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)

    if sort_by == "price_asc":
        sql += " ORDER BY listed_price ASC"
    elif sort_by == "price_desc":
        sql += " ORDER BY listed_price DESC"
    else:
        sql += " ORDER BY id DESC"

    sql += " LIMIT ? OFFSET ?"
    params2 = params + [per_page, offset]

    cursor.execute(sql, params2)
    db_properties = cursor.fetchall()

    analyzed_properties = []
    for p in db_properties:
        predicted_price = predict_price(p["location"], p["sqft"], p["bath"], p["bhk"])
        rec = price_recommendation(p["listed_price"], predicted_price)
        rating = deal_rating(p["listed_price"], predicted_price)
        score = investment_score(p["listed_price"], predicted_price)
        dclass = deal_class(rating)
        low = round(predicted_price * 0.92, 2)
        high = round(predicted_price * 1.08, 2)

        analyzed_properties.append({
            "id": p["id"],
            "location": p["location"],
            "sqft": p["sqft"],
            "bath": p["bath"],
            "bhk": p["bhk"],
            "listed_price": p["listed_price"],
            "image": p["image"],
            "predicted_price": round(predicted_price, 2),
            "recommendation": rec,
            "deal_rating": rating,
            "deal_class": dclass,
            "investment_score": score,
            "fair_low": low,
            "fair_high": high
        })

    cursor.execute("SELECT DISTINCT location FROM properties ORDER BY location")
    locations = [r["location"] for r in cursor.fetchall()]

    conn.close()

    return render_template(
        "home.html",
        result=result,
        recommendation=recommendation,
        properties=analyzed_properties,
        locations=locations,
        q=q,
        q_location=q_location,
        q_bhk=q_bhk,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages
    )



@app.route("/property/<int:pid>", methods=["GET", "POST"])
def property(pid):
    success = None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM properties WHERE id = ?", (pid,))
    p = cur.fetchone()
    if p is None:
        conn.close()
        return "Property not found", 404

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        message = request.form["message"]

        cur.execute("""
            INSERT INTO inquiries (property_id, name, phone, message)
            VALUES (?, ?, ?, ?)
        """, (pid, name, phone, message))
        conn.commit()
        success = "Inquiry sent successfully!"

    cur.execute("""
        SELECT old_price, new_price, changed_at
        FROM price_history
        WHERE property_id = ?
        ORDER BY id ASC
    """, (pid,))
    hist = cur.fetchall()

    labels = []
    series = []

    if not hist:
        labels = ["Current"]
        series = [float(p["listed_price"])]
    else:
        labels.append("Initial")
        series.append(float(hist[0]["old_price"]))
        for h in hist:
            labels.append(h["changed_at"])
            series.append(float(h["new_price"]))

    predicted_price = predict_price(p["location"], p["sqft"], p["bath"], p["bhk"])
    rec = price_recommendation(p["listed_price"], predicted_price)

    rating = deal_rating(p["listed_price"], predicted_price)
    score = investment_score(p["listed_price"], predicted_price)
    dclass = deal_class(rating)
    risk = risk_meter(p["listed_price"], predicted_price, p["sqft"], p["bhk"], p["bath"])
    risk_text, risk_class = risk_label(risk)
    flags = anomaly_flags(p["listed_price"], predicted_price, p["sqft"], p["bhk"], p["bath"])

    property_data = {
        "id": p["id"],
        "location": p["location"],
        "sqft": p["sqft"],
        "bath": p["bath"],
        "bhk": p["bhk"],
        "listed_price": p["listed_price"],
        "image": p["image"],
        "predicted_price": round(predicted_price, 2),
        "recommendation": rec,
        "deal_rating": rating,
        "deal_class": dclass,
        "investment_score": score,
        "risk_score": risk,
        "risk_text": risk_text,
        "risk_class": risk_class,
        "flags": flags
    }

    conn.close()

    return render_template("property.html", p=property_data, success=success, labels=labels, series=series)
    

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

@app.route("/analytics")
def analytics():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT location, listed_price FROM properties")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "No data available"

    import pandas as pd
    import matplotlib.pyplot as plt
    import os

    df = pd.DataFrame(rows, columns=["location", "price"])

    # Create folder for charts
    charts_dir = os.path.join(BASE_DIR, "static", "charts")
    os.makedirs(charts_dir, exist_ok=True)

    # 1️⃣ Average Price by Location
    avg_price = df.groupby("location")["price"].mean().sort_values(ascending=False).head(10)

    plt.figure(figsize=(10,6))
    avg_price.plot(kind="bar")
    plt.title("Top 10 Locations by Average Property Price")
    plt.xlabel("Location")
    plt.ylabel("Average Price (Lakhs)")
    plt.xticks(rotation=45)

    chart_path = os.path.join(charts_dir, "location_price.png")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    # 2️⃣ Price Distribution Graph
    plt.figure(figsize=(8,5))
    df["price"].hist(bins=15)
    plt.title("Property Price Distribution")
    plt.xlabel("Price (Lakhs)")
    plt.ylabel("Number of Properties")

    hist_path = os.path.join(charts_dir, "price_distribution.png")
    plt.tight_layout()
    plt.savefig(hist_path)
    plt.close()

    return render_template("analytics.html")

@app.route("/add", methods=["GET", "POST"])
def add_property():
    msg = None

    if request.method == "POST":
        location = request.form["location"]
        sqft = float(request.form["sqft"])
        bath = int(request.form["bath"])
        bhk = int(request.form["bhk"])
        listed_price = float(request.form["listed_price"])

        image_file = request.files.get("image")
        filename = None

        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO properties (location, sqft, bath, bhk, listed_price, image)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (location, sqft, bath, bhk, listed_price, filename))
        conn.commit()
        conn.close()

        msg = "✅ Property posted successfully!"

    # ✅ Get locations from model columns first
    locations = sorted([c.replace("site_location_", "") for c in columns if c.startswith("site_location_")])

    # ✅ Fallback: if for any reason model columns are empty, use DB distinct locations
    if not locations:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT location FROM properties ORDER BY location")
        locations = [r["location"] for r in cur.fetchall()]
        conn.close()

    return render_template("add.html", msg=msg, locations=locations)

@app.route("/admin/inquiries")
def admin_inquiries():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            i.id AS inquiry_id,
            i.property_id,
            i.name,
            i.phone,
            i.message,
            p.location,
            p.sqft,
            p.bhk,
            p.bath,
            p.listed_price
        FROM inquiries i
        JOIN properties p ON p.id = i.property_id
        ORDER BY i.id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    inquiries = []
    for r in rows:
        inquiries.append({
            "inquiry_id": r["inquiry_id"],
            "property_id": r["property_id"],
            "name": r["name"],
            "phone": r["phone"],
            "message": r["message"],
            "location": r["location"],
            "sqft": r["sqft"],
            "bhk": r["bhk"],
            "bath": r["bath"],
            "listed_price": r["listed_price"]
        })

    return render_template("admin_inquiries.html", inquiries=inquiries)

@app.route("/property/<int:pid>/update_price", methods=["POST"])
def update_price(pid):
    new_price = float(request.form["new_price"])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT listed_price FROM properties WHERE id = ?", (pid,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return "Property not found", 404

    old_price = float(row["listed_price"])

    if new_price != old_price:
        cur.execute("UPDATE properties SET listed_price = ? WHERE id = ?", (new_price, pid))
        cur.execute("""
            INSERT INTO price_history (property_id, old_price, new_price, changed_at)
            VALUES (?, ?, ?, ?)
        """, (pid, old_price, new_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    conn.close()
    return redirect(f"/property/{pid}")

if __name__ == "__main__":
    app.run(debug=True)
