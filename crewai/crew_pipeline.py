import sys
import json
import argparse
import os
import re
from crewai import Crew, Process
from dotenv import load_dotenv

from agents import creer_agents
from tasks  import creer_taches

load_dotenv()

def extraire_json_verdict(raw_str: str) -> dict:
    """
    FIX BUG CRITIQUE : l'ancienne regex ne trouvait pas les JSON imbriqués.
    Cette version balance les accolades correctement.
    """
    raw_str = str(raw_str)

    # Tentative 1 : le texte EST déjà un JSON pur
    try:
        return json.loads(raw_str.strip())
    except Exception:
        pass

    # Tentative 2 : balancement d'accolades (robuste pour JSON imbriqués)
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
                        # Garder uniquement le verdict final
                        if "copies_suspectes" in candidate or "nb_suspects" in candidate:
                            return candidate
                    except Exception:
                        pass
                    # Chercher le prochain {
                    start = raw_str.find('{', i + 1)
                    break
        else:
            break

    # Tentative 3 : extraire entre ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', raw_str, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    return {"raw": raw_str[:500]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=False, default='{}')
    args = parser.parse_args()

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError:
        payload = {}

    chemin_json = payload.get("chemin_json", "data/resultats_ocr.json")
    email_prof  = payload.get("email",       "professeur@ensaj.ma")
    session_id  = payload.get("session_id",  "session_001")

    # Résoudre le chemin depuis le dossier du script
    script_dir    = os.path.dirname(os.path.abspath(__file__))
    chemin_absolu = os.path.abspath(os.path.join(script_dir, chemin_json))

    if not os.path.exists(chemin_absolu):
        out = {"statut": "erreur", "message": f"Fichier introuvable: {chemin_absolu}"}
        print(json.dumps(out))
        sys.exit(1)

    print(f"[Pipeline] Fichier JSON chargé : {chemin_absolu}", file=sys.stderr)

    agents = creer_agents()
    taches = creer_taches(agents, email_prof)

    crew = Crew(
        agents=[
            agents["expert_nlp"],
            agents["analyste_fraude"],
            agents["juge_forensique"],
        ],
        tasks=taches,
        process=Process.sequential,
        verbose=True,
        memory=False,
    )

    inputs = {"chemin_fichier_json": chemin_absolu}
    resultat_brut = crew.kickoff(inputs=inputs)

    # Extraction JSON robuste
    resultat_json = extraire_json_verdict(str(resultat_brut))

    resultat_json["session_id"] = session_id
    resultat_json["statut"]     = "termine"

    # Génération rapport Markdown
    chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
    os.makedirs(chemin_dashboard, exist_ok=True)
    chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

    md  = "# Rapport Forensique Officiel\n\n"
    md += f"- **Copies analysées :** {resultat_json.get('nb_copies_analysees', 20)}\n"
    md += f"- **Nombre de suspects :** {resultat_json.get('nb_suspects', 'Non précisé')}\n\n"

    md += "## Suspicions de Génération IA\n\n"
    suspects = resultat_json.get("copies_suspectes") or []
    if not suspects:
        md += "- Aucune copie suspectée de génération par IA.\n\n"
    else:
        for s in suspects if isinstance(suspects, list) else []:
            if isinstance(s, dict):
                md += f"### Copie {s.get('copie_id','?')} — Risque : **{s.get('niveau_risque','?')}**\n"
                md += f"- **Preuves IA :** {s.get('preuves_ia','—')}\n"
                md += f"- **Collaboration :** {s.get('preuves_collaboration','—')}\n"
                md += f"- **Verdict :** {s.get('verdict_juge','—')}\n\n"

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

    print(f"[Pipeline] Rapport sauvegardé : {chemin_rapport}", file=sys.stderr)

    # Sortie propre pour n8n (stdout seulement)
    print(json.dumps(resultat_json, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
