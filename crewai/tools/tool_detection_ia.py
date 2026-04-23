import os
import json
from crewai.tools import tool
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

@tool("Outil de Detection Stylometrique Globale")
def outil_detection_ia(chemin_fichier: str) -> str:
    """
    Outil forensique qui analyse un lot complet de copies depuis un fichier.
    Paramètre : Le chemin absolu vers le fichier JSON (ex: C:/.../resultats_ocr.json).
    Action : Lit le fichier, boucle sur chaque copie et évalue si elle a été générée par une IA.
    Retourne : Un rapport JSON listant le score et les preuves.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    system_prompt = """Tu es un algorithme forensique spécialisé dans la stylométrie.
    Détermine si ce texte est écrit par un humain ou généré par une IA.
    CRITÈRES IA : Parfait, lisse, transitions mécaniques.
    CRITÈRES HUMAIN : Irrégulier, fautes, oralité.
    Tu dois retourner UNIQUEMENT un JSON strict avec cette structure :
    {"score_ia": <int 0-100>, "niveau_risque": "faible|modere|eleve", "preuves_ia": [], "preuves_humain": [], "synthese": "..."}"""

    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    
    # 1. LECTURE DU FICHIER SUR LE DISQUE
    try:
        with open(chemin_fichier.strip(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        copies = data.get("copies", data) if isinstance(data, dict) else data
    except Exception as e:
        return f'{{"erreur": "Impossible de lire le fichier {chemin_fichier} : {str(e)}"}}'

    resultats_globaux = []
    print("\n[Outil NLP] 🚀 Début de l'analyse des copies en cours...")

    # 2. BOUCLE D'ANALYSE
    for copie in copies:
        copie_id = copie.get("copie_id", "Inconnu")
        texte = copie.get("texte_complet", "")
        
        if len(texte.strip()) < 30:
            continue
            
        print(f"   -> Analyse de la copie {copie_id}...")
        texte_tronque = texte[:8000] if len(texte) > 8000 else texte

        try:
            prompt_complet = f"{system_prompt}\n\nAnalyse ce texte :\n\n{texte_tronque}"
            reponse = model.generate_content(prompt_complet)
            
            clean_json_str = reponse.text.replace("```json", "").replace("```", "").strip()
            analyse_json = json.loads(clean_json_str)
            analyse_json["copie_id"] = copie_id
            resultats_globaux.append(analyse_json)
            
        except Exception as e:
            print(f"   [!] Erreur sur {copie_id}: {str(e)}")
            resultats_globaux.append({
                "copie_id": copie_id, "score_ia": 0, "niveau_risque": "erreur", "synthese": f"Échec : {str(e)}"
            })

    print("[Outil NLP] ✅ Analyse terminée.\n")
    return json.dumps({"resultats_stylometrie": resultats_globaux}, ensure_ascii=False)
