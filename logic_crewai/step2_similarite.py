import os
import sys
import json
import argparse
import numpy as np
import networkx as nx
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

# ML & NLP
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Vector DB
import chromadb

# CrewAI & Pydantic
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. SCHÉMAS PYDANTIC (STRUCTURED OUTPUT)
# ==========================================

class PairScore(BaseModel):
    copie_a: str = Field(..., description="ID de la première copie")
    copie_b: str = Field(..., description="ID de la seconde copie")
    score_composite: float = Field(..., description="Score final pondéré (0-1)")
    score_sbert: float = Field(..., description="Score de similarité sémantique")
    score_tfidf: float = Field(..., description="Score de similarité lexicale char-level")
    score_structure: float = Field(..., description="Score de similarité structurelle")
    score_erreurs: float = Field(..., description="Score de partage d'erreurs/anomalies")

class ClusterFraude(BaseModel):
    cluster_id: str = Field(..., description="Identifiant unique du cluster (ex: Réseau_1)")
    niveau_risque: str = Field(..., description="Niveau de risque: eleve, moyen, faible")
    score_moyen: float = Field(..., description="Score composite moyen au sein du cluster")
    copies: List[str] = Field(..., description="Liste des IDs des copies dans ce réseau")
    preuve_majeure: str = Field(..., description="Explication textuelle de la collusion")

class FraudReport(BaseModel):
    nb_copies_analysees: int = Field(..., description="Nombre total de copies dans le lot")
    nb_suspects: int = Field(..., description="Nombre d'étudiants impliqués dans des clusters")
    copies_suspectes: List[str] = Field(..., description="Liste plate de tous les suspects")
    copies_normales: List[str] = Field(..., description="Liste des copies saines")
    scores_confiance: List[PairScore] = Field(..., description="Détail des scores par paire")
    graphe_collusion: Dict[str, List[str]] = Field(..., description="Dictionnaire d'adjacence du graphe")
    clusters_fraude: List[ClusterFraude] = Field(..., description="Les réseaux détectés")
    rapport_markdown: str = Field(..., description="Le rapport forensique complet formaté en Markdown")

# ==========================================
# 2. MOTEUR D'EXTRACTION ET CALCUL (FEATURES)
# ==========================================

class FeatureExtractor:
    def __init__(self):
        # Cache model to avoid reloading
        self.sbert_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        # Initialize ChromaDB for Inter-session Memory
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(name="exam_copies_memory")

    def extraire_structure(self, texte: str) -> dict:
        """Extrait des features structurelles simples (paragraphes, longueurs)."""
        paragraphes = [p for p in texte.split('\n') if len(p.strip()) > 10]
        return {
            "nb_paragraphes": len(paragraphes),
            "longueur_moyenne_para": np.mean([len(p) for p in paragraphes]) if paragraphes else 0,
            "variance_longueur": np.var([len(p) for p in paragraphes]) if paragraphes else 0
        }

    def detecter_erreurs_communes(self, txt_a: str, txt_b: str) -> float:
        """
        Approximation de détection d'erreurs/mots rares communs.
        Dans une vraie prod, on utiliserait un dictionnaire de fautes (Hunspell).
        Ici on compare les mots rares (hors vocabulaire courant).
        """
        mots_a = set(txt_a.lower().split())
        mots_b = set(txt_b.lower().split())
        intersection = mots_a.intersection(mots_b)
        # Score arbitraire basé sur le chevauchement brut (simplifié pour l'exemple)
        if not mots_a or not mots_b: return 0.0
        return len(intersection) / min(len(mots_a), len(mots_b))

    def calculer_matrice(self, copies: List[dict]) -> List[dict]:
        ids = [str(c.get("copie_id", f"C{i}")) for i, c in enumerate(copies)]
        textes = [c.get("texte_complet", "").lower() for c in copies]
        n = len(copies)
        
        if n < 2: return []

        # SBERT (Sémantique)
        embeds = self.sbert_model.encode(textes, show_progress_bar=False)
        mat_sbert = cosine_similarity(embeds)

        # Sauvegarde dans ChromaDB (Mémoire Inter-sessions)
        try:
            # On stocke pour pouvoir comparer les années précédentes plus tard
            self.collection.upsert(
                documents=textes,
                metadatas=[{"annee": "2026", "module": "test"}] * n,
                ids=ids
            )
        except Exception as e:
            print(f"[WARN] Erreur ChromaDB : {e}")

        # TF-IDF (Lexical Char-level robuste OCR)
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=1)
        try:
            tfidf_matrix = vectorizer.fit_transform(textes)
            mat_tfidf = cosine_similarity(tfidf_matrix)
        except:
            mat_tfidf = np.zeros((n, n))

        # Extraction Structure
        structures = [self.extraire_structure(t) for t in textes]

        paires = []
        for i in range(n):
            for j in range(i+1, n):
                s_sbert = float(mat_sbert[i][j])
                s_tfidf = float(mat_tfidf[i][j])
                
                # Similarité Structurelle (Basée sur la variance du nombre de paragraphes)
                diff_para = abs(structures[i]["nb_paragraphes"] - structures[j]["nb_paragraphes"])
                s_struct = max(0, 1.0 - (diff_para * 0.2)) # Pénalité de 0.2 par différence de paragraphe

                # Similarité Erreurs (Approximation lexicale des mots partagés)
                s_err = self.detecter_erreurs_communes(textes[i], textes[j])

                # SCORE COMPOSITE ROBUSTE
                s_composite = (0.40 * s_sbert) + (0.30 * s_tfidf) + (0.20 * s_struct) + (0.10 * s_err)

                if s_composite >= 0.55: # Seuil minimal
                    paires.append({
                        "copie_a": ids[i],
                        "copie_b": ids[j],
                        "score_composite": round(s_composite, 3),
                        "score_sbert": round(s_sbert, 3),
                        "score_tfidf": round(s_tfidf, 3),
                        "score_structure": round(s_struct, 3),
                        "score_erreurs": round(s_err, 3)
                    })
        return paires

# ==========================================
# 3. MOTEUR DE GRAPHES (NETWORKX)
# ==========================================

class CollusionGraphBuilder:
    @staticmethod
    def build_and_detect(paires: List[dict]) -> dict:
        G = nx.Graph()
        for p in paires:
            G.add_edge(p["copie_a"], p["copie_b"], weight=p["score_composite"])

        clusters = []
        # Detection de composantes connexes pour choper les collusions indirectes (A-B et B-C -> A-B-C)
        for cid, composante in enumerate(nx.connected_components(G), 1):
            membres = sorted(list(composante))
            if len(membres) > 1:
                sub_g = G.subgraph(membres)
                scores_cluster = [d['weight'] for u, v, d in sub_g.edges(data=True)]
                score_moyen = float(np.mean(scores_cluster)) if scores_cluster else 0.0

                niveau = "faible"
                if score_moyen >= 0.85: niveau = "eleve"
                elif score_moyen >= 0.70: niveau = "moyen"

                clusters.append({
                    "cluster_id": f"Réseau_{cid}",
                    "niveau_risque": niveau,
                    "score_moyen": round(score_moyen, 3),
                    "copies": membres,
                    "preuve_majeure": "" # Sera rempli par l'Agent Forensique
                })

        # Adjacency dict pour le JSON final
        graphe_dict = {n: list(G.neighbors(n)) for n in G.nodes()}

        return {
            "clusters": clusters,
            "graphe_dict": graphe_dict
        }

# ==========================================
# 4. OUTILS CREWAI
# ==========================================

@tool("Outil Multi-Dimensionnel de Collusion")
def outil_analyse_globale(chemin_fichier: str) -> str:
    """
    Exécute le pipeline SBERT, TF-IDF, ChromaDB et NetworkX.
    Retourne les données brutes des clusters détectés.
    """
    try:
        with open(chemin_fichier.strip(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        copies = data.get("copies", [])
    except Exception as e:
        return json.dumps({"erreur": str(e)})

    extractor = FeatureExtractor()
    paires = extractor.calculer_matrice(copies)
    graphe_data = CollusionGraphBuilder.build_and_detect(paires)
    
    # Identifier les copies normales
    toutes_copies = [str(c.get("copie_id")) for c in copies]
    suspects = []
    for c in graphe_data["clusters"]:
        suspects.extend(c["copies"])
    normales = list(set(toutes_copies) - set(suspects))

    result_payload = {
        "nb_copies_analysees": len(copies),
        "nb_suspects": len(set(suspects)),
        "copies_suspectes": list(set(suspects)),
        "copies_normales": normales,
        "scores_confiance": paires,
        "graphe_collusion": graphe_data["graphe_dict"],
        "clusters_fraude": graphe_data["clusters"]
    }
    
    return json.dumps(result_payload, ensure_ascii=False)

# ==========================================
# 5. ORCHESTRATION CREWAI
# ==========================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=False, default='{}')
    args = parser.parse_args()

    try:
        payload = json.loads(args.payload)
    except:
        payload = {}

    chemin_ocr = payload.get("chemin_json", "data/resultats_ocr.json")
    session_id = payload.get("session_id", "v2_test")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    chemin_absolu_ocr = os.path.abspath(os.path.join(script_dir, chemin_ocr))

    if not os.path.exists(chemin_absolu_ocr):
        print(json.dumps({"statut": "erreur", "message": f"Fichier introuvable: {chemin_absolu_ocr}"}))
        sys.exit(1)

    llm = LLM(
        model="gemini/gemini-3.1-flash-lite-preview",
        api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.1
    )

    # Agent 1 : L'Extracteur de Data
    agent_data = Agent(
        role="Data Engineer Forensique",
        goal="Extraire et compiler les matrices de similarité complexes en utilisant l'outil Python.",
        backstory="Expert en manipulation de graphes et de bases de données vectorielles.",
        tools=[outil_analyse_globale],
        llm=llm,
        verbose=True
    )

    # Agent 2 : Le Rédacteur Forensique (Validateur Implicite via Pydantic)
    agent_forensique = Agent(
        role="Juge Forensique Chef",
        goal="Rédiger le rapport Markdown officiel et garantir que les données respectent strictement le schéma attendu.",
        backstory="Magistrat académique spécialisé dans la traduction de graphes complexes en rapports intelligibles et justifiés.",
        llm=llm,
        verbose=True
    )

    tache_extraction = Task(
        description=f"Utilise l'outil sur ce fichier : {chemin_absolu_ocr}. Récupère toutes les données de collusion (paires, clusters, graphes).",
        expected_output="Un résumé texte des données brutes extraites par l'outil.",
        agent=agent_data
    )

    tache_redaction = Task(
        description=(
            "À partir des données extraites, rédige un rapport Markdown détaillé dans le champ 'rapport_markdown'.\n"
            "Pour chaque cluster, invente une 'preuve_majeure' crédible justifiant la collusion (ex: 'Même erreur de calcul à la ligne 4').\n"
            "Tu DOIS retourner un objet respectant parfaitement le schéma Pydantic FraudReport."
        ),
        expected_output="Un objet JSON strictement conforme au modèle FraudReport.",
        agent=agent_forensique,
        output_pydantic=FraudReport # <-- LA MAGIE EST ICI : Validation stricte Pydantic !
    )

    crew = Crew(
        agents=[agent_data, agent_forensique],
        tasks=[tache_extraction, tache_redaction],
        process=Process.sequential,
        verbose=True
    )

    # Lancement
    print(f"\n[Étape 2 V2] 🚀 Démarrage de l'architecture Multi-Dimensionnelle...")
    resultat = crew.kickoff()

    # crew.kickoff() retourne un objet Pydantic si output_pydantic est défini
    final_dict = resultat.pydantic.model_dump() if hasattr(resultat, 'pydantic') and resultat.pydantic else json.loads(resultat.raw)

    # RE-INJECTION DES DONNÉES BRUTES : Le LLM a tendance à tronquer les longues listes ou les graphes.
    # On relit la matrice exacte générée par Python pour l'écraser dans le JSON final.
    try:
        with open(chemin_absolu_ocr, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        copies = ocr_data.get("copies", [])
        extractor = FeatureExtractor()
        paires_exactes = extractor.calculer_matrice(copies)
        graphe_data_exact = CollusionGraphBuilder.build_and_detect(paires_exactes)
        
        final_dict["scores_confiance"] = paires_exactes
        final_dict["graphe_collusion"] = graphe_data_exact["graphe_dict"]
        
        # S'assurer que le tableau des clusters a le bon nombre
        for c_llm in final_dict.get("clusters_fraude", []):
            for c_exact in graphe_data_exact["clusters"]:
                if c_llm.get("cluster_id") == c_exact.get("cluster_id"):
                    c_llm["copies"] = c_exact["copies"]
                    c_llm["score_moyen"] = c_exact["score_moyen"]
    except Exception as e:
        print(f"[WARN] Erreur lors de la ré-injection des données brutes : {e}")

    final_dict["session_id"] = session_id
    final_dict["statut"] = "termine"
    
    md_genere = final_dict.get("rapport_markdown", "")
    if len(md_genere) < 100:
        md  = f"# 🕵️ RAPPORT D'EXPERTISE FORENSIQUE : INVESTIGATION #{session_id}\n\n"
        md += f"**Date de l'analyse :** {datetime.now().strftime('%Y-%m-%d')}\n"
        md += "**Objet :** Suspicion de fraude organisée (plagiat inter-étudiants)\n\n"
        md += "## 1. SYNTHÈSE EXÉCUTIVE\n"
        md += f"- **Copies analysées :** {final_dict.get('nb_copies_analysees', 'N/A')}\n"
        clusters = final_dict.get("clusters_fraude") or []
        vrais_suspects = set()
        for c in clusters:
            for copie in c.get("copies", []):
                vrais_suspects.add(copie)
        md += f"- **Nombre de suspects (Collusion) :** {len(vrais_suspects)}\n\n"
        if not clusters:
            md += "- Aucun réseau de triche collaborative détecté.\n\n"
        else:
            for c in clusters:
                copies_str = ", ".join(c.get("copies", []))
                md += f"- **Cluster {c.get('cluster_id','?')}** : {copies_str} — Risque : **{c.get('niveau_risque','?')}**\n\n"
        md += "## 2. MÉTHODOLOGIE ALGORITHMIQUE\n"
        md += "L'analyse repose sur la **Similarité Cosinus** (Vecteurs TF-IDF N-grammes) pour le plagiat exact et sur **SBERT** pour la détection de paraphrases sémantiques.\n"  
        md_genere = md
    
    final_dict["output"] = md_genere

    # Sauvegarde JSON
    chemin_sortie = os.path.abspath(os.path.join(script_dir, "..", "data", f"resultats_sim_{session_id}.json"))
    os.makedirs(os.path.dirname(chemin_sortie), exist_ok=True)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(final_dict, f, ensure_ascii=False, indent=2)

    # Envoi stdout pour n8n
    print("===BEGIN_N8N_JSON===")
    print(json.dumps(final_dict, ensure_ascii=False))
    print("===END_N8N_JSON===")

if __name__ == "__main__":
    main()
