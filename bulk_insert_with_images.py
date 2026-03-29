import os
import random
import sqlite3

import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "model", "pune_house_price_model.pkl")
COLUMNS_PATH = os.path.join(BASE_DIR, "model", "model_columns.pkl")

model = joblib.load(MODEL_PATH)
columns = joblib.load(COLUMNS_PATH)
locations = sorted(col.replace("site_location_", "") for col in columns if col.startswith("site_location_"))

images = [
    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c",
    "https://images.unsplash.com/photo-1605276374104-dee2a0ed3cd6",
    "https://images.unsplash.com/photo-1570129477492-45c003edd2be",
    "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c",
    "https://images.unsplash.com/photo-1599423300746-b62533397364",
    "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde",
    "https://images.unsplash.com/photo-1605146768851-eda79da39897",
    "https://images.unsplash.com/photo-1600607687644-c7171b42498f",
]


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


def make_listed_price(predicted_price, bucket):
    if predicted_price <= 0:
        return round(random.uniform(40, 120), 2)

    if bucket == "fair":
        multiplier = random.uniform(0.92, 1.08)
    elif bucket == "under":
        multiplier = random.uniform(0.80, 0.90)
    else:
        multiplier = random.uniform(1.10, 1.25)

    return round(predicted_price * multiplier, 2)


def seed_properties(total_properties=60, clear_existing=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if clear_existing:
        cur.execute("DELETE FROM properties")

    for _ in range(total_properties):
        location = random.choice(locations)
        bhk = random.randint(1, 4)
        bath = random.randint(1, bhk + 1)
        sqft = random.randint(600, 2600)

        predicted_price = predict_price(location, sqft, bath, bhk)
        rand = random.random()
        if rand < 0.50:
            bucket = "fair"
        elif rand < 0.75:
            bucket = "under"
        else:
            bucket = "over"

        listed_price = make_listed_price(predicted_price, bucket)
        image = random.choice(images)

        cur.execute(
            """
            INSERT INTO properties (location, sqft, bath, bhk, listed_price, image)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (location, sqft, bath, bhk, listed_price, image),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed_properties(total_properties=60, clear_existing=False)
    print("✅ 60 balanced properties with images inserted successfully!")
