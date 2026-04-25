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

    # Génération rapport Markdown (requis pour n8n / dashboard)
    chemin_dashboard = os.path.abspath(os.path.join(script_dir, "..", "dashboard"))
    os.makedirs(chemin_dashboard, exist_ok=True)
    chemin_rapport = os.path.join(chemin_dashboard, "rapport_officiel.md")

    md  = "# 🕵️ Rapport Forensique : Synthèse Multi-Couches\n\n"
    md += f"**Copies analysées :** `{resultat_json.get('nb_copies_analysees', 'N/A')}` &nbsp; | &nbsp; "
    md += f"**Alerte Suspects :** `{resultat_json.get('nb_suspects', 'Non précisé')}`\n\n"

    md += "## ⚖️ Verdict du Juge Forensique\n\n"
    suspects = resultat_json.get("copies_suspectes") or []
    if not suspects:
        md += "> ✅ *Aucune anomalie croisée majeure n'a été détectée lors de l'instruction.* \n\n"
    else:
        for s in suspects if isinstance(suspects, list) else []:
            if isinstance(s, dict):
                risque = str(s.get('niveau_risque', 'N/A')).upper()
                color_risque = "text-red-600" if "ELEVE" in risque else "text-amber-600" if "MODERE" in risque else "text-slate-600"
                
                md += f"<div class=\"bg-white p-6 rounded-2xl border border-slate-200 shadow-sm mb-4\">\n"
                md += f"  <h3 class=\"text-lg font-black mb-2\">Dossier Copie : <strong>{s.get('copie_id','?')}</strong></h3>\n"
                md += f"  <div class=\"flex gap-2 mb-4\">\n"
                md += f"    <span class=\"px-2 py-1 bg-slate-100 text-[10px] font-black uppercase tracking-widest rounded {color_risque}\">Risque : {risque}</span>\n"
                md += f"  </div>\n"
                md += f"  <p class=\"text-sm text-slate-700 mb-2\"><strong><i class=\"bi bi-robot\"></i> Signaux IA :</strong> {s.get('preuves_ia','—')}</p>\n"
                md += f"  <p class=\"text-sm text-slate-700 mb-4\"><strong><i class=\"bi bi-people\"></i> Collusion :</strong> {s.get('preuves_collaboration','—')}</p>\n"
                md += f"  <div class=\"bg-slate-50 border-l-4 border-slate-400 p-3 rounded\">\n"
                md += f"    <p class=\"text-sm font-medium text-slate-800\"><strong>Verdict :</strong> {s.get('verdict_juge','—')}</p>\n"
                md += f"  </div>\n"
                md += f"</div>\n\n"

    md += "## 🕸️ Topologie des Réseaux de Fraude\n\n"
    clusters = resultat_json.get("clusters_fraude") or []
    if not clusters:
        md += "> ✅ *Aucune structure de triche collaborative identifiée.*\n\n"
    else:
        for c in clusters if isinstance(clusters, list) else []:
            if isinstance(c, dict):
                copies_vals = []
                for v in c.values():
                    if isinstance(v, list):
                        copies_vals = v
                        break
                copies_str = ", ".join(str(x) for x in copies_vals) if copies_vals else str(c.get("copies","?"))
                md += f"- **Réseau {c.get('cluster_id','?')}** : Les copies `{copies_str}` partagent une sémantique ou structure anormalement similaire (Risque : **{c.get('niveau_risque','?').upper()}**).\n"

    md += "\n---\n\n"
    md += "## 🔬 Fiches Techniques : Détection Stylométrique (IA)\n\n"
    
    # Intégrer les détails riches du JSON (resultats_nlp.json)
    try:
        with open(chemin_nlp, "r", encoding="utf-8") as f:
            nlp_data = json.load(f)
            
        resultats_nlp = nlp_data.get("resultats", [])
        if not resultats_nlp:
            md += "⚠️ *Aucune donnée NLP détaillée disponible.*\n\n"
        else:
            for s in resultats_nlp:
                # Si les détails sont imbriqués
                details = s.get('details_complets', s)
                
                classification = s.get('classification', details.get('classification_finale', 'INCONNU'))
                score = s.get('score_ia', details.get('score_recalcule', 0))
                
                icon = "🔴" if classification == "PROBABLEMENT_IA" else "🟠" if classification == "HYBRIDE" else "🟢"
                color_class = "text-red-600" if classification == "PROBABLEMENT_IA" else "text-amber-600" if classification == "HYBRIDE" else "text-green-600"
                
                md += f"### {icon} Fiche Copie : **{s.get('copie_id','?')}**\n\n"
                
                md += "#### 📋 Synthèse Exécutive\n"
                md += f"> **Classification IA :** <strong class=\"{color_class}\">{classification}</strong> (Indice : **{score}%**)\n> \n"
                md += f"> **Conclusion du modèle :** *{details.get('resume_executif', s.get('synthese', 'N/A'))}*\n\n"
                
                # --- EXTRAITS SUSPECTS ---
                extraits = details.get('extraits_suspects', [])
                if extraits:
                    md += "#### 🚨 Pièces à Conviction (Extraits générés par IA)\n"
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
                md += "#### 📊 Profil Dimensionnel\n\n"
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
                    md += "| N/A | N/A | Détails des dimensions non disponibles |\n"
                md += "\n"
                
                # --- INDICES & HYPOTHÈSES ---
                md += "<div class=\"grid grid-cols-1 md:grid-cols-2 gap-4 my-4\">\n"
                
                md += "<div class=\"bg-slate-50 p-4 rounded-xl border border-slate-100\">\n"
                md += "<h5 class=\"text-sm font-bold mb-2\">🔎 Indices Linguistiques</h5>\n"
                md += "<ul class=\"text-xs space-y-1 text-slate-600 list-disc list-inside ml-2\">\n"
                indices = details.get('indices_linguistiques', s.get('preuves_ia', []))
                if indices:
                    for ind in indices:
                        md += f"<li>{ind}</li>\n"
                else:
                    md += "<li>Aucun indicateur marquant</li>\n"
                md += "</ul>\n</div>\n"
                
                md += "<div class=\"bg-slate-50 p-4 rounded-xl border border-slate-100\">\n"
                md += "<h5 class=\"text-sm font-bold mb-2\">🤖 Prompts Hypothétiques</h5>\n"
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
                md += "#### ⚖️ Tolérance aux Faux Positifs\n"
                md += f"<p class=\"text-sm\">Risque de Faux Positif : <span class=\"px-2 py-0.5 rounded text-xs font-bold {badge_color}\">{risque_fp}</span><br>\n"
                md += f"<span class=\"text-slate-500 italic\">{details.get('faux_positif_raison', 'Aucune raison spécifiée.')}</span></p>\n\n"
                
                md += "---\n\n"
    except Exception as e:
        md += f"> ⚠️ *Erreur lors de l'extraction des fiches techniques détaillées ({str(e)}).* \n\n"

    with open(chemin_rapport, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[Pipeline] Rapport sauvegardé : {chemin_rapport}", file=sys.stderr)

    resultat_json["output"] = md
    
    # Sauvegarde du verdict final complet (avec le markdown)
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", f"verdict_final_{session_id}.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(resultat_json, f, ensure_ascii=False, indent=2)

    print("===BEGIN_N8N_JSON===")
    print(json.dumps(resultat_json, ensure_ascii=False))
    print("===END_N8N_JSON===")
    sys.exit(0)

if __name__ == "__main__":
    main()
