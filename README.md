# 🔍 Plateforme de Confiance Numérique — ENSAJ

Système forensique avancé pour la détection de fraude académique (IA & Plagiat) utilisant **CrewAI**, **Google Gemini (AI Studio)** et **n8n**.

---

## 🚀 Fonctionnalités
- **Dashboard Moderne** : Interface sombre (Dark Mode) responsive avec TailwindCSS.
- **Gestion de Rôles** : Accès différenciés pour Administrateurs et Professeurs.
- **Pipeline Forensique** :
    - OCR via Google Gemini 1.5 Flash pour une extraction textuelle haute précision.
    - Analyse par agents IA spécialisés (Expert NLP, Juge Forensique).
- **Intégration n8n** : Workflow externe pour le traitement asynchrone des copies.
- **Rapports Automatisés** : Génération de rapports Markdown détaillés avec score de risque.

---

## 🛠️ Installation (De A à Z)

### 1. Cloner le projet
```bash
cd plateforme-confiance-numerique
```

### 2. Créer l'environnement virtuel
```bash
python -m venv env
# Activer sous Windows
.\env\Scripts\activate
# Activer sous Linux/Mac
source env/bin/activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configuration (.env)
Créez un fichier `.env` à la racine et ajoutez votre clé Gemini :
```env
GEMINI_API_KEY="votre_cle_gemini_ici"
SECRET_KEY="une_cle_secrete_aleatoire"
```

---

## ⚙️ Configuration n8n

La plateforme délègue l'analyse à n8n.
1. **Webhook URL** : Par défaut, le projet utilise `http://localhost:5678/webhook/upload-copies`.
2. **Callback** : Votre workflow n8n doit renvoyer le résultat à la fin via un nœud HTTP Request :
   - **Method** : POST
   - **URL** : `http://localhost:5001/api/investigation/callback`
   - **Body (JSON)** :
     ```json
     {
       "investigation_id": "{{ $node.Webhook.json.investigation_id }}",
       "status": "completed",
       "report_content": "{{ $node.CrewAI.json.output }}"
     }
     ```

---

## 🏁 Démarrage

Lancez simplement le script de démarrage automatique :
```bash
python run.py
```
*Le script va créer la base de données et les comptes par défaut lors du premier lancement.*

### Accès :
- **URL** : `http://localhost:5001`
- **Compte Admin** : `admin` / `admin123`
- **Compte Prof** : `prof_demo` / `prof123`

---

## 📁 Architecture du Projet
- `run.py` : Script de démarrage et initialisation DB.
- `web/` : Application Flask (Modèles, Routes, Templates).
- `crewai/` : Logique des agents et scripts OCR.
- `data/` : Stockage des copies uploadées et des rapports générés.
- `n8n/` : Fichier JSON du workflow pour import dans n8n.

---

## 🧪 Tests
Pour vérifier que la communication Flask <-> n8n fonctionne sans lancer un vrai workflow :
```bash
python seed_test.py   # Prépare une investigation en DB
python test_n8n.py    # Simule un retour de n8n
```

---
*Développé pour l'ENSAJ — 2026*
