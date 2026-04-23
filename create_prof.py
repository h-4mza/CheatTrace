import os
import sys
from dotenv import load_dotenv

# Ajoute le dossier 'web' au chemin de recherche de Python
sys.path.append(os.path.join(os.getcwd(), 'web'))

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

load_dotenv()

def create_prof():
    print("--- Création d'un profil Professeur ---")
    with app.app_context():
        username = 'prof_test'
        email = 'prof@ensaj.ma'
        password = 'prof123'
        
        if User.query.filter_by(username=username).first():
            print(f"ℹ️ L'utilisateur {username} existe déjà.")
        else:
            new_prof = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='prof'
            )
            db.session.add(new_prof)
            db.session.commit()
            print(f"✅ Profil Professeur créé !")
            print(f"🔑 Login: {username}")
            print(f"🔑 Pass: {password}")

if __name__ == "__main__":
    create_prof()
