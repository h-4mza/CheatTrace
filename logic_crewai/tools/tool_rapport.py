import json
import os
from datetime import datetime
from crewai.tools import tool

@tool("Outil de Generation de Rapport Forensique")
def outil_rapport(verdict_json_str: str) -> str:
    """
    Outil final utilisé pour générer un rapport officiel formel à partir du verdict du juge.
    Input : Le texte JSON final contenant les copies suspectes, les preuves et les clusters.
    Action : Parse le JSON, formate un rapport en Markdown propre et professionnel, 
             et le sauvegarde dans le dossier 'dashboard'.
    Output : Un message de confirmation contenant le chemin du fichier généré.
    """
    try:
        # 1. Lecture des données
        donnees = json.loads(verdict_json_str)
        suspects = donnees.get("copies_suspectes", [])
        clusters = donnees.get("clusters_fraude", [])
    except Exception as e:
        return f"Erreur : Impossible de lire le JSON pour générer le rapport. Détails : {str(e)}"

    # 2. Création du dossier dashboard s'il n'existe pas
    dossier_sortie = os.path.join(os.path.dirname(__file__), "../../dashboard")
    os.makedirs(dossier_sortie, exist_ok=True)
    
    nom_fichier = f"rapport_investigation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    chemin_fichier = os.path.join(dossier_sortie, nom_fichier)

    # 3. Formatage du document en Markdown
    lignes_rapport = [
        "# 🕵️ Rapport d'Investigation Forensique - Fraude Académique",
        f"**Date de l'analyse :** {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        "---",
        f"## 📊 Bilan Synthétique",
        f"- **Nombre de copies analysées :** {donnees.get('nb_copies_analysees', 'N/A')}",
        f"- **Nombre total de suspects :** {donnees.get('nb_suspects', len(suspects))}",
        f"- **Réseaux de fraude détectés :** {len(clusters)}",
        "---",
        "## 🔴 Détail des Copies Suspectes\n"
    ]

    if not suspects:
        lignes_rapport.append("*Aucune fraude significative n'a été détectée par le système.*")
    else:
        for s in suspects:
            lignes_rapport.extend([
                f"### Copie ID : {s.get('copie_id', 'Inconnu')} (Risque : {s.get('niveau_risque', 'N/A').upper()})",
                f"- **Verdict du Juge :** {s.get('verdict_juge', 'Aucun verdict')}",
                f"- **Signaux IA :** {s.get('preuves_ia', 'Non détecté')}",
                f"- **Signaux Plagiat :** {s.get('preuves_collaboration', 'Non détecté')}\n"
            ])

    if clusters:
        lignes_rapport.extend([
            "---",
            "## 🕸️ Topologie des Réseaux de Triche (Clusters)\n"
        ])
        for c in clusters:
            membres = ", ".join(c.get("copies", []))
            lignes_rapport.extend([
                f"### Cluster {c.get('cluster_id')} (Risque : {c.get('niveau_risque', 'N/A')})",
                f"- **Membres impliqués :** {membres}",
                f"- **Score de similarité moyen :** {c.get('score_moyen', 0.0)}\n"
            ])

    # 4. Sauvegarde physique du fichier
    try:
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes_rapport))
        return f"Succès : Le rapport officiel a été généré et sauvegardé ici : {os.path.abspath(chemin_fichier)}"
    except Exception as e:
        return f"Erreur lors de l'écriture du fichier : {str(e)}"