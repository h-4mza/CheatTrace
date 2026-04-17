import os
import sys
from werkzeug.security import generate_password_hash

# Ensure the 'web' directory is in the python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

from web.app import app, db
from web.models import User

def setup_database():
    """
    Checks if the database exists. If not, creates tables and seeds default users.
    """
    with app.app_context():
        # Correct path for the database file
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web', 'forensique_web.db')
        
        if not os.path.exists(db_path):
            print("--- Initialisation de la base de données ---")
            db.create_all()
            
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
            print("✅ Base de données créée et initialisée avec succès.")
            print("🔑 Admin: admin / admin123")
            print("🔑 Prof:  prof_demo / prof123")
        else:
            print("✔️ Base de données détectée. Prêt au lancement.")

if __name__ == '__main__':
    setup_database()
    print("\n🚀 Démarrage de la Plateforme de Confiance Numérique — ENSAJ")
    print("📍 URL : http://localhost:5001")
    print("----------------------------------------------------------")
    # Using host='0.0.0.0' to allow access from other devices if needed
    app.run(debug=True, host='0.0.0.0', port=5001)
