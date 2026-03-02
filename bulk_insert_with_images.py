import sqlite3
import random
import joblib
import pandas as pd

# Load model + columns (same as your app)
model = joblib.load("model/pune_house_price_model.pkl")
columns = joblib.load("model/model_columns.pkl")

def predict_price(location, sqft, bath, bhk):
    x = pd.DataFrame(columns=columns)
    x.loc[0] = 0
    x.loc[0, "total_sqft"] = sqft
    x.loc[0, "bath"] = bath
    x.loc[0, "bhk"] = bhk

    loc_col = "site_location_" + location
    if loc_col in columns:
        x.loc[0, loc_col] = 1

    return float(model.predict(x)[0])

locations = sorted([c.replace("site_location_", "") for c in columns if c.startswith("site_location_")])

# Different images
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
    "https://images.unsplash.com/photo-1600607687644-c7171b42498f"
]

# Target distribution
# 50% Fair (within +-8%), 25% Under (10-20% low), 25% Over (10-20% high)
def make_listed_price(pred, bucket):
    if pred <= 0:
        return round(random.uniform(40, 120), 2)

    if bucket == "fair":
        mult = random.uniform(0.92, 1.08)   # within fair range
    elif bucket == "under":
        mult = random.uniform(0.80, 0.90)   # underpriced
    else:  # "over"
        mult = random.uniform(1.10, 1.25)   # overpriced

    return round(pred * mult, 2)

conn = sqlite3.connect("database.db")
cur = conn.cursor()

N = 60  # change count
for i in range(N):
    location = random.choice(locations)
    bhk = random.randint(1, 4)
    bath = random.randint(1, bhk + 1)
    sqft = random.randint(600, 2600)

    pred = predict_price(location, sqft, bath, bhk)

    r = random.random()
    if r < 0.50:
        bucket = "fair"
    elif r < 0.75:
        bucket = "under"
    else:
        bucket = "over"

    listed_price = make_listed_price(pred, bucket)
    image = random.choice(images)

    cur.execute("""
        INSERT INTO properties (location, sqft, bath, bhk, listed_price, image)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (location, sqft, bath, bhk, listed_price, image))

conn.commit()
conn.close()

print("✅ Balanced properties inserted with Fair/Under/Over mix!")