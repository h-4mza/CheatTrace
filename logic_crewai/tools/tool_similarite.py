import json
import numpy as np
from crewai.tools import tool

@tool("Outil de Calcul de Similarite SBERT et MinHash")
def outil_similarite_sbert(chemin_fichier: str) -> str:
    """
    Outil mathématique pour calculer la similarité entre un lot de copies.
    Input : Le chemin absolu vers le fichier JSON des copies.
    Action : Lit le fichier et calcule la distance sémantique.
    Output : Un JSON listant les paires de copies suspectes.
    """
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    from datasketch import MinHash

    # 1. LECTURE DU FICHIER SUR LE DISQUE
    try:
        with open(chemin_fichier.strip(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        copies = data.get("copies", data) if isinstance(data, dict) else data
        copies_valides = [c for c in copies if isinstance(c, dict) and c.get("texte_complet") and len(c.get("texte_complet", "").strip()) > 30]
    except Exception as e:
        return f'{{"erreur": "Impossible de lire le fichier {chemin_fichier} : {str(e)}"}}'

    ids = [c["copie_id"] for c in copies_valides]
    textes = [c["texte_complet"] for c in copies_valides]
    n = len(copies_valides)

    if n < 2:
        return '{"paires_suspectes": []}'

    # 2. COUCHE SÉMANTIQUE SBERT (Le reste du code ne change pas)
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2") 
        embeds = model.encode(textes, show_progress_bar=False)
        mat_sbert = cosine_similarity(embeds)
        np.fill_diagonal(mat_sbert, 0)
    except Exception as e:
        print(f"Attention: Erreur SBERT ({e}).")
        mat_sbert = np.zeros((n, n))

    def get_shingles(texte, k=5):
        mots = texte.lower().split()
        return set(" ".join(mots[i:i+k]) for i in range(max(1, len(mots)-k+1)))

    minhashes = []
    for texte in textes:
        m = MinHash(num_perm=128)
        for shingle in get_shingles(texte):
            m.update(shingle.encode("utf-8"))
        minhashes.append(m)

    paires = []
    for i in range(n):
        for j in range(i+1, n):
            s_sbert = float(mat_sbert[i][j])
            s_minhash = minhashes[i].jaccard(minhashes[j])
            
            # On donne beaucoup plus de poids au sens (SBERT) qu'aux mots exacts (MinHash)
            # pour détecter la reformulation d'idées (triche intelligente)
            s_combine = (0.80 * s_sbert) + (0.20 * s_minhash)
            
            # Seuil abaissé pour capter des reformulations plus larges
            if s_combine > 0.30:
                paires.append({
                    "copie_a": ids[i],
                    "copie_b": ids[j],
                    "score_sbert": round(s_sbert, 3),
                    "score_minhash": round(s_minhash, 3),
                    "score_combine": round(s_combine, 3)
                })

    paires.sort(key=lambda x: -x["score_combine"])
    return json.dumps({"paires_suspectes": paires}, ensure_ascii=False)

@tool("Outil de Clustering de Fraude")
def outil_clustering(paires_json_str: str) -> str:
    """
    Outil d'analyse de réseau.
    Input : Le JSON généré par l'Outil de Calcul de Similarite (contenant 'paires_suspectes').
    Action : Calcule un seuil adaptatif de triche et regroupe les fraudeurs en clusters.
    Output : Un JSON listant les clusters de fraude organisée et le seuil utilisé.
    """
    import networkx as nx

    try:
        data = json.loads(paires_json_str)
        paires = data.get("paires_suspectes", [])
    except Exception as e:
        return f'{{"erreur": "Impossible de lire les paires : {str(e)}"}}'

    if not paires:
        return '{"seuil_utilise": 0.0, "clusters": [], "message": "Aucune paire suspecte."}'

    # 1. Calcul du Seuil Adaptatif (Le bruit de fond de la classe)
    scores = [p["score_combine"] for p in paires]
    moyenne = float(np.mean(scores))
    ecart_type = float(np.std(scores))
    
    # Seuil assoupli : moyenne + 1 ecart-type (au lieu de 2) pour lier plus facilement les fraudeurs qui reformulent
    seuil = min(moyenne + (1.0 * ecart_type), 0.85)

    # 2. Modélisation du Graphe
    G = nx.Graph()
    for p in paires:
        if p["score_combine"] >= seuil:
            G.add_edge(p["copie_a"], p["copie_b"], weight=p["score_combine"])

    # 3. Extraction des Composantes Connexes (Les Clusters)
    clusters_out = []
    for cid, composante in enumerate(nx.connected_components(G), 1):
        if len(composante) > 1:
            membres = sorted(list(composante))
            
            # On récupère les scores moyens au sein de ce cluster
            scores_cluster = [
                p["score_combine"] for p in paires 
                if p["copie_a"] in membres and p["copie_b"] in membres
            ]
            score_moyen = float(np.mean(scores_cluster)) if scores_cluster else 0.0
            niveau = "eleve" if score_moyen >= 0.80 else "modere"

            clusters_out.append({
                "cluster_id": cid,
                "copies": membres,
                "score_moyen": round(score_moyen, 3),
                "niveau_risque": niveau
            })

    return json.dumps({
        "seuil_utilise_statistique": round(seuil, 3),
        "nb_clusters_trouves": len(clusters_out),
        "clusters": clusters_out
    }, ensure_ascii=False)