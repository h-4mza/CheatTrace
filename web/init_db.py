from app import app, db
from models import User
from werkzeug.security import generate_password_hash
import os

def init_db():
    with app.app_context():
        # Create database file and tables
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'forensique_web.db')
        if os.path.exists(db_path):
            print(f"Database already exists at {db_path}. Overwriting...")
            os.remove(db_path)
        
        db.create_all()
        print("Tables created successfully.")

        # Seed Admin
        admin = User(
            username='admin',
            email='admin@ensaj.ma',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )

        # Seed Prof Demo
        prof = User(
            username='prof_demo',
            email='prof@ensaj.ma',
            password_hash=generate_password_hash('prof123'),
            role='prof'
        )

        db.session.add(admin)
        db.session.add(prof)
        db.session.commit()
        
        print("Database seeded successfully:")
        print(" - Admin: admin / admin123")
        print(" - Prof:  prof_demo / prof123")

if __name__ == '__main__':
    init_db()
