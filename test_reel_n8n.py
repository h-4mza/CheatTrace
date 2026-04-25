import requests
import os
import sys
import json
import time
from datetime import datetime

# Ajoute le dossier 'web' au chemin de recherche
sys.path.append(os.path.join(os.getcwd(), 'web'))

from app import app, db
from models import Investigation, ExamCopy, Module

N8N_URL = "http://localhost:5678/webhook/upload-copies"

def lancer_test_n8n(type_test="singuliere"):
    print(f"\n--- 🚀 Lancement d'une Investigation {type_test.upper()} via n8n ---")
    
    with app.app_context():
        module = Module.query.first()
        question = "Pensez-vous que les réseaux sociaux ont un impact positif ou négatif sur les relations entre les personnes ? Justifiez votre réponse avec des arguments et des exemples."
        
        # 1. Création en base
        inv = Investigation(
            module_id=module.id,
            status='processing',
            type_investigation=type_test,
            exam_question=question,
            created_at=datetime.utcnow()
        )
        db.session.add(inv)
        db.session.commit()
        inv_id = inv.id
        print(f"✅ Base de données : Investigation #{inv_id} créée.")

        # 2. Préparation des fichiers pour l'envoi
        files_payload = []
        
        if type_test == "singuliere":
            # On prend juste la première copie de notre fichier de simulation
            with open('entree_detection_ia.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            copie = data['copies'][0]
            
            # On crée une image temporaire
            img_path = "test_scan_n8n.jpg"
            with open(img_path, 'wb') as f: f.write(b"fake_jpeg_content")
            
            files_payload.append(('files', (f"scan_C01.jpg", open(img_path, 'rb'), 'image/jpeg')))
        else:
            # Investigation Collaborative (9 copies)
            with open('entree_detection_ia.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for i, copie in enumerate(data['copies']):
                img_name = f"scan_{copie['copie_id']}.jpg"
                with open(img_name, 'wb') as f: f.write(b"fake_jpeg_content")
                files_payload.append(('files', (img_name, open(img_name, 'rb'), 'image/jpeg')))

        # 3. Envoi à n8n
        data_payload = {
            "investigation_id": inv_id,
            "email": "test@ensaj.ma",
            "type_investigation": type_test,
            "exam_question": question,
            "callback_url": "http://localhost:5001/api/investigation/callback"
        }

        print(f"📤 Envoi de la requête à n8n ({len(files_payload)} fichiers)...")
        try:
            response = requests.post(N8N_URL, data=data_payload, files=files_payload)
            if response.status_code == 200:
                print(f"✅ n8n a accepté la demande pour #{inv_id}.")
                print(f"👉 Allez voir n8n pour suivre l'exécution des scripts Python.")
            else:
                print(f"❌ Erreur n8n ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Impossible de joindre n8n : {e}")
        
        # Nettoyage des fichiers temporaires créés pour l'upload
        for _, file_info in files_payload:
            file_info[1].close()
            try: os.remove(file_info[0])
            except: pass

if __name__ == "__main__":
    # Test 1 : Collaborative
    lancer_test_n8n("collaborative")
    
    # Pause pour ne pas surcharger n8n
    time.sleep(5)
    
    # Test 2 : Complete (Globale)
    lancer_test_n8n("complete")

    print("\n--- FIN DU SCRIPT DE LANCEMENT ---")
    print("Vérifiez l'interface Web ou la base de données PostgreSQL dans quelques instants.")
