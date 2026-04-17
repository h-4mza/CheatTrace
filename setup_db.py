import sqlite3
import os

DB_NAME = "forensique.db"

def setup_database():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"Base de données existante '{DB_NAME}' supprimée.")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Activation des clés étrangères
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Table users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'prof')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Table modules
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        professor_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (professor_id) REFERENCES users(id)
    )
    ''')

    # Table investigations
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS investigations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        report_path TEXT,
        FOREIGN KEY (module_id) REFERENCES modules(id)
    )
    ''')

    # Table exam_copies
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exam_copies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investigation_id INTEGER NOT NULL,
        original_filename TEXT NOT NULL,
        stored_path TEXT NOT NULL,
        ocr_text TEXT,
        uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (investigation_id) REFERENCES investigations(id)
    )
    ''')

    # Seeding
    users_to_seed = [
        ('admin', 'admin@ensaj.ma', 'admin123', 'admin'),
        ('prof_demo', 'prof_demo@ensaj.ma', 'prof123', 'prof')
    ]

    cursor.executemany(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        users_to_seed
    )

    conn.commit()
    print("Base de données créée et initialisée avec succès.")
    conn.close()

if __name__ == "__main__":
    setup_database()
