import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass
import json
import argparse
import os
import re
from crewai import Crew, Process, Task
from agents import creer_agents
from tools.tool_detection_ia import outil_detection_ia
from dotenv import load_dotenv

load_dotenv()

def extraire_json_verdict(raw_str: str) -> dict:
    raw_str = str(raw_str)
    
    # Nettoyage des erreurs fréquentes des LLMs
    clean_str = raw_str.replace("\\'", "'")
    
    try:
        return json.loads(clean_str.strip())
    except Exception:
        pass

    start = clean_str.find('{')
    while start != -1:
        depth = 0
        for i, c in enumerate(clean_str[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    fragment = clean_str[start:i+1]
                    try:
                        candidate = json.loads(fragment)
                        if "copies_suspectes" in candidate or "nb_suspects" in candidate or "resultats_stylometrie" in candidate:
                            return candidate
                    except Exception:
                        pass
                    start = clean_str.find('{', i + 1)
                    break
        else:
            break

    match = re.search(r'```json\s*(.*?)\s*```', clean_str, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return {"statut": "erreur_parsing", "raw": clean_str[:500]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=False, default='{}')
    args = parser.parse_args()

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError:
        payload = {}

    chemin_ocr = payload.get("chemin_json", "data/resultats_ocr.json")
    type_inv = payload.get("type_investigation", "complete")
    session_id = payload.get("session_id", "session_001")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    chemin_absolu_ocr = os.path.abspath(os.path.join(script_dir, chemin_ocr))

    if not os.path.exists(chemin_absolu_ocr):
        print(json.dumps({"statut": "erreur", "message": f"Fichier introuvable: {chemin_absolu_ocr}"}))
        sys.exit(1)

    agents = creer_agents()
    expert_nlp = agents["expert_nlp"]

    if type_inv == "singuliere":
        desc = (
            "Le fichier contenant la copie OCR se trouve à cette adresse absolue :\n"
            f"{chemin_absolu_ocr}\n\n"
            "Ta mission :\n"
            "1. Donne EXACTEMENT cette adresse à l'outil 'Outil de Detection Stylometrique Globale'.\n"
            "2. Attends que l'outil te renvoie l'analyse.\n"
            "3. Retourne STRICTEMENT le JSON brut que l'outil t'a renvoyé, sans le modifier."
        )
    else:
        desc = (
            "Le fichier contenant les copies OCR se trouve à cette adresse absolue :\n"
            f"{chemin_absolu_ocr}\n\n"
            "Ta mission :\n"
            "1. Donne EXACTEMENT cette adresse à l'outil 'Outil de Detection Stylometrique Globale'.\n"
            "2. Attends que l'outil te renvoie l'analyse complète (JSON).\n"
            "3. Retourne STRICTEMENT le JSON brut sans balises Markdown."
        )

    tache_detection = Task(
        description=desc,
        expected_output="Un JSON strict contenant l'analyse NLP des copies.",
        agent=expert_nlp,
        tools=[outil_detection_ia]
    )

    crew = Crew(
        agents=[expert_nlp],
        tasks=[tache_detection],
        process=Process.sequential,
        verbose=True
    )

    resultat_brut = crew.kickoff()
    resultat_json = extraire_json_verdict(str(resultat_brut))
    
    # Correction : Si le résultat est une liste ou imbriqué, on normalise en dictionnaire
    if isinstance(resultat_json, dict) and "resultats_stylometrie" in resultat_json:
        inner_data = resultat_json["resultats_stylometrie"]
        if isinstance(inner_data, list):
            resultat_json = {
                "nb_copies": len(inner_data),
                "nb_suspects": sum(1 for x in inner_data if x.get('classification') != 'HUMAIN'),
                "resultats": inner_data
            }
        else:
            resultat_json = inner_data
    elif isinstance(resultat_json, list):
        resultat_json = {
            "nb_copies": len(resultat_json),
            "nb_suspects": sum(1 for x in resultat_json if x.get('classification') != 'HUMAIN'),
            "resultats": resultat_json
        }

    # S'assurer que c'est un dictionnaire pour la suite
    if not isinstance(resultat_json, dict):
        resultat_json = {"resultats": [], "erreur": "Format de sortie invalide"}

    # Sauvegarder le résultat NLP
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", f"resultats_nlp_{session_id}.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultat_json, f, ensure_ascii=False, indent=2)

    if type_inv == "singuliere":
        resultat_json["session_id"] = session_id
        resultat_json["statut"] = "termine"
        
        chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
        os.makedirs(chemin_dashboard, exist_ok=True)
        chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

        md  = "# 🕵️ Rapport Forensique : Analyse Stylométrique\n\n"
        md += f"**Copies analysées :** `{resultat_json.get('nb_copies', 1)}` &nbsp; | &nbsp; "
        md += f"**Alerte Suspects :** `{resultat_json.get('nb_suspects', 0)}`\n\n"
        md += "---\n\n"

        resultats = resultat_json.get("resultats", [])
        if not resultats:
            md += "⚠️ *Aucune analyse détaillée n'a pu être extraite.*\n\n"
        else:
            for s in resultats:
                details = s.get('details_complets', s)
                classification = s.get('classification', details.get('classification_finale', 'INCONNU'))
                score = s.get('score_ia', details.get('score_recalcule', 0))
                
                icon = "🔴" if classification == "PROBABLEMENT_IA" else "🟠" if classification == "HYBRIDE" else "🟢"
                color_class = "text-red-600" if classification == "PROBABLEMENT_IA" else "text-amber-600" if classification == "HYBRIDE" else "text-green-600"
                
                md += f"## {icon} Fiche Copie : **{s.get('copie_id','?')}**\n\n"
                
                # --- VERDICT EXÉCUTIF ---
                md += "### 📋 Synthèse Exécutive\n"
                md += f"> **Classification :** <strong class=\"{color_class}\">{classification}</strong> (Indice de certitude : **{score}%**)\n> \n"
                md += f"> **Conclusion du modèle :** *{details.get('resume_executif', s.get('synthese', 'N/A'))}*\n\n"
                
                # --- EXTRAITS SUSPECTS (Preuves matérielles) ---
                extraits = details.get('extraits_suspects', [])
                if extraits:
                    md += "### 🚨 Pièces à Conviction (Extraits générés par IA)\n"
                    for ext in extraits:
                        texte = ext.get('texte', '')
                        justif = ext.get('justification', '')
                        if texte:
                            md += f"<div class=\"bg-red-50 border-l-4 border-red-500 p-4 my-2 rounded\">\n"
                            md += f"  <p class=\"font-mono text-sm text-slate-800 mb-2\">« {texte} »</p>\n"
                            md += f"  <p class=\"text-xs text-red-700 font-medium\"><strong>Motif :</strong> {justif}</p>\n"
                            md += f"</div>\n"
                    md += "\n"

                # --- TABLEAU DES DIMENSIONS ---
                md += "### 📊 Profil Dimensionnel\n\n"
                md += "| Dimension Analysée | Score IA | Observation |\n"
                md += "| :--- | :---: | :--- |\n"
                dimensions = details.get('dimensions', {})
                if dimensions:
                    for dim_key, dim_data in dimensions.items():
                        name = dim_key.replace('_', ' ').title()
                        note = dim_data.get('note', 0)
                        obs = dim_data.get('observation', '').replace('\n', ' ')
                        md += f"| **{name}** | `{note}/10` | {obs} |\n"
                else:
                    md += "| N/A | N/A | Détails non disponibles |\n"
                md += "\n"
                
                # --- INDICES & HYPOTHÈSES ---
                md += "<div class=\"grid grid-cols-1 md:grid-cols-2 gap-4 my-4\">\n"
                
                md += "<div class=\"bg-slate-50 p-4 rounded-xl border border-slate-100\">\n"
                md += "<h4 class=\"text-sm font-bold mb-2\">🔎 Indices Linguistiques</h4>\n"
                md += "<ul class=\"text-xs space-y-1 text-slate-600 list-disc list-inside ml-2\">\n"
                indices = details.get('indices_linguistiques', s.get('preuves_ia', []))
                if indices:
                    for ind in indices:
                        md += f"<li>{ind}</li>\n"
                else:
                    md += "<li>Aucun indicateur marquant</li>\n"
                md += "</ul>\n</div>\n"
                
                md += "<div class=\"bg-slate-50 p-4 rounded-xl border border-slate-100\">\n"
                md += "<h4 class=\"text-sm font-bold mb-2\">🤖 Prompts Hypothétiques</h4>\n"
                md += "<ul class=\"text-xs space-y-1 text-slate-600 list-disc list-inside ml-2\">\n"
                prompts = details.get('prompts_plausibles', {})
                if prompts and isinstance(prompts, dict):
                    for p in prompts.get('liste', []):
                        md += f"<li><code class=\"bg-white px-1 rounded border\">{p}</code></li>\n"
                else:
                    md += "<li>Non applicable</li>\n"
                md += "</ul>\n</div>\n"
                
                md += "</div>\n\n"
                
                # --- FIABILITÉ ---
                risque_fp = details.get('faux_positif_risque', 'INCONNU')
                badge_color = "bg-green-100 text-green-800" if risque_fp == "FAIBLE" else "bg-amber-100 text-amber-800" if risque_fp == "MODERE" else "bg-red-100 text-red-800"
                md += "### ⚖️ Tolérance aux Faux Positifs\n"
                md += f"<p class=\"text-sm\">Risque de Faux Positif : <span class=\"px-2 py-0.5 rounded text-xs font-bold {badge_color}\">{risque_fp}</span><br>\n"
                md += f"<span class=\"text-slate-500 italic\">{details.get('faux_positif_raison', 'Aucune raison spécifiée.')}</span></p>\n\n"
                
                md += "---\n\n"

        with open(chemin_rapport, "w", encoding="utf-8") as f:
            f.write(md)

        resultat_json["output"] = md
        print("===BEGIN_N8N_JSON===")
        print(json.dumps(resultat_json, ensure_ascii=False))
        print("===END_N8N_JSON===")
        sys.exit(0)
    else:
        print(f"\n[Etape 1]  Analyse NLP terminee et sauvegardee dans {chemin_sortie}")
        sys.exit(0)

if __name__ == "__main__":
    main()
