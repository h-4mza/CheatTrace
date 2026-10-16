<div align="center">

<img src="docs/assets/logo.png" alt="CheatTrace" width="260">

# CheatTrace

**Plateforme de confiance numérique pour la détection de fraude académique basée sur l'IA générative**

Analyse forensique des copies d'examen manuscrites : OCR, détection de texte généré par IA et repérage des coalitions de fraude entre étudiants.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy-4169E1?logo=postgresql&logoColor=white)
![CrewAI](https://img.shields.io/badge/CrewAI-multi--agents-FF5A50)
![Gemini](https://img.shields.io/badge/Google-Gemini-8E75B2?logo=googlegemini&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-orchestration-EA4B71?logo=n8n&logoColor=white)

*Projet de Fin d'Année — Filière CCN, 2ᵉ année — ENSA El Jadida (Université Chouaïb Doukkali) — 2025/2026*

</div>

---

## Sommaire

- [Le problème](#-le-problème)
- [La solution](#-la-solution)
- [Aperçu](#-aperçu)
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Comment ça marche](#-comment-ça-marche)
- [Pile technologique](#-pile-technologique)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Structure du dépôt](#-structure-du-dépôt)
- [Limites et perspectives](#-limites-et-perspectives)
- [Équipe](#-équipe)

---

## 🎯 Le problème

Les outils d'IA générative (ChatGPT, Gemini, Claude…) ont introduit de nouvelles formes de fraude, **y compris dans les examens présentiels sur copie manuscrite** :

- photo de l'énoncé envoyée à une IA ou à un complice externe ;
- réponses générées puis partagées dans un groupe WhatsApp ;
- répartition des questions entre plusieurs étudiants ;
- pré-mémorisation de réponses IA après une fuite de l'énoncé.

Les détecteurs existants (Turnitin, Copyleaks, Originality.ai…) travaillent sur du texte numérique, analysent les copies une par une et donnent un score peu explicable. Aucun ne traite les copies manuscrites ni ne détecte les **coalitions** entre étudiants.

## 💡 La solution

CheatTrace permet à un enseignant de déposer les copies scannées d'un examen et d'obtenir un **rapport forensique explicable** :

| Mode d'analyse | Question posée | Résultat |
|---|---|---|
| **Singulière** | Cette copie a-t-elle été écrite par une IA ? | Score de suspicion, classification `HUMAIN` / `HYBRIDE` / `PROBABLEMENT_IA`, extraits suspects |
| **Collaborative** | Des copies se ressemblent-elles anormalement ? | Paires suspectes, clusters de fraude, graphe de collusion |
| **Complète** | Les deux à la fois | Verdict croisé du Juge Forensique pour chaque suspect |

La plateforme reste un **outil d'aide à la décision** : elle fournit des preuves (scores, dimensions, extraits) mais la décision disciplinaire reste au jury.

## 📸 Aperçu

<table>
  <tr>
    <td width="50%"><img src="docs/assets/dashboard.jpg" alt="Tableau de bord"><p align="center"><sub>Tableau de bord enseignant</sub></p></td>
    <td width="50%"><img src="docs/assets/rapport.jpg" alt="Rapport forensique"><p align="center"><sub>Rapport forensique multi-couches</sub></p></td>
  </tr>
  <tr>
    <td colspan="2"><img src="docs/assets/investigations.jpg" alt="Registre des investigations"><p align="center"><sub>Registre des investigations</sub></p></td>
  </tr>
</table>

## ✨ Fonctionnalités

- **OCR manuscrit multimodal** avec Google Gemini : transcription de la copie et extraction de l'identifiant étudiant en une seule requête, sortie JSON structurée, relance automatique (*exponential backoff*).
- **Détection d'IA sur 7 dimensions stylométriques** notées par le LLM puis **recalculées de façon déterministe en Python** (le score du LLM n'est jamais utilisé tel quel).
- **Détection de collusion** : similarité sémantique (SBERT), lexicale (TF-IDF), signatures d'erreurs communes et structure des paragraphes.
- **Clustering des coalitions** par graphe (NetworkX) en trois passes : noyaux forts, expansion, fusion.
- **Mémoire inter-sessions** (ChromaDB) pour repérer une copie qui ressemble à celle d'une promotion précédente.
- **Rapports « zéro hallucination »** : Python calcule tous les chiffres, le LLM ne fait que la rédaction, puis Python réinjecte les données exactes.
- **Gestion des rôles** Administrateur / Professeur, modules pédagogiques, historique des investigations, suivi du statut en temps réel.
- **Orchestration asynchrone** via un workflow n8n, avec **alerte email au professeur** quand des suspects sont détectés.

## 🏗️ Architecture

```mermaid
flowchart LR
    P([Enseignant]) -->|copies scannées| W[Flask<br/>web/]
    W <--> DB[(PostgreSQL)]
    W -->|webhook| N[n8n<br/>workflow_fraude.json]
    N --> O[OCR Gemini<br/>ocr_batch.py]
    O --> S{Type<br/>d'analyse}
    S -->|singulière| A1[Expert NLP<br/>step1_nlp.py]
    S -->|collaborative| A2[Analyste collusion<br/>step2_similarite.py]
    S -->|complète| A1 & A2
    A1 & A2 --> J[Juge Forensique<br/>step3_juge.py]
    J --> R[Rapport Markdown]
    R --> W
```

Le projet est organisé en trois pôles :

| Pôle | Dossier | Rôle |
|---|---|---|
| **Web** | `web/` | Application Flask : authentification, modules, investigations, dashboards (Jinja2 + Tailwind) |
| **Intelligence artificielle** | `logic_crewai/` | Agents CrewAI, OCR, analyse NLP, similarité, juge et génération des rapports |
| **Orchestration** | `n8n/` | Workflow n8n qui enchaîne les scripts selon le type d'investigation |

### Workflow n8n

<img src="docs/assets/workflow-n8n.png" alt="Workflow n8n">

| Étape | Nœud | Rôle |
|---|---|---|
| 1 | **Webhook — Réception des scans** | Reçoit en `POST` les copies et les métadonnées envoyées par Flask |
| 2 | **Sauvegarde des images** | Enregistre les copies dans le dossier de l'investigation |
| 3 | **OCR — Extraction texte** | Lance `ocr_batch.py` (Gemini) |
| 4 | **Vérification OCR** | Contrôle que le texte a bien été extrait |
| 5 | **CrewAI — Investigation** | Exécute le pipeline multi-agents (NLP, similarité, juge) |
| 6 | **Parse résultat CrewAI** | Récupère le verdict et le rapport |
| 7 | **Y a-t-il des suspects ?** | Si oui : **email d'alerte au professeur** + réponse « Succès » ; sinon : réponse « Aucune fraude » |

Le déclencheur manuel (*When clicking 'Execute workflow'*) permet de tester le workflow directement depuis n8n.

## 🔬 Comment ça marche

### 1. Analyse singulière — détection d'IA

Le LLM note chaque copie de 0 (humain) à 10 (IA) sur sept dimensions, après un raisonnement guidé (*Chain of Thought*). Python recalcule ensuite le score avec les poids suivants et applique des pénalités logiques (ex. structure parfaite **et** fautes « trop humaines » = signe de camouflage) :

| Dimension | Poids |
|---|---:|
| Structure argumentative | 18 % |
| Fluidité et cohérence | 18 % |
| Imperfections humaines | 17 % |
| Régularité stylistique | 15 % |
| Adéquation sémantique | 12 % |
| Richesse lexicale | 10 % |
| Répétitions | 10 % |

Le score final est traduit en niveau de risque **Faible / Modéré / Élevé**, accompagné des extraits de texte qui le justifient.

### 2. Analyse collaborative — détection de collusion

Chaque paire de copies reçoit un score composite :

```
S = 0.35·SBERT + 0.25·TF-IDF + 0.25·Erreurs communes + 0.15·Structure + bonus signatures rares
```

- **SBERT** (`paraphrase-multilingual-mpnet-base-v2`) détecte la paraphrase même avec des mots différents.
- **TF-IDF** sur n-grammes de caractères, robuste aux erreurs d'OCR ; `max_df = 0.6` écarte le vocabulaire propre au sujet.
- **Erreurs communes** : séquences rares partagées par deux copies seulement — l'indice le plus discriminant.
- **Structure** : corrélation de Pearson sur la longueur des paragraphes (plan commun).

Les paires suspectes forment un graphe ; les coalitions sont extraites en trois passes (noyaux ≥ 0.80, expansion ≥ 0.65 avec SBERT > 0.80, fusion des clusters proches).

### 3. Juge Forensique — verdict final

En mode complet, Python fusionne les suspects des deux analyses (union sans doublon), puis l'agent Juge rédige un verdict motivé pour chacun. Le rapport final contient l'en-tête et le verdict croisé, les fiches individuelles NLP, puis le rapport collaboratif (clusters, matrices).

## 🧰 Pile technologique

| Composant | Technologie |
|---|---|
| Langage | Python 3.13 |
| Backend web | Flask, Flask-Login, Flask-SQLAlchemy |
| Base de données | PostgreSQL |
| Interface | HTML, Jinja2, Tailwind CSS |
| Multi-agents | CrewAI |
| Modèle multimodal / LLM | Google Gemini (`gemini-3.1-flash-lite-preview`) |
| NLP | Sentence-Transformers (SBERT), scikit-learn (TF-IDF) |
| Graphes | NetworkX (Louvain) |
| Mémoire vectorielle | ChromaDB |
| Orchestration | n8n |

## 🛠️ Installation

### Prérequis

- Python 3.11+ (développé avec 3.13)
- PostgreSQL
- [n8n](https://n8n.io/) (local, port 5678 par défaut)
- Une clé API Google Gemini ([Google AI Studio](https://aistudio.google.com/))

### 1. Cloner et créer l'environnement

```bash
git clone https://github.com/h-4mza/CheatTrace.git
cd CheatTrace

python -m venv env
# Windows
.\env\Scripts\activate
# Linux / macOS
source env/bin/activate

pip install -r requirements.txt
```

### 2. Configurer `.env`

Créez un fichier `.env` à la racine :

```env
GEMINI_API_KEY="votre_cle_gemini"
DATABASE_URL="postgresql://postgres:mot_de_passe@localhost:5432/forensique_db"
SECRET_KEY="une_cle_secrete_aleatoire"
# Optionnel (valeur par défaut ci-dessous)
N8N_WEBHOOK_URL="http://localhost:5678/webhook/upload-copies"
```

### 3. Préparer le stockage et n8n

- Créez le dossier de stockage des copies : `C:\Forensic_Storage` (chemin défini dans `web/app.py`, à adapter hors Windows).
- Dans n8n, importez `n8n/workflow_fraude.json` et activez-le. Le webhook attendu est `/webhook/upload-copies`.

### 4. Lancer

```bash
python run.py
```

Au premier lancement, les tables sont créées et un compte administrateur est ajouté. L'application est disponible sur **http://localhost:5001**.

| Compte | Identifiants |
|---|---|
| Administrateur | `admin` / `admin123` |
| Professeur de démo | `prof_demo` / `prof123` (créé par `python setup_db.py` ou `python create_prof.py`) |

> ⚠️ Changez ces mots de passe et la `SECRET_KEY` avant toute utilisation réelle.

## 🚀 Utilisation

1. Connectez-vous en tant que professeur.
2. Créez un **module** (matière).
3. Lancez une **nouvelle investigation** : titre, question d'examen, type d'analyse (singulière, collaborative ou complète), puis déposez les copies scannées (JPEG, PNG, WebP, BMP).
4. Suivez le statut sur le tableau de bord (*En attente → En traitement → Terminé*).
5. Consultez le **rapport forensique** : verdicts, scores par dimension, extraits suspects et clusters.

Les scripts du pipeline peuvent aussi être lancés seuls, par exemple :

```bash
python logic_crewai/ocr_batch.py --dossier chemin/vers/copies --sortie data/resultats_ocr.json --question "Énoncé de l'examen"
```

Pour tester l'appel Flask → n8n sans passer par l'interface :

```bash
python seed_test.py       # crée une investigation de test en base
python test_reel_n8n.py   # envoie des copies au webhook n8n
```

## 📁 Structure du dépôt

```
.
├── run.py                    # Point d'entrée : init de la base + serveur Flask
├── setup_db.py               # Création de la base et des comptes par défaut
├── requirements.txt
├── web/                      # Application Flask
│   ├── app.py                # Routes (auth, modules, investigations, admin, API)
│   ├── models.py             # Modèles SQLAlchemy
│   ├── pipeline_runner.py    # Envoi des copies au webhook n8n
│   └── templates/            # Vues Jinja2
├── logic_crewai/             # Moteur forensique
│   ├── ocr_batch.py          # OCR/HTR Gemini
│   ├── step1_nlp.py          # Analyse singulière (détection IA)
│   ├── step2_similarite.py   # Analyse collaborative (collusion)
│   ├── step3_juge.py         # Fusion et verdict final
│   ├── agents.py / tasks.py  # Définition des agents et tâches CrewAI
│   └── tools/                # Outils : OCR, détection IA, similarité, rapport
├── n8n/workflow_fraude.json  # Workflow à importer dans n8n
├── data/                     # Exemples de résultats JSON
├── dashboard/                # Exemples de rapports générés
└── docs/assets/              # Images du README
```

## 🧭 Limites et perspectives

**Limites observées**

- Les réponses courtes donnent peu de signal stylométrique.
- Une copie humaine très structurée peut ressembler à un texte IA ; les textes hybrides reformulés restent difficiles à trancher.
- La qualité dépend de la lisibilité de l'écriture et du scan.
- Certains sujets appellent naturellement des réponses proches, ce qui peut gonfler la similarité.

**Perspectives**

- Modèles OCR/HTR plus performants.
- Amélioration de la détection collaborative.
- Modèles spécialisés sur le domaine académique.
- Déploiement en environnement universitaire réel.

## 👥 Équipe

Réalisé par **Hayat Bouchra**, **Alioua Malak Elferdouas** et **Bahalloul Hamza**,
sous l'encadrement du **Pr. Abdelhak Aqqal**.

École Nationale des Sciences Appliquées d'El Jadida — Département Télécommunications, Réseaux et Informatique — Filière Cybersécurité et Confiance Numérique (CCN).
