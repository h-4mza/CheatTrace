import sqlite3

def verify_tables():
    conn = sqlite3.connect('forensique.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in database:", [t[0] for t in tables])
    
    for table in tables:
        table_name = table[0]
        if table_name == 'sqlite_sequence': continue
        print(f"\nStructure of {table_name}:")
        cursor.execute(f"PRAGMA table_info({table_name})")
        for column in cursor.fetchall():
            print(column)
            
    conn.close()

if __name__ == "__main__":
    verify_tables()
