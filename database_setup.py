import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        location TEXT NOT NULL,
        sqft REAL NOT NULL,
        bath INTEGER NOT NULL,
        bhk INTEGER NOT NULL,
        listed_price REAL NOT NULL,
        image TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER,
        name TEXT,
        phone TEXT,
        message TEXT
    )
    """
)

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        old_price REAL NOT NULL,
        new_price REAL NOT NULL,
        changed_at TEXT NOT NULL
    )
    """
)

cur.execute("PRAGMA table_info(properties)")
columns = [col[1] for col in cur.fetchall()]
if "user_id" not in columns:
    cur.execute("ALTER TABLE properties ADD COLUMN user_id INTEGER")

cur.execute("SELECT COUNT(*) FROM properties")
count = cur.fetchone()[0]

if count == 0:
    properties = [
        (None, "Aundh", 1200, 2, 2, 75, "and_pun.jpg"),
        (None, "Baner", 1500, 3, 3, 120, "Residential-13-scaled.jpg"),
        (None, "Wakad", 1000, 2, 2, 65, None),
        (None, "Kothrud", 1800, 3, 3, 140, None),
        (None, "Hinjewadi", 900, 2, 2, 55, None),
        (None, "Viman Nagar", 1300, 2, 3, 95, None),
        (None, "Pimpri", 850, 1, 2, 45, None),
        (None, "Kharadi", 1100, 2, 2, 78, None),
        (None, "Hadapsar", 1050, 2, 2, 72, None),
        (None, "Sinhagad Road", 1250, 2, 3, 88, None),
    ]

    cur.executemany(
        """
        INSERT INTO properties (user_id, location, sqft, bath, bhk, listed_price, image)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        properties,
    )

conn.commit()
conn.close()
print("✅ Database setup completed successfully!")