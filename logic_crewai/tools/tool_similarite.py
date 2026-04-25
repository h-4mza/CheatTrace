import json
import numpy as np
from crewai.tools import tool

# Global model cache to avoid reloading on every tool call
_sbert_model = None

def get_sbert_model():
    global _sbert_model
    if _sbert_model is None:
        from sentence_transformers import SentenceTransformer
        # Utilisation d'un modèle multilingue performant pour le Français
        _sbert_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _sbert_model

@tool("Outil de Calcul de Similarite SBERT et TF-IDF")
def outil_similarite_sbert(chemin_fichier: str) -> str:
    """
    Outil mathématique avancé pour calculer la similarité entre un lot de copies.
    Input : Le chemin absolu vers le fichier JSON des copies.
    Action : Lit le fichier et calcule une distance sémantique (SBERT Multilingue) et lexicale (TF-IDF) avec pénalité de disparité.
    Output : Un JSON listant les paires de copies suspectes.
    """
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.feature_extraction.text import TfidfVectorizer

    # 1. LECTURE DU FICHIER SUR LE DISQUE
    try:
        with open(chemin_fichier.strip(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        copies = data.get("copies", data) if isinstance(data, dict) else data
        copies_valides = [c for c in copies if isinstance(c, dict) and c.get("texte_complet") and len(c.get("texte_complet", "").strip()) > 30]
    except Exception as e:
        return f'{{"erreur": "Impossible de lire le fichier {chemin_fichier} : {str(e)}"}}'

    ids = [c["copie_id"] for c in copies_valides]
    textes = [c["texte_complet"].lower() for c in copies_valides]
    n = len(copies_valides)

    if n < 2:
        return '{"paires_suspectes": []}'

    # 2. COUCHE SÉMANTIQUE (SBERT Multilingue)
    try:
        model = get_sbert_model()
        embeds = model.encode(textes, show_progress_bar=False)
        mat_sbert = cosine_similarity(embeds)
        np.fill_diagonal(mat_sbert, 0)
    except Exception as e:
        print(f"Attention: Erreur SBERT ({e}).")
        mat_sbert = np.zeros((n, n))

    # 3. COUCHE LEXICALE (TF-IDF - Ajusté pour le Français)
    try:
        # Suppression de stop_words='english' car nous analysons des copies en français
        vectorizer = TfidfVectorizer(ngram_range=(1, 3), max_df=0.95, min_df=1)
        tfidf_matrix = vectorizer.fit_transform(textes)
        mat_tfidf = cosine_similarity(tfidf_matrix)
        np.fill_diagonal(mat_tfidf, 0)
    except Exception as e:
        print(f"Attention: Erreur TF-IDF ({e}).")
        mat_tfidf = np.zeros((n, n))

    # 4. FUSION ET PÉNALITÉ DE DISPARITÉ (LENGTH PENALTY)
    paires = []
    for i in range(n):
        for j in range(i+1, n):
            s_sbert = float(mat_sbert[i][j])
            s_tfidf = float(mat_tfidf[i][j])
            
            # La similarité globale est le max des deux (soit copié-collé exact, soit paraphrasé)
            s_base = max(s_sbert, s_tfidf) * 0.7 + ((s_sbert + s_tfidf) / 2) * 0.3
            
            # Pénalité de disparité de taille
            len_i = len(textes[i])
            len_j = len(textes[j])
            ratio_taille = min(len_i, len_j) / max(len_i, len_j)
            
            # Si une copie est plus de 2x plus grande que l'autre, on applique une pénalité exponentielle
            penalty = 1.0
            if ratio_taille < 0.5:
                penalty = ratio_taille + 0.5 # Ex: ratio 0.2 -> penalty 0.7. (score réduit de 30%)
                
            s_final = s_base * penalty
            
            if s_final > 0.35: # Seuil minimum de pertinence
                paires.append({
                    "copie_a": ids[i],
                    "copie_b": ids[j],
                    "score_sbert": round(s_sbert, 3),
                    "score_tfidf": round(s_tfidf, 3),
                    "score_combine": round(s_final, 3)
                })

    paires.sort(key=lambda x: -x["score_combine"])
    return json.dumps({"paires_suspectes": paires}, ensure_ascii=False)

@tool("Outil de Clustering de Fraude")
def outil_clustering(paires_json_str: str) -> str:
    """
    Outil d'analyse de réseau (Community Detection).
    Input : Le JSON généré par l'Outil de Calcul de Similarite (contenant 'paires_suspectes').
    Action : Utilise l'algorithme de Louvain pour trouver des communautés denses de fraudeurs sans faux positifs.
    Output : Un JSON listant les clusters de fraude organisée et le seuil utilisé.
    """
    import networkx as nx
    from networkx.algorithms import community

    try:
        data = json.loads(paires_json_str)
        paires = data.get("paires_suspectes", [])
    except Exception as e:
        return f'{{"erreur": "Impossible de lire les paires : {str(e)}"}}'

    if not paires:
        return '{"seuil_utilise": 0.0, "clusters": [], "message": "Aucune paire suspecte."}'

    # 1. Filtrage dynamique (Garder uniquement le top)
    scores = [p["score_combine"] for p in paires]
    moyenne = float(np.mean(scores))
    ecart_type = float(np.std(scores))
    
    # Seuil dynamique de confiance
    seuil = min(moyenne + (1.0 * ecart_type), 0.80)

    # 2. Modélisation du Graphe
    G = nx.Graph()
    for p in paires:
        if p["score_combine"] >= seuil:
            G.add_edge(p["copie_a"], p["copie_b"], weight=p["score_combine"])

    if G.number_of_edges() == 0:
        return json.dumps({
            "seuil_utilise_statistique": round(seuil, 3),
            "nb_clusters_trouves": 0,
            "clusters": []
        }, ensure_ascii=False)

    # 3. Extraction par Détection de Communautés (Algorithme de Louvain / Modularity)
    # Empêche l'effet de chaîne des composantes connexes.
    clusters_out = []
    
    # On utilise Louvain Communities s'il est dispo, sinon on fallback sur connected_components propre
    try:
        if hasattr(nx.community, 'louvain_communities'):
            communautes = list(nx.community.louvain_communities(G, weight='weight'))
        else:
            communautes = list(nx.community.greedy_modularity_communities(G, weight='weight'))
            
        for cid, com in enumerate(communautes, 1):
            membres = sorted(list(com))
            if len(membres) > 1:
                # Filtrage supplémentaire : Vérifier que le sous-graphe est vraiment dense (Cliques)
                sub_g = G.subgraph(membres)
                densite = nx.density(sub_g)
                
                # Si la communauté a été formée juste par un lien très faible, on la skip ou la re-sépare
                if densite < 0.3 and len(membres) > 3:
                    continue # On ignore les chaînes bizarres très éparses
                
                scores_cluster = [d['weight'] for u, v, d in sub_g.edges(data=True)]
                score_moyen = float(np.mean(scores_cluster)) if scores_cluster else 0.0
                niveau = "eleve" if score_moyen >= 0.80 else "modere"

                clusters_out.append({
                    "cluster_id": cid,
                    "copies": membres,
                    "score_moyen": round(score_moyen, 3),
                    "niveau_risque": niveau
                })
    except Exception as e:
        # Fallback de sécurité si les communautés échouent
        for cid, composante in enumerate(nx.connected_components(G), 1):
            if len(composante) > 1:
                membres = sorted(list(composante))
                clusters_out.append({
                    "cluster_id": cid,
                    "copies": membres,
                    "score_moyen": 0.0,
                    "niveau_risque": "modere"
                })

    return json.dumps({
        "seuil_utilise_statistique": round(seuil, 3),
        "nb_clusters_trouves": len(clusters_out),
        "clusters": clusters_out
    }, ensure_ascii=False)