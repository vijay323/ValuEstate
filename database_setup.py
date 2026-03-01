import sqlite3

DB_PATH = "database.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    sqft REAL NOT NULL,
    bath INTEGER NOT NULL,
    bhk INTEGER NOT NULL,
    listed_price REAL NOT NULL
)
""")

cur.execute("DELETE FROM properties")

properties = [
    ("Aundh", 1200, 2, 2, 75),
    ("Baner", 1500, 3, 3, 120),
    ("Wakad", 1000, 2, 2, 65),
    ("Kothrud", 1800, 3, 3, 140),
    ("Hinjewadi", 900, 2, 2, 55),
    ("Viman Nagar", 1300, 2, 3, 95),
    ("Pimpri", 850, 1, 2, 45),
    ("Kharadi", 1100, 2, 2, 78),
    ("Hadapsar", 1050, 2, 2, 72),
    ("Sinhagad Road", 1250, 2, 3, 88)
]

cur.executemany("""
INSERT INTO properties (location, sqft, bath, bhk, listed_price)
VALUES (?, ?, ?, ?, ?)
""", properties)
cur.execute("ALTER TABLE properties ADD COLUMN image TEXT")
cur.execute("""
CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    name TEXT,
    phone TEXT,
    message TEXT
)
""")
conn.commit()

cur.execute("SELECT COUNT(*) FROM properties")
print("✅ Rows in properties:", cur.fetchone()[0])

conn.close()
print("✅ Database reset + sample properties inserted!")