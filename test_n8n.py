import requests
import json
import time

BASE_URL = "http://localhost:5001"

def test_n8n_flow():
    print("--- Démarrage du test d'intégration n8n ---")
    
    # 1. Login to get session (Mocking for internal logic check)
    # Actually, we can just trigger the callback directly to see if DB updates
    # Let's assume investigation #1 is created via UI (or we create one in DB)
    
    # Let's simulate what n8n would send back to Flask
    payload = {
        "investigation_id": 1,
        "status": "completed",
        "report_content": """
# Rapport de Test n8n
## Résultats de l'Analyse
- **Moteur OCR** : n8n Vision
- **Verdict** : Succès de l'intégration
- **Commentaire** : La communication entre Flask et n8n est opérationnelle.
        """
    }
    
    print("\n[STEP] Envoi du callback de n8n vers Flask...")
    try:
        response = requests.post(f"{BASE_URL}/api/investigation/callback", json=payload)
        if response.status_code == 200:
            print("✅ Callback n8n traité par Flask.")
            print(f"Message: {response.json().get('message')}")
        else:
            print(f"❌ Erreur callback: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"❌ Connexion échouée: {e}")
        return

    # 2. Check if the status is updated in Flask API
    print("\n[STEP] Vérification du statut via l'API Flask...")
    try:
        # We need a session/login to check this, but let's try a direct DB check via a temp script if needed
        # Or just use the endpoint if we disable login_required for testing (not ideal)
        # Let's just check if the report file exists
        print("Note: On vérifie si le fichier rapport a été créé dans le dossier reports/")
        import os
        report_path = os.path.join(os.getcwd(), 'data', 'reports', 'investigation_1.md')
        if os.path.exists(report_path):
            print(f"✅ Fichier rapport créé à : {report_path}")
            with open(report_path, 'r', encoding='utf-8') as f:
                print("Contenu du rapport sauvegardé :")
                print(f.read())
        else:
            print(f"❌ Rapport introuvable à : {report_path}")

    except Exception as e:
        print(f"❌ Erreur de vérification: {e}")

if __name__ == "__main__":
    test_n8n_flow()
