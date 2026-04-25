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
from tools.tool_rapport import outil_rapport
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
                        if "copies_suspectes" in candidate or "nb_suspects" in candidate:
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

    email_prof  = payload.get("email", "professeur@ensaj.ma")
    session_id  = payload.get("session_id", "session_001")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    chemin_nlp = os.path.abspath(os.path.join(script_dir, "..", "data", "resultats_nlp.json"))
    chemin_sim = os.path.abspath(os.path.join(script_dir, "..", "data", "resultats_sim.json"))

    if not os.path.exists(chemin_nlp) or not os.path.exists(chemin_sim):
        out = {"statut": "erreur", "message": "Les rapports des étapes 1 ou 2 sont manquants."}
        print(json.dumps(out))
        sys.exit(1)

    with open(chemin_nlp, "r", encoding="utf-8") as f:
        rapport_nlp = f.read()
        
    with open(chemin_sim, "r", encoding="utf-8") as f:
        rapport_sim = f.read()

    agents = creer_agents()
    juge_forensique = agents["juge_forensique"]

    tache_verdict = Task(
        description=(
            "Voici le rapport de l'Expert NLP (Stylométrie) :\n"
            f"{rapport_nlp}\n\n"
            "Voici le rapport de l'Analyste Fraude (Similarité) :\n"
            f"{rapport_sim}\n\n"
            "1. Croise leurs preuves. Identifie les étudiants qui cumulent fraude IA ET collusion ou l'un des deux de manière évidente.\n"
            "2. Rédige un verdict défendable et synthétique pour chaque cas suspect.\n"
            f"3. Prépare ce rapport pour qu'il soit envoyé à : {email_prof}.\n\n"
            "4. Appelle l'outil 'Outil de Generation de Rapport Forensique' avec ton JSON final.\n\n"
            "Tu DOIS retourner UNIQUEMENT un JSON avec la structure exacte suivante :\n"
            "{\n"
            '  "nb_copies_analysees": X (le nombre réel de copies),\n'
            '  "nb_suspects": X,\n'
            '  "copies_suspectes": [\n'
            "    {\n"
            '      "copie_id": "C01",\n'
            '      "niveau_risque": "eleve",\n'
            '      "preuves_ia": "Résumé des signaux...",\n'
            '      "preuves_collaboration": "Fait partie du cluster X...",\n'
            '      "verdict_juge": "Conclusion finale..."\n'
            "    }\n"
            "  ],\n"
            '  "clusters_fraude": [...],\n'
            '  "copies_normales": ["C05", "C08"]\n'
            "}"
        ),
        expected_output="Un JSON strict et valide contenant le verdict final de l'investigation.",
        agent=juge_forensique,
        tools=[outil_rapport]
    )

    crew = Crew(
        agents=[juge_forensique],
        tasks=[tache_verdict],
        process=Process.sequential,
        verbose=True
    )

    resultat_brut = crew.kickoff()

    # Extraction JSON robuste
    resultat_json = extraire_json_verdict(str(resultat_brut))
    resultat_json["session_id"] = session_id
    resultat_json["statut"] = "termine"

    # Sauvevegarde du verdict final
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", f"verdict_final_{session_id}.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultat_json, f, ensure_ascii=False, indent=2)

    # Génération rapport Markdown (requis pour n8n / dashboard)
    chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
    os.makedirs(chemin_dashboard, exist_ok=True)
    chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

    md  = "# 🕵️ Rapport Forensique Officiel et Détaillé\n\n"
    md += f"- **Copies analysées :** {resultat_json.get('nb_copies_analysees', 'N/A')}\n"
    md += f"- **Nombre de suspects :** {resultat_json.get('nb_suspects', 'Non précisé')}\n\n"

    md += "## ⚖️ Synthèse du Juge Forensique\n\n"
    suspects = resultat_json.get("copies_suspectes") or []
    if not suspects:
        md += "- Aucune copie suspectée par le Juge Forensique.\n\n"
    else:
        for s in suspects if isinstance(suspects, list) else []:
            if isinstance(s, dict):
                md += f"### Copie {s.get('copie_id','?')} — Risque Global : **{s.get('niveau_risque','?')}**\n"
                md += f"- **Preuves IA :** {s.get('preuves_ia','—')}\n"
                md += f"- **Collaboration :** {s.get('preuves_collaboration','—')}\n"
                md += f"- **Verdict du Juge :** {s.get('verdict_juge','—')}\n\n"

    md += "## 🕸️ Clusters de Fraude Collaborative\n\n"
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

    md += "---\n\n"
    md += "## 🔬 Rapport Détaillé de Détection IA (NLP)\n\n"
    
    # Intégrer les détails riches du JSON (resultats_nlp.json)
    try:
        with open(chemin_nlp, "r", encoding="utf-8") as f:
            nlp_data = json.load(f)
            
        resultats_nlp = nlp_data.get("resultats", [])
        if not resultats_nlp:
            md += "- Aucune donnée NLP détaillée disponible.\n\n"
        else:
            for s in resultats_nlp:
                # Si les détails sont imbriqués
                details = s.get('details_complets', s)
                
                classification = s.get('classification', details.get('classification_finale', 'INCONNU'))
                score = s.get('score_ia', details.get('score_recalcule', 0))
                
                icon = "🔴" if classification == "PROBABLEMENT_IA" else "🟠" if classification == "HYBRIDE" else "🟢"
                md += f"### {icon} Copie {s.get('copie_id','?')} — {classification} (Score : {score}/100)\n\n"
                
                md += f"**Résumé Exécutif :**\n{details.get('resume_executif', s.get('synthese', 'N/A'))}\n\n"
                
                md += "#### 📊 Analyse Multidimensionnelle\n"
                dimensions = details.get('dimensions', {})
                if dimensions:
                    for dim_key, dim_data in dimensions.items():
                        name = dim_key.replace('_', ' ').title()
                        note = dim_data.get('note', 0)
                        obs = dim_data.get('observation', '')
                        md += f"- **{name} ({note}/10) :** {obs}\n"
                else:
                    md += "- Détails des dimensions non disponibles.\n"
                md += "\n"
                
                md += "#### 🔎 Indices Linguistiques Relevés\n"
                indices = details.get('indices_linguistiques', s.get('preuves_ia', []))
                if indices:
                    for ind in indices:
                        md += f"- {ind}\n"
                else:
                    md += "- Aucun indice spécifique relevé.\n"
                md += "\n"
                
                extraits = details.get('extraits_suspects', [])
                if extraits:
                    md += "#### 🚨 Extraits Suspects (Générés par IA)\n"
                    for ext in extraits:
                        texte = ext.get('texte', '')
                        justif = ext.get('justification', '')
                        if texte:
                            md += f"> <mark class=\"bg-red-100 text-red-900 px-1 rounded\">\"{texte}\"</mark>\n> \n> **Justification :** *{justif}*\n\n"

                prompts = details.get('prompts_plausibles', {})
                if prompts:
                    md += "#### 🤖 Prompts Plausibles (Hypothèses)\n"
                    if isinstance(prompts, dict):
                        md += f"*{prompts.get('avertissement', '')}*\n"
                        for p in prompts.get('liste', []):
                            md += f"- `{p}`\n"
                    md += "\n"
                
                md += "#### ⚖️ Conclusion & Risque de Faux Positif\n"
                md += f"**Conclusion :** {details.get('conclusion', 'N/A')}\n\n"
                md += f"**Risque de Faux Positif :** `{details.get('faux_positif_risque', 'INCONNU')}`\n"
                md += f"**Raison :** {details.get('faux_positif_raison', 'N/A')}\n\n"
                md += "---\n\n"
    except Exception as e:
        md += f"- Erreur lors de la lecture des détails NLP : {str(e)}\n\n"

    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[Pipeline] Rapport sauvegardé : {chemin_rapport}", file=sys.stderr)

    resultat_json["output"] = md
    print("===BEGIN_N8N_JSON===")
    print(json.dumps(resultat_json, ensure_ascii=False))
    print("===END_N8N_JSON===")
    sys.exit(0)

if __name__ == "__main__":
    main()
