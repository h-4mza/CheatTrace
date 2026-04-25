import os
import sys
import json
import sqlite3
from datetime import datetime

# Ajoute le dossier 'web' au chemin de recherche
sys.path.append(os.path.join(os.getcwd(), 'web'))

from app import app, db
from models import Investigation, ExamCopy, Module

def simuler_investigation():
    print("--- Simulation d'une Investigation Globale (9 copies) ---")
    
    with app.app_context():
        # 1. Récupération ou création d'un module de test
        module = Module.query.first()
        if not module:
            print("❌ Aucun module trouvé. Veuillez d'abord en créer un via l'interface.")
            return

        # 2. Création de l'investigation en base (PostgreSQL)
        question_text = "Pensez-vous que les réseaux sociaux ont un impact positif ou négatif sur les relations entre les personnes ? Justifiez votre réponse avec des arguments et des exemples."
        
        inv = Investigation(
            module_id=module.id,
            status='pending',
            type_investigation='collaborative', # On commence par collaborative
            exam_question=question_text,
            created_at=datetime.utcnow()
        )
        db.session.add(inv)
        db.session.commit()
        inv_id = inv.id
        print(f"✅ Investigation #{inv_id} créée en base (Type: Collaborative).")

        # 3. Préparation du dossier physique
        storage_path = r'C:\Forensic_Storage\investigations'
        inv_dir = os.path.join(storage_path, str(inv_id))
        os.makedirs(inv_dir, exist_ok=True)
        
        # Sauvegarde de la question
        with open(os.path.join(inv_dir, 'question.txt'), 'w', encoding='utf-8') as f:
            f.write(question_text)

        # 4. Chargement des données simulées
        with open('entree_detection_ia.json', 'r', encoding='utf-8') as f:
            data_simulee = json.load(f)

        # 5. Création des copies en base et fichiers OCR
        copies_pour_json = []
        for i, copie_data in enumerate(data_simulee['copies']):
            filename = f"copie_{copie_data['copie_id']}.jpg"
            filepath = os.path.join(inv_dir, filename)
            
            # On crée un fichier vide pour simuler l'image
            with open(filepath, 'w') as f: f.write("fake image data")

            new_copy = ExamCopy(
                investigation_id=inv_id,
                original_filename=filename,
                stored_path=filepath,
                ocr_text=copie_data['texte_complet']
            )
            db.session.add(new_copy)
            
            # Préparation de l'entrée pour le JSON final
            copies_pour_json.append({
                "copie_id": copie_data['copie_id'],
                "fichier": filename,
                "texte_complet": copie_data['texte_complet'],
                "nb_chars": len(copie_data['texte_complet']),
                "duree_sec": 0.5,
                "question": question_text
            })

        db.session.commit()
        print(f"✅ 9 copies enregistrées en base pour l'investigation #{inv_id}.")

        # 6. Création du fichier resultats_ocr.json (ce que n8n ferait normalement)
        resultats_ocr = {
            "nb_copies": len(copies_pour_json),
            "copies": copies_pour_json
        }
        ocr_json_path = os.path.join(inv_dir, 'resultats_ocr.json')
        with open(ocr_json_path, 'w', encoding='utf-8') as f:
            json.dump(resultats_ocr, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Fichier {ocr_json_path} généré.")

        # 7. Lancement manuel de l'étape de similarité (Investigation Collaborative)
        print("\n🚀 Lancement de l'étape 2 : Analyse de Similarité (Collaborative)...")
        
        # On simule l'appel que ferait n8n
        import subprocess
        
        # Commande pour step2_similarite.py
        payload = {
            "chemin_json": ocr_json_path.replace('\\', '/'),
            "type_investigation": "collaborative",
            "session_id": str(inv_id)
        }
        payload_str = json.dumps(payload).replace('"', '\\"')
        
        cmd = [
            sys.executable, 
            "crewai/step2_similarite.py", 
            "--payload", 
            f'"{json.dumps(payload)}"'
        ]
        
        # Pour éviter les problèmes de guillemets sous Windows, on utilise une version simplifiée
        os.environ['PYTHONPATH'] = os.getcwd()
        
        print(f"Exécution de l'analyse de similarité sur 9 copies...")
        
        # On lance le script
        try:
            # On ajoute le dossier logic_crewai au path pour les imports internes (agents, tools)
            sys.path.append(os.path.join(os.getcwd(), 'logic_crewai'))
            
            # 1. TEST ÉTAPE 2 (DÉJÀ FAIT MAIS ON GARDE LA LOGIQUE)
            from logic_crewai.step2_similarite import main as run_similarity
            sys.argv = ['step2_similarite.py', '--payload', json.dumps(payload)]
            # run_similarity() # On peut le commenter si on veut juste l'étape 1
            
            # 2. TEST ÉTAPE 1 (NLP / DÉTECTION IA)
            print("\n🚀 Lancement de l'étape 1 : Analyse NLP (Détection IA)...")
            from logic_crewai.step1_nlp import main as run_nlp
            payload_nlp = {
                "chemin_json": ocr_json_path.replace('\\', '/'),
                "type_investigation": "singuliere", # singuliere ou complete déclenche le NLP
                "session_id": str(inv_id)
            }
            sys.argv = ['step1_nlp.py', '--payload', json.dumps(payload_nlp)]
            run_nlp()
            
            print("\n✅ Simulation complète terminée.")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution de CrewAI : {e}")

if __name__ == "__main__":
    simuler_investigation()
