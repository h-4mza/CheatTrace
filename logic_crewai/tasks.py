from crewai import Task
from tools.tool_detection_ia import outil_detection_ia
from tools.tool_similarite   import outil_similarite_sbert, outil_clustering
from tools.tool_rapport      import outil_rapport

def creer_taches(agents: dict, email_prof: str) -> list:

    # ── Tâche 1 : Détection IA ──────────────────────────────
    tache_detection = Task(
        description=(
            "Le fichier contenant les copies se trouve à cette adresse absolue :\n"
            "{chemin_fichier_json}\n\n"
            "Ta mission est très simple :\n"
            "1. Donne EXACTEMENT cette adresse (ce chemin de fichier) à l'outil 'Outil de Detection Stylometrique Globale'. Ne lui envoie surtout pas de JSON.\n"
            "2. Attends que l'outil te renvoie l'analyse complète de toutes les copies.\n"
            "3. Formate joliment les résultats retournés par l'outil en un rapport clair."
        ),
        expected_output="Un rapport listant les ID des copies suspectées d'IA avec leurs scores.",
        agent=agents["expert_nlp"],
        tools=[outil_detection_ia],
    )

    # ── Tâche 2 : Analyse des réseaux de Fraude ─────────────
    tache_fraude = Task(
        description=(
            "Le fichier contenant les copies se trouve à cette adresse absolue :\n"
            "{chemin_fichier_json}\n\n"
            "1. Appelle l'outil 'Outil de Calcul de Similarite SBERT et MinHash' en lui passant EXACTEMENT cette adresse de fichier.\n"
            "2. Prends le JSON retourné par cet outil et appelle 'Outil de Clustering de Fraude' avec ce JSON comme paramètre.\n"
            "3. Rédige un rapport listant les clusters de fraudeurs et le seuil utilisé."
        ),
        expected_output="Un rapport listant les clusters de fraude et les paires évidentes.",
        agent=agents["analyste_fraude"],
        tools=[outil_similarite_sbert, outil_clustering],
    )

    # ── Tâche 3 : Le Verdict Final du Juge ──────────────────
    tache_verdict = Task(
        description=(
            "Tu as reçu le rapport de l'Expert NLP et celui de l'Analyste Fraude.\n\n"
            "1. Croise leurs preuves. Identifie les étudiants qui cumulent fraude IA ET collusion.\n"
            "2. Rédige un verdict défendable et synthétique pour chaque cas suspect.\n"
            f"3. Prépare ce rapport pour qu'il soit envoyé à : {email_prof}.\n\n"
            "4. Appelle l'outil 'Outil de Generation de Rapport Forensique' avec ton JSON final.\n\n"
            "Tu DOIS retourner UNIQUEMENT un JSON avec la structure exacte suivante :\n"
            "{\n"
            '  "nb_copies_analysees": 20,\n'
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
        agent=agents["juge_forensique"],
        tools=[outil_rapport],
        context=[tache_detection, tache_fraude],
    )

    return [tache_detection, tache_fraude, tache_verdict]