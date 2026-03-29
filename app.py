from datetime import datetime
import os
import sqlite3
from functools import wraps

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from flask import Flask, redirect, render_template, request, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "model", "pune_house_price_model.pkl")
COLUMNS_PATH = os.path.join(BASE_DIR, "model", "model_columns.pkl")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
CHARTS_FOLDER = os.path.join(BASE_DIR, "static", "charts")
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2"

app = Flask(__name__)
app.secret_key = "valuestate_super_secret_key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)

model = joblib.load(MODEL_PATH)
columns = joblib.load(COLUMNS_PATH)
MODEL_LOCATIONS = sorted(
    col.replace("site_location_", "")
    for col in columns
    if col.startswith("site_location_")
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def current_user():
    if "user_id" not in session:
        return None
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user


def predict_price(location, sqft, bath, bhk):
    x = pd.DataFrame(columns=columns)
    x.loc[0] = 0
    x.loc[0, "total_sqft"] = float(sqft)
    x.loc[0, "bath"] = int(bath)
    x.loc[0, "bhk"] = int(bhk)

    loc_col = f"site_location_{location}"
    if loc_col in columns:
        x.loc[0, loc_col] = 1

    return float(model.predict(x)[0])


def price_recommendation(listed_price, predicted_price):
    if predicted_price <= 0:
        return "Fair"

    percentage_diff = ((float(listed_price) - float(predicted_price)) / float(predicted_price)) * 100
    if percentage_diff < -10:
        return "Underpriced"
    if percentage_diff > 10:
        return "Overpriced"
    return "Fair"


def investment_score(listed_price, predicted_price):
    listed_price = float(listed_price)
    predicted_price = float(predicted_price)
    if predicted_price <= 0:
        return 50

    diff_ratio = (predicted_price - listed_price) / predicted_price
    score = 50 + (diff_ratio * 200)
    return int(round(max(0, min(100, score))))


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
    return "Poor"


def deal_class(rating):
    return {
        "Excellent": "deal-excellent",
        "Good": "deal-good",
        "Fair": "deal-fair",
        "Poor": "deal-poor",
    }.get(rating, "deal-fair")


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


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
        return "Low", "risk-low"
    if risk <= 50:
        return "Medium", "risk-med"
    return "High", "risk-high"


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




def decision_summary(category, rating, risk_text):
    return f"{category} property with {rating.lower()} investment potential and {risk_text.lower()} risk."

def resolve_image_path(image_value):
    if not image_value:
        return DEFAULT_IMAGE
    if str(image_value).startswith("http"):
        return image_value
    return f"/static/uploads/{image_value}"


def analyze_property(row):
    predicted_price = predict_price(row["location"], row["sqft"], row["bath"], row["bhk"])
    price_category = price_recommendation(row["listed_price"], predicted_price)
    rating = deal_rating(row["listed_price"], predicted_price)
    score = investment_score(row["listed_price"], predicted_price)
    risk = risk_meter(row["listed_price"], predicted_price, row["sqft"], row["bhk"], row["bath"])
    risk_text, risk_class = risk_label(risk)
    summary = decision_summary(price_category, rating, risk_text)

    return {
        "id": row["id"],
        "location": row["location"],
        "sqft": row["sqft"],
        "bath": row["bath"],
        "bhk": row["bhk"],
        "listed_price": row["listed_price"],
        "image": row["image"],
        "image_src": resolve_image_path(row["image"]),
        "predicted_price": round(predicted_price, 2),
        "recommendation": price_category,
        "price_category": price_category,
        "deal_rating": rating,
        "deal_class": deal_class(rating),
        "investment_score": score,
        "ai_fair_value_low": round(predicted_price * 0.92, 2),
        "ai_fair_value_high": round(predicted_price * 1.08, 2),
        "fair_low": round(predicted_price * 0.92, 2),
        "fair_high": round(predicted_price * 1.08, 2),
        "risk_score": risk,
        "risk_text": risk_text,
        "risk_class": risk_class,
        "decision_summary": summary,
        "flags": anomaly_flags(row["listed_price"], predicted_price, row["sqft"], row["bhk"], row["bath"]),
    }

def get_property_ai_response(question, property_data):
    q = question.lower().strip()

    location = property_data["location"]
    bhk = property_data["bhk"]
    sqft = property_data["sqft"]
    listed_price = property_data["listed_price"]

    analyzed = analyze_property(property_data)
    predicted_price = analyzed["predicted_price"]
    recommendation = analyzed["recommendation"]

    if "overpriced" in q:
        if recommendation == "Overpriced":
            return f"Yes, this property appears overpriced. The listed price is ₹{listed_price:.2f} lakh, while the estimated AI price is around ₹{predicted_price:.2f} lakh."
        return f"No, this property is not overpriced according to the AI analysis. It is classified as {recommendation}."

    elif "underpriced" in q:
        if recommendation == "Underpriced":
            return f"Yes, this property appears underpriced. The listed price is ₹{listed_price:.2f} lakh, while the estimated AI price is around ₹{predicted_price:.2f} lakh."
        return f"No, this property is not underpriced. It is classified as {recommendation}."

    elif "fair price" in q or "fair" in q:
        if recommendation == "Fair Price":
            return f"This property is close to the AI-estimated value, so it is considered fairly priced."
        return f"This property is not in the fair price range. It is currently marked as {recommendation}."

    elif "buy" in q or "should i buy" in q:
        if recommendation == "Underpriced":
            return f"This may be a good buying opportunity because the property is underpriced compared to the AI estimate."
        elif recommendation == "Fair Price":
            return f"This property looks reasonably priced. If the location, condition, and amenities are good, it may be a sensible purchase."
        else:
            return f"You should be careful. This property looks overpriced compared to the AI-estimated value."

    elif "investment" in q:
        if recommendation == "Underpriced":
            return f"This property may be a strong investment option because it is priced below the estimated value."
        elif recommendation == "Fair Price":
            return f"This property could be a moderate investment choice if the location has good demand and growth potential."
        else:
            return f"This property may not be the best investment right now because it seems overpriced."

    elif "why" in q:
        return (
            f"The AI compares the listed price of this {bhk} BHK property in {location} "
            f"with its predicted market value based on features like location, BHK, bathrooms, and area. "
            f"Here, the listed price is ₹{listed_price:.2f} lakh and the predicted value is ₹{predicted_price:.2f} lakh, "
            f"so the result is {recommendation}."
        )

    elif "location" in q:
        return f"This property is located in {location}. Location plays a major role in the AI-estimated price."

    elif "summary" in q or "explain" in q:
        return (
            f"This is a {bhk} BHK property in {location} with {sqft} sqft area. "
            f"Its listed price is ₹{listed_price:.2f} lakh, while the AI-estimated price is ₹{predicted_price:.2f} lakh. "
            f"So the system classifies it as {recommendation}."
        )

    else:
        return (
            f"This property is a {bhk} BHK home in {location} with {sqft} sqft area. "
            f"It is listed at ₹{listed_price:.2f} lakh, and the AI-estimated price is ₹{predicted_price:.2f} lakh. "
            f"According to the analysis, it is {recommendation}."
        )

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)

        conn = get_connection()
        existing_user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if existing_user:
            conn.close()
            flash("Email already registered. Please login.")
            return redirect(url_for("login"))

        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password),
        )
        conn.commit()
        conn.close()

        flash("Signup successful. Please login.")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Login successful.")
            return redirect(url_for("home"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("home"))

@app.route("/", methods=["GET", "POST"])
def home():
    analysis = None

    if request.method == "POST":
        location = request.form["location"]
        sqft = float(request.form["sqft"])
        bath = int(request.form["bath"])
        bhk = int(request.form["bhk"])
        listed_price = float(request.form["listed_price"])

        analysis = analyze_property(
            {
                "id": 0,
                "location": location,
                "sqft": sqft,
                "bath": bath,
                "bhk": bhk,
                "listed_price": listed_price,
                "image": None,
            }
        )

    conn = get_connection()
    cursor = conn.cursor()

    q = request.args.get("q", "").strip()
    q_location = request.args.get("location", "").strip()
    q_bhk = request.args.get("bhk", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort", "new")
    page = max(1, int(request.args.get("page", 1)))
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

    count_sql = f"SELECT COUNT(*) FROM ({sql})"
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
    cursor.execute(sql, params + [per_page, offset])
    properties = [analyze_property(row) for row in cursor.fetchall()]

    locations = MODEL_LOCATIONS or [r["location"] for r in cursor.execute("SELECT DISTINCT location FROM properties ORDER BY location")]
    conn.close()

    return render_template(
        "home.html",
        analysis=analysis,
        properties=properties,
        locations=locations,
        q=q,
        q_location=q_location,
        q_bhk=q_bhk,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        total_pages=total_pages,
        user=current_user(),
    )

@app.route("/my_listings")
@login_required
def my_listings():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM properties WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    properties = [analyze_property(row) for row in rows]
    return render_template("my_listings.html", properties=properties)

@app.route("/property/<int:pid>", methods=["GET", "POST"])
def property(pid):
    success = None
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
    """
    SELECT p.*, u.name AS owner_name, u.email AS owner_email
    FROM properties p
    LEFT JOIN users u ON p.user_id = u.id
    WHERE p.id = ?
    """,
    (pid,),
)
    row = cur.fetchone()
    if row is None:
        conn.close()
        return "Property not found", 404

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        message = request.form["message"]
        cur.execute(
            """
            INSERT INTO inquiries (property_id, name, phone, message)
            VALUES (?, ?, ?, ?)
            """,
            (pid, name, phone, message),
        )
        conn.commit()
        success = "Inquiry sent successfully!"

    cur.execute(
        """
        SELECT old_price, new_price, changed_at
        FROM price_history
        WHERE property_id = ?
        ORDER BY id ASC
        """,
        (pid,),
    )
    history = cur.fetchall()

    if not history:
        labels = ["Current"]
        series = [float(row["listed_price"])]
    else:
        labels = ["Initial"] + [h["changed_at"] for h in history]
        series = [float(history[0]["old_price"])] + [float(h["new_price"])]

    property_data = analyze_property(row)
    conn.close()
    return render_template(
    "property.html",
    p=property_data,
    success=success,
    labels=labels,
    series=series,
    owner_name=row["owner_name"],
    owner_email=row["owner_email"]
)


@app.route("/dashboard")
def dashboard():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM properties").fetchall()
    conn.close()

    if not rows:
        return "No properties found in database", 404

    data = []
    for row in rows:
        predicted = predict_price(row["location"], row["sqft"], row["bath"], row["bhk"])
        data.append(
            {
                "location": row["location"],
                "bhk": row["bhk"],
                "listed_price": float(row["listed_price"]),
                "recommendation": price_recommendation(row["listed_price"], predicted),
            }
        )

    df = pd.DataFrame(data)

    loc_avg = df.groupby("location")["listed_price"].mean().sort_values(ascending=False).head(10)
    plt.figure()
    loc_avg.sort_values().plot(kind="barh")
    plt.xlabel("Avg Listed Price (Lakhs)")
    plt.ylabel("Location")
    plt.title("Top 10 Locations by Avg Listed Price")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "loc_avg.png"))
    plt.close()

    bhk_avg = df.groupby("bhk")["listed_price"].mean().sort_index()
    plt.figure()
    bhk_avg.plot(kind="bar")
    plt.xlabel("BHK")
    plt.ylabel("Avg Listed Price (Lakhs)")
    plt.title("BHK vs Avg Listed Price")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "bhk_avg.png"))
    plt.close()

    rec_counts = df["recommendation"].value_counts()
    plt.figure()
    rec_counts.plot(kind="bar")
    plt.xlabel("Recommendation")
    plt.ylabel("Count")
    plt.title("AI Recommendation Distribution")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "rec_counts.png"))
    plt.close()

    ver = str(int(__import__("time").time()))
    return render_template(
        "dashboard.html",
        ver=ver,
        total=len(df),
        under=int(rec_counts.get("Underpriced", 0)),
        fair=int(rec_counts.get("Fair", 0)),
        over=int(rec_counts.get("Overpriced", 0)),
    )


@app.route("/analytics")
def analytics():
    conn = get_connection()
    rows = conn.execute("SELECT location, listed_price FROM properties").fetchall()
    conn.close()

    if not rows:
        return "No data available"

    df = pd.DataFrame(rows, columns=["location", "price"])

    avg_price = df.groupby("location")["price"].mean().sort_values(ascending=False).head(10)
    plt.figure(figsize=(10, 6))
    avg_price.plot(kind="bar")
    plt.title("Top 10 Locations by Average Property Price")
    plt.xlabel("Location")
    plt.ylabel("Average Price (Lakhs)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "location_price.png"))
    plt.close()

    plt.figure(figsize=(8, 5))
    df["price"].hist(bins=15)
    plt.title("Property Price Distribution")
    plt.xlabel("Price (Lakhs)")
    plt.ylabel("Number of Properties")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "price_distribution.png"))
    plt.close()

    return render_template("analytics.html")


@app.route("/add", methods=["GET", "POST"])
@login_required
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
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = get_connection()
        conn.execute(
            """
            INSERT INTO properties (user_id, location, sqft, bath, bhk, listed_price, image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session["user_id"], location, sqft, bath, bhk, listed_price, filename),
        )
        conn.commit()
        conn.close()
        msg = "✅ Property posted successfully!"

    return render_template("add.html", msg=msg, locations=MODEL_LOCATIONS)

@app.route("/admin/inquiries")
def admin_inquiries():
    conn = get_connection()
    rows = conn.execute(
        """
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
        """
    ).fetchall()
    conn.close()

    inquiries = [dict(row) for row in rows]
    return render_template("admin_inquiries.html", inquiries=inquiries)


@app.route("/property/<int:pid>/update_price", methods=["POST"])
def update_price(pid):
    new_price = float(request.form["new_price"])

    conn = get_connection()
    row = conn.execute("SELECT listed_price FROM properties WHERE id = ?", (pid,)).fetchone()
    if row is None:
        conn.close()
        return "Property not found", 404

    old_price = float(row["listed_price"])
    if new_price != old_price:
        conn.execute("UPDATE properties SET listed_price = ? WHERE id = ?", (new_price, pid))
        conn.execute(
            """
            INSERT INTO price_history (property_id, old_price, new_price, changed_at)
            VALUES (?, ?, ?, ?)
            """,
            (pid, old_price, new_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()

    conn.close()
    return redirect(f"/property/{pid}")

@app.route("/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def edit_property(pid):
    conn = get_connection()

    property_data = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (pid,)
    ).fetchone()

    if not property_data:
        conn.close()
        flash("Property not found.")
        return redirect(url_for("home"))

    if property_data["user_id"] != session["user_id"]:
        conn.close()
        flash("Unauthorized access.")
        return redirect(url_for("home"))

    if request.method == "POST":
        location = request.form["location"]
        sqft = float(request.form["sqft"])
        bath = int(request.form["bath"])
        bhk = int(request.form["bhk"])
        listed_price = float(request.form["listed_price"])

        conn.execute(
            """
            UPDATE properties
            SET location=?, sqft=?, bath=?, bhk=?, listed_price=?
            WHERE id=?
            """,
            (location, sqft, bath, bhk, listed_price, pid),
        )

        conn.commit()
        conn.close()

        flash("Property updated successfully.")
        return redirect(url_for("my_listings"))

    conn.close()
    return render_template("edit.html", p=property_data)

@app.route("/delete/<int:pid>")
@login_required
def delete_property(pid):
    conn = get_connection()

    property_data = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (pid,)
    ).fetchone()

    if not property_data:
        conn.close()
        flash("Property not found.")
        return redirect(url_for("home"))

    if property_data["user_id"] != session["user_id"]:
        conn.close()
        flash("Unauthorized action.")
        return redirect(url_for("home"))

    conn.execute("DELETE FROM properties WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

    flash("Property deleted successfully.")
    return redirect(url_for("my_listings"))

@app.route("/property_ai/<int:pid>", methods=["GET", "POST"])
def property_ai(pid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM properties WHERE id = ?", (pid,)).fetchone()
    conn.close()

    if not row:
        flash("Property not found.")
        return redirect(url_for("home"))

    answer = None
    question = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            answer = get_property_ai_response(question, row)

    analyzed = analyze_property(row)

    return render_template(
        "property_ai.html",
        p=row,
        answer=answer,
        question=question,
        analyzed=analyzed
    )


if __name__ == "__main__":
    app.run(debug=True)
