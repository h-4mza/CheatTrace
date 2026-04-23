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
from tools.tool_similarite import outil_similarite_sbert, outil_clustering
from dotenv import load_dotenv

load_dotenv()

def extraire_json_verdict(raw_str: str) -> dict:
    raw_str = str(raw_str)
    try:
        return json.loads(raw_str.strip())
    except Exception:
        pass

    start = raw_str.find('{')
    while start != -1:
        depth = 0
        for i, c in enumerate(raw_str[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    fragment = raw_str[start:i+1]
                    try:
                        candidate = json.loads(fragment)
                        if "clusters_fraude" in candidate or "nb_suspects" in candidate:
                            return candidate
                    except Exception:
                        pass
                    start = raw_str.find('{', i + 1)
                    break
        else:
            break

    match = re.search(r'```json\s*(.*?)\s*```', raw_str, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return {"statut": "erreur_parsing", "raw": raw_str[:500]}

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
    analyste_fraude = agents["analyste_fraude"]

    if type_inv == "collaborative":
        desc = (
            "Le fichier contenant les copies OCR se trouve à cette adresse absolue :\n"
            f"{chemin_absolu_ocr}\n\n"
            "Ta mission :\n"
            "1. Appelle l'outil 'Outil de Calcul de Similarite SBERT et MinHash' en lui passant EXACTEMENT cette adresse.\n"
            "2. Prends le JSON retourné et appelle 'Outil de Clustering de Fraude' avec.\n"
            "3. Rédige un rapport final qui formatte ces résultats.\n"
            "Tu DOIS retourner UNIQUEMENT un JSON avec la structure exacte suivante :\n"
            "{\n"
            '  "nb_copies_analysees": 20,\n'
            '  "nb_suspects": X,\n'
            '  "copies_suspectes": [],\n'
            '  "clusters_fraude": [\n'
            "    {\n"
            '      "cluster_id": "Cluster_1",\n'
            '      "niveau_risque": "eleve",\n'
            '      "copies": ["C01", "C02"]\n'
            "    }\n"
            "  ]\n"
            "}"
        )
    else:
        desc = (
            "Le fichier contenant les copies OCR se trouve à cette adresse absolue :\n"
            f"{chemin_absolu_ocr}\n\n"
            "Ta mission :\n"
            "1. Appelle l'outil 'Outil de Calcul de Similarite SBERT et MinHash' en lui passant EXACTEMENT cette adresse.\n"
            "2. Prends le JSON retourné et appelle 'Outil de Clustering de Fraude' avec.\n"
            "3. Retourne UNIQUEMENT le JSON brut final sans balises Markdown."
        )

    tache_fraude = Task(
        description=desc,
        expected_output="Un JSON strict listant les clusters de fraude.",
        agent=analyste_fraude,
        tools=[outil_similarite_sbert, outil_clustering]
    )

    crew = Crew(
        agents=[analyste_fraude],
        tasks=[tache_fraude],
        process=Process.sequential,
        verbose=True
    )

    resultat_brut = crew.kickoff()
    resultat_json = extraire_json_verdict(str(resultat_brut))

    # Sauvegarder le résultat Similarité
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", "resultats_sim.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultat_json, f, ensure_ascii=False, indent=2)

    if type_inv == "collaborative":
        resultat_json["session_id"] = session_id
        resultat_json["statut"] = "termine"
        
        chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
        os.makedirs(chemin_dashboard, exist_ok=True)
        chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

        md  = "# Rapport Forensique Officiel (Analyse Collaborative)\n\n"
        md += f"- **Copies analysées :** {resultat_json.get('nb_copies_analysees', 'Plusieurs')}\n"
        md += f"- **Nombre de suspects :** {resultat_json.get('nb_suspects', 0)}\n\n"

        md += "## Clusters de Fraude Collaborative\n\n"
        clusters = resultat_json.get("clusters_fraude") or []
        if not clusters:
            md += "- Aucun réseau de triche collaborative détecté.\n\n"
        else:
            for c in clusters if isinstance(clusters, list) else []:
                if isinstance(c, dict):
                    copies_vals = []
                    for v in c.values():
                        if isinstance(v, list):
                            copies_vals = v
                            break
                    copies_str = ", ".join(str(x) for x in copies_vals) if copies_vals else str(c.get("copies","?"))
                    md += f"- **Cluster {c.get('cluster_id','?')}** : {copies_str} — {c.get('niveau_risque','?')}\n"

        with open(chemin_rapport, "w", encoding="utf-8") as f:
            f.write(md)

        resultat_json["output"] = md
        print("===BEGIN_N8N_JSON===")
        print(json.dumps(resultat_json, ensure_ascii=False))
        print("===END_N8N_JSON===")
        sys.exit(0)
    else:
        print(f"\n[Étape 2] ✅ Analyse de Collusion terminée et sauvegardée dans {chemin_sortie}")
        sys.exit(0)

if __name__ == "__main__":
    main()
