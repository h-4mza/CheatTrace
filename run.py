import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

# S'assurer que le dossier 'web' est dans le chemin de recherche
sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

def setup_database():
    """
    Initialise la base PostgreSQL si nécessaire et crée l'admin par défaut.
    """
    with app.app_context():
        # Avec PostgreSQL, on tente de créer les tables (ne fait rien si elles existent déjà)
        print("--- Vérification de la structure PostgreSQL ---")
        try:
            db.create_all()
        except Exception as e:
            print(f"❌ Erreur de connexion à la base de données : {e}")
            print("Assurez-vous que PostgreSQL est lancé et que DATABASE_URL dans .env est correct.")
            sys.exit(1)
            
        # Seed Admin si la table est vide
        if not User.query.filter_by(username='admin').first():
            print("--- Création du compte administrateur par défaut ---")
            admin = User(
                username='admin',
                email='admin@ensaj.ma',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Compte admin créé (admin / admin123)")
        else:
            print("✔️ Base de données prête.")

if __name__ == '__main__':
    setup_database()
    print("\n🚀 Démarrage de la Plateforme de Confiance Numérique — ENSAJ (PostgreSQL Mode)")
    print("📍 URL : http://localhost:5001")
    print("----------------------------------------------------------")
    app.run(debug=True, host='0.0.0.0', port=5001)
