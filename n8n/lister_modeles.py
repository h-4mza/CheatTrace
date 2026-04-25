import os
from dotenv import load_dotenv
from google import genai

# Charger la clé API
load_dotenv()
cle_api = os.environ.get("GEMINI_API_KEY")

if not cle_api:
    print("❌ Clé API introuvable !")
    exit()

# Connecter le client officiel de Google
client = genai.Client(api_key=cle_api)

print("🔍 Recherche des modèles compatibles avec ton compte...")
print("-" * 40)

# Lister tous les modèles qui savent générer du texte
for model in client.models.list():
    if "generateContent" in model.supported_actions:
        print(f"✅ Nom exact à utiliser : {model.name}")
        
print("-" * 40)