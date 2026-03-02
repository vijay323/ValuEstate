import sqlite3

DB_PATH = "database.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Properties table (with image included from start)
cur.execute("""
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    sqft REAL NOT NULL,
    bath INTEGER NOT NULL,
    bhk INTEGER NOT NULL,
    listed_price REAL NOT NULL,
    image TEXT
)
""")

# Inquiries table
cur.execute("""
CREATE TABLE IF NOT EXISTS inquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER,
    name TEXT,
    phone TEXT,
    message TEXT
)
""")

# Price history table (for AI tracking - very good feature for your project)
cur.execute("""
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    old_price REAL NOT NULL,
    new_price REAL NOT NULL,
    changed_at TEXT NOT NULL
)
""")

# OPTIONAL: Insert sample data only if table is empty
cur.execute("SELECT COUNT(*) FROM properties")
count = cur.fetchone()[0]

if count == 0:
    properties = [
        ("Aundh", 1200, 2, 2, 75, "house1.jpg"),
        ("Baner", 1500, 3, 3, 120, "house2.jpg"),
        ("Wakad", 1000, 2, 2, 65, "house3.jpg"),
        ("Kothrud", 1800, 3, 3, 140, "house4.jpg"),
        ("Hinjewadi", 900, 2, 2, 55, "house5.jpg"),
        ("Viman Nagar", 1300, 2, 3, 95, "house6.jpg"),
        ("Pimpri", 850, 1, 2, 45, "house7.jpg"),
        ("Kharadi", 1100, 2, 2, 78, "house8.jpg"),
        ("Hadapsar", 1050, 2, 2, 72, "house9.jpg"),
        ("Sinhagad Road", 1250, 2, 3, 88, "house10.jpg")
    ]

    cur.executemany("""
    INSERT INTO properties (location, sqft, bath, bhk, listed_price, image)
    VALUES (?, ?, ?, ?, ?, ?)
    """, properties)

conn.commit()
conn.close()

print("✅ Database setup completed successfully!")