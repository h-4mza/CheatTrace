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
            "3. Rédige un verdict final pour cette copie.\n"
            "Tu DOIS retourner UNIQUEMENT un JSON avec la structure exacte suivante :\n"
            "{\n"
            '  "nb_copies_analysees": 1,\n'
            '  "nb_suspects": X,\n'
            '  "copies_suspectes": [\n'
            "    {\n"
            '      "copie_id": "C01",\n'
            '      "niveau_risque": "eleve",\n'
            '      "preuves_ia": "Résumé des signaux...",\n'
            '      "preuves_collaboration": "Non applicable",\n'
            '      "verdict_juge": "Conclusion finale..."\n'
            "    }\n"
            "  ],\n"
            '  "clusters_fraude": []\n'
            "}"
        )
    else:
        desc = (
            "Le fichier contenant les copies OCR se trouve à cette adresse absolue :\n"
            f"{chemin_absolu_ocr}\n\n"
            "Ta mission :\n"
            "1. Donne EXACTEMENT cette adresse à l'outil 'Outil de Detection Stylometrique Globale'.\n"
            "2. Attends que l'outil te renvoie l'analyse complète (JSON).\n"
            "3. Retourne UNIQUEMENT le JSON brut sans balises Markdown."
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

    # Sauvegarder le résultat NLP
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", "resultats_nlp.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultat_json, f, ensure_ascii=False, indent=2)

    if type_inv == "singuliere":
        resultat_json["session_id"] = session_id
        resultat_json["statut"] = "termine"
        
        chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
        os.makedirs(chemin_dashboard, exist_ok=True)
        chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

        md  = "# Rapport Forensique Officiel (Analyse Singulière)\n\n"
        md += f"- **Copies analysées :** {resultat_json.get('nb_copies_analysees', 1)}\n"
        md += f"- **Nombre de suspects :** {resultat_json.get('nb_suspects', 0)}\n\n"

        md += "## Suspicions de Génération IA\n\n"
        suspects = resultat_json.get("copies_suspectes") or []
        if not suspects:
            md += "- Aucune copie suspectée de génération par IA.\n\n"
        else:
            for s in suspects if isinstance(suspects, list) else []:
                if isinstance(s, dict):
                    md += f"### Copie {s.get('copie_id','?')} — Risque : **{s.get('niveau_risque','?')}**\n"
                    md += f"- **Preuves IA :** {s.get('preuves_ia','—')}\n"
                    md += f"- **Verdict :** {s.get('verdict_juge','—')}\n\n"

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
