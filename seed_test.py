import os
import sys

# Ensure the 'web' directory is in the python path
sys.path.append(os.path.join(os.getcwd(), 'web'))

from app import app, db
from models import Module, Investigation, User

def seed_test_full():
    with app.app_context():
        # Get user
        u = User.query.first()
        if not u:
            print("❌ Erreur : Aucun utilisateur dans la DB.")
            return

        # Create module if not exists
        m = Module.query.filter_by(name='Module de Test n8n').first()
        if not m:
            m = Module(name='Module de Test n8n', professor_id=u.id)
            db.session.add(m)
            db.session.commit()
            print("✅ Module de test créé.")
        else:
            print("✔️ Module de test existe déjà.")
            
        # Create investigation #1 if not exists
        inv = Investigation.query.get(1)
        if not inv:
            inv = Investigation(id=1, module_id=m.id, status='pending')
            db.session.add(inv)
            db.session.commit()
            print("✅ Investigation #1 créée.")
        else:
            print("✔️ Investigation #1 existe déjà.")

if __name__ == '__main__':
    seed_test_full()
