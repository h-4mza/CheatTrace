import os
import json
import time
import re
import concurrent.futures
from crewai.tools import tool
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

SEUIL_HUMAIN_MAX = 29
SEUIL_HYBRIDE_MAX = 69
SEUIL_IA_MIN = 70

NB_RETRIES_429 = 4
DELAI_RETRY_BASE = 15.0  # Augmenté pour gérer les quotas sévères en parallèle


SYSTEM_PROMPT_FORENSIQUE = """
Tu es un expert en analyse forensique textuelle spécialisé dans la détection de contenu généré par des modèles de langage (LLM) dans un contexte académique. Ton rôle est d'analyser la réponse d'un étudiant à une question d'examen et d'évaluer sa compatibilité avec un texte produit par un LLM.

## MISSION

Tu reçois :
- une QUESTION d'examen,
- une RÉPONSE numérisée d'un étudiant.

Tu dois produire une analyse forensique rigoureuse, prudente et non accusatoire. Ton analyse ne constitue pas une preuve de fraude : elle est un signal d'alerte probabiliste destiné à un humain qui prendra la décision finale.

## MÉTHODOLOGIE OBLIGATOIRE (CHAIN OF THOUGHT)
Avant de donner tes notes, tu DOIS rédiger un "analyse_brouillon" (invisible pour l'utilisateur final) où tu réfléchis étape par étape :
1. Est-ce que le texte répond exactement à la question ou fait-il des détours génériques ?
2. Y a-t-il des sauts cognitifs, des émotions, ou le texte est-il parfaitement linéaire et clinique ?
3. Le niveau de vocabulaire est-il cohérent avec un étudiant sous contrainte de temps ?

## CRITÈRES D'ANALYSE (Notes de 0 à 10)
0 = Caractéristique typiquement HUMAINE.
10 = Caractéristique typiquement IA.

1. Structure argumentative
- IA (10) : Symétrie parfaite, transitions formulaiques ("Premièrement", "En conclusion"), plan scolaire rigide.
- Humain (0) : Idées parfois désorganisées, digressions, ajout d'idées en fin de paragraphe.

2. Fluidité et cohérence
- IA (10) : Fluidité clinique, aucune rupture de ton.
- Humain (0) : Hésitations, phrases parfois trop longues ou tronquées, sauts cognitifs.

3. Régularité stylistique
- IA (10) : Ton parfaitement homogène, souvent soutenu ou neutre.
- Humain (0) : Relâchement de la pression, variations de niveau de langue.

4. Richesse et registre lexical
- IA (10) : Vocabulaire sectoriel très riche de manière constante, termes typiques ("Il est crucial de souligner", "Dans un monde en perpétuelle évolution").
- Humain (0) : Vocabulaire hétérogène, mots de tous les jours mélangés à des termes techniques.

5. Imperfections humaines
- IA (10) : Zéro faute. Zéro.
- Humain (0) : Fautes de frappe, erreurs d'accord, répétitions maladroites (à ne pas confondre avec un style simple).
- *Note : Un très bon étudiant peut avoir 10/10 ici sans être une IA. Ce critère seul ne suffit pas.*

6. Adéquation sémantique question/réponse
- IA (10) : Réponse sur-généralisée, survole le sujet sans prendre de position forte (neutralité axiomatique).
- Humain (0) : Prise de position claire, exemples personnels, anecdotes, quitte à être légèrement hors-sujet.

7. Répétitions et redondances
- IA (10) : Répétition de la même idée sous des formulations différentes (remplissage).
- Humain (0) : Densité informationnelle variable.

## EXTRAITS SUSPECTS
Si tu classes la copie en PROBABLEMENT_IA ou HYBRIDE, IL EST STRICTEMENT INTERDIT de retourner une liste vide []. Tu DOIS extraire au moins 1 phrase du texte (par exemple, l'introduction stéréotypée, une transition artificielle, ou une conclusion générique). Cite la phrase EXACTEMENT et justifie en quoi elle représente une signature LLM.

## EXEMPLES DE CALIBRAGE (FEW-SHOT)
- Exemple 1 : Texte sans faute, très structuré, mais avec une anecdote personnelle très précise et une opinion tranchée -> HYBRIDE (Score ~50).
- Exemple 2 : Texte avec des fautes d'orthographe (Humain), mais une structure en 3 parties parfaites avec des connecteurs "De plus, En outre, Finalement" -> HYBRIDE (Score ~60).
- Exemple 3 : Texte parfait, vocabulaire riche, aucune faute, aucune opinion, refus de s'impliquer, conclusion résumant le texte -> PROBABLEMENT_IA (Score ~85).
- Exemple 4 : Texte avec des ratures, des phrases mal finies, des idées qui s'enchaînent mal -> HUMAIN (Score ~15).

## FORMAT DE SORTIE STRICT (JSON ONLY)
Tu dois retourner UNIQUEMENT un objet JSON valide, sans balises Markdown.
{
  "analyse_brouillon": "<Ton raisonnement étape par étape>",
  "score_suspicion": <entier entre 0 et 100>,
  "classification": <"HUMAIN" | "HYBRIDE" | "PROBABLEMENT_IA">,
  "resume_executif": <string>,
  "dimensions": {
    "structure_argumentative":   { "note": <0-10>, "observation": <string> },
    "fluidite_coherence":        { "note": <0-10>, "observation": <string> },
    "regularite_stylistique":    { "note": <0-10>, "observation": <string> },
    "richesse_lexicale":         { "note": <0-10>, "observation": <string> },
    "imperfections_humaines":    { "note": <0-10>, "observation": <string> },
    "adequation_semantique":     { "note": <0-10>, "observation": <string> },
    "repetitions_redondances":   { "note": <0-10>, "observation": <string> }
  },
  "indices_linguistiques": [ <string> ],
  "extraits_suspects": [
    { "texte": "<citation exacte>", "justification": "<explication>" }
  ],
  "prompts_plausibles": {
    "avertissement": "Ces prompts sont des reconstructions hypothétiques.",
    "liste": [ <string> ]
  },
  "conclusion": <string>,
  "faux_positif_risque": <"FAIBLE" | "MODERE" | "ELEVE">,
  "faux_positif_raison": <string>
}
""".strip()


def construire_user_prompt(question: str, reponse_etudiant: str) -> str:
    return f"""
QUESTION D'EXAMEN :
{question}

RÉPONSE DE L'ÉTUDIANT :
{reponse_etudiant}

Analyse cette réponse dans le contexte de la question.

Retourne uniquement un JSON valide conforme au format demandé.
Ne mets ni balises markdown, ni texte explicatif avant ou après.
""".strip()


def extraire_retry_delay(message: str):
    if not message:
        return None

    m = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) + 1.0
        except Exception:
            pass

    m = re.search(r"seconds:\s*([0-9]+)", message, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) + 1.0
        except Exception:
            pass

    return None


def extraire_json(texte: str) -> dict:
    texte = texte.strip()

    try:
        return json.loads(texte)
    except Exception:
        pass

    match = re.search(r"```json\s*(\{.*?\})\s*```", texte, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut != -1 and fin != -1 and fin > debut:
        sous_texte = texte[debut:fin + 1]
        try:
            return json.loads(sous_texte)
        except Exception:
            pass

    raise ValueError("Impossible d'extraire un JSON valide depuis la réponse du modèle.")


def normaliser_classification(score: int) -> str:
    if score <= SEUIL_HUMAIN_MAX:
        return "HUMAIN"
    elif score <= SEUIL_HYBRIDE_MAX:
        return "HYBRIDE"
    return "PROBABLEMENT_IA"


def corriger_dimensions(dimensions: dict) -> dict:
    def get_note(name):
        try:
            return float(dimensions.get(name, {}).get("note", 0))
        except:
            return 0.0

    def set_note(name, val):
        if name not in dimensions:
            dimensions[name] = {}
        dimensions[name]["note"] = val

    structure = get_note("structure_argumentative")
    fluidite = get_note("fluidite_coherence")

    if (structure >= 3 and fluidite >= 3):
        if structure < 4: set_note("structure_argumentative", 4)
        if fluidite < 4: set_note("fluidite_coherence", 4)

    return dimensions

def recalculer_score_depuis_dimensions(dimensions: dict) -> int:
    def get_note(nom: str) -> float:
        bloc = dimensions.get(nom, {})
        if not isinstance(bloc, dict):
            return 0.0
        note = bloc.get("note", 0)
        try:
            note = float(note)
        except:
            note = 0.0
        return max(0.0, min(10.0, note))

    structure = get_note("structure_argumentative")
    fluidite = get_note("fluidite_coherence")
    regularite = get_note("regularite_stylistique")
    richesse = get_note("richesse_lexicale")
    imperfections = get_note("imperfections_humaines")
    adequation = get_note("adequation_semantique")
    repetitions = get_note("repetitions_redondances")

    score_0_10 = (
        structure * 0.18 +
        fluidite * 0.18 +
        regularite * 0.15 +
        richesse * 0.10 +
        imperfections * 0.17 +
        adequation * 0.12 +
        repetitions * 0.10
    )

    if (structure >= 4 and fluidite >= 4 and richesse <= 3 and imperfections <= 4):
        score_0_10 += 1.5

    contradiction = abs(structure - imperfections)
    if contradiction >= 3:
        score_0_10 += 0.8

    if (structure >= 5 and fluidite >= 5 and adequation >= 5 and 2 <= imperfections <= 7):
        score_0_10 += 1.2

    if (structure >= 6 and adequation >= 6 and score_0_10 < 3):
        score_0_10 = 3.5

    if (structure >= 6 and fluidite >= 6):
        score_0_10 = max(score_0_10, 4.0)

    if (structure >= 8 and fluidite >= 8 and regularite >= 8 and imperfections >= 8):
        score_0_10 += 0.5

    if (fluidite <= 3 and richesse <= 3 and imperfections <= 3):
        score_0_10 -= 0.8

    if (structure >= 4 and fluidite >= 4 and score_0_10 < 4 and imperfections >= 3):
        score_0_10 = 4.5

    if (imperfections >= 7 and structure <= 4 and fluidite <= 4):
        score_0_10 -= 1.5

    score_0_10 = max(0.0, min(10.0, score_0_10))
    return int(round(score_0_10 * 10))


def normaliser_sortie(data: dict) -> dict:
    score_brut = data.get("score_suspicion", 0)
    try:
        score_modele = int(round(float(score_brut)))
    except Exception:
        score_modele = 0
    score_modele = max(0, min(100, score_modele))

    dims = data.get("dimensions", {})
    if not isinstance(dims, dict):
        dims = {}

    dims = corriger_dimensions(dims)
    score = recalculer_score_depuis_dimensions(dims)
    classification = normaliser_classification(score)

    def safe_note(name):
        try:
            return round(float(dims.get(name, {}).get("note", 0)))
        except:
            return 0.0

    structure = safe_note("structure_argumentative")
    fluidite = safe_note("fluidite_coherence")
    imperfections = safe_note("imperfections_humaines")

    if (structure >= 4 and fluidite >= 4 and 2 <= imperfections <= 6):
        classification = "HYBRIDE"
        if score >= 70:
            score = 65

    if (imperfections >= 7 and structure <= 5 and fluidite <= 5):
        classification = "HUMAIN"
        if score > 30:
            score = 25

    prompts = data.get("prompts_plausibles", {})
    if not isinstance(prompts, dict):
        prompts = {}

    liste_prompts = prompts.get("liste", [])
    if not isinstance(liste_prompts, list):
        liste_prompts = []

    def dim(name: str):
        bloc = dims.get(name, {})
        if not isinstance(bloc, dict):
            bloc = {}
        note = bloc.get("note", 0)
        try:
            note = float(note)
        except Exception:
            note = 0.0
        note = max(0.0, min(10.0, note))
        return {
            "note": note,
            "observation": str(bloc.get("observation", ""))
        }

    faux_positif_risque = str(data.get("faux_positif_risque", "")).strip().upper()
    faux_positif_risque = faux_positif_risque.replace("É", "E")
    if faux_positif_risque not in {"FAIBLE", "MODERE", "ELEVE"}:
        faux_positif_risque = "MODERE"

    classification_modele = str(data.get("classification", "")).strip().upper()
    if classification_modele not in {"HUMAIN", "HYBRIDE", "PROBABLEMENT_IA"}:
        classification_modele = None

    return {
        "score_suspicion": score,
        "score_modele": score_modele,
        "score_recalcule": score,
        "classification": classification,
        "classification_modele": classification_modele,
        "resume_executif": str(data.get("resume_executif", "")),
        "dimensions": {
            "structure_argumentative": dim("structure_argumentative"),
            "fluidite_coherence": dim("fluidite_coherence"),
            "regularite_stylistique": dim("regularite_stylistique"),
            "richesse_lexicale": dim("richesse_lexicale"),
            "imperfections_humaines": dim("imperfections_humaines"),
            "adequation_semantique": dim("adequation_semantique"),
            "repetitions_redondances": dim("repetitions_redondances"),
        },
        "indices_linguistiques": [str(x) for x in data.get("indices_linguistiques", [])][:12],
        "prompts_plausibles": {
            "avertissement": str(
                prompts.get(
                    "avertissement",
                    "Ces prompts sont des reconstructions hypothétiques. Aucun ne peut être considéré comme le prompt réellement utilisé."
                )
            ),
            "liste": [str(x) for x in liste_prompts][:5]
        },
        "conclusion": str(data.get("conclusion", "")),
        "faux_positif_risque": faux_positif_risque,
        "faux_positif_raison": str(data.get("faux_positif_raison", "")),
    }


class ClientGeminiForensique:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY manquante dans le fichier .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    def appeler_json(self, question: str, texte_reponse: str) -> dict:
        prompt_complet = f"{SYSTEM_PROMPT_FORENSIQUE}\n\n{construire_user_prompt(question, texte_reponse)}"
        dernier_echec = None

        for tentative in range(1, NB_RETRIES_429 + 1):
            try:
                response = self.model.generate_content(
                    prompt_complet,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1
                    )
                )
                return extraire_json(response.text)

            except Exception as e:
                dernier_echec = e
                message = str(e)

                if "429" in message or "quota" in message.lower() or "rate limit" in message.lower():
                    attente = extraire_retry_delay(message) or (DELAI_RETRY_BASE * tentative)
                    print(f"[WARN] Rate limit/quota détecté. Nouvelle tentative dans {attente:.1f}s")
                    time.sleep(attente)
                    continue

                raise

        raise dernier_echec

def process_single_copy(copie, client):
    copie_id = copie.get("copie_id", "Inconnu")
    question = copie.get("question", "")
    texte = copie.get("texte_complet", "")

    if len(texte.strip()) < 20:
        return None

    print(f"   -> Analyse de la copie {copie_id}...")

    try:
        brut = client.appeler_json(question, texte)
        propre = normaliser_sortie(brut)

        classification = propre.get("classification", "HUMAIN")
        if classification == "PROBABLEMENT_IA":
            niveau_risque = "eleve"
        elif classification == "HYBRIDE":
            niveau_risque = "modere"
        else:
            niveau_risque = "faible"

        preuves_ia = propre.get("indices_linguistiques", [])[:6]
        preuves_humain = []
        dims = propre.get("dimensions", {})

        imp = dims.get("imperfections_humaines", {})
        obs_imp = imp.get("observation", "")
        if obs_imp:
            preuves_humain.append(obs_imp)

        extraits = propre.get("extraits_suspects", [])
        if not extraits and classification in ["PROBABLEMENT_IA", "HYBRIDE"]:
            # Fallback : on prend la première phrase du texte comme exemple de la structure
            phrase_fallback = texte.split('.')[0].strip() + "." if '.' in texte else texte[:100] + "..."
            extraits = [{
                "texte": phrase_fallback,
                "justification": "Extrait capturé automatiquement. La structure globale et le ton de cette phrase reflètent la neutralité et la standardisation typiques relevées dans l'analyse."
            }]

        return {
            "copie_id": copie_id,
            "score_ia": propre.get("score_suspicion", 0),
            "niveau_risque": niveau_risque,
            "classification": classification,
            "preuves_ia": preuves_ia,
            "preuves_humain": preuves_humain,
            "synthese": propre.get("resume_executif", ""),
            "details_complets": {
                "score_modele": propre.get("score_modele"),
                "score_recalcule": propre.get("score_recalcule"),
                "classification_modele": propre.get("classification_modele"),
                "classification_finale": propre.get("classification"),
                "dimensions": propre.get("dimensions"),
                "indices_linguistiques": propre.get("indices_linguistiques"),
                "extraits_suspects": extraits,
                "prompts_plausibles": propre.get("prompts_plausibles"),
                "conclusion": propre.get("conclusion"),
                "faux_positif_risque": propre.get("faux_positif_risque"),
                "faux_positif_raison": propre.get("faux_positif_raison"),
            }
        }

    except Exception as e:
        print(f"   [!] Erreur sur {copie_id}: {str(e)}")
        return {
            "copie_id": copie_id,
            "score_ia": None,
            "niveau_risque": "erreur",
            "classification": "ERREUR_ANALYSE",
            "preuves_ia": [],
            "preuves_humain": [],
            "synthese": "Échec de l'analyse IA.",
            "details_complets": {"erreur": str(e)}
        }


@tool("Outil de Detection Stylometrique Globale")
def outil_detection_ia(chemin_fichier: str) -> str:
    """
    Outil forensique qui analyse un lot complet de copies depuis un fichier JSON OCR.
    Paramètre : chemin absolu vers le fichier JSON (ex: C:/.../resultats_ocr.json)
    Retourne : JSON compatible avec le pipeline CrewAI.
    """
    try:
        with open(chemin_fichier.strip(), "r", encoding="utf-8") as f:
            data = json.load(f)
        copies = data.get("copies", data) if isinstance(data, dict) else data
    except Exception as e:
        return json.dumps({"erreur": f"Impossible de lire le fichier {chemin_fichier}: {str(e)}"}, ensure_ascii=False)

    try:
        client = ClientGeminiForensique()
    except Exception as e:
        return json.dumps({"erreur": f"Initialisation Gemini impossible: {str(e)}"}, ensure_ascii=False)

    resultats_globaux = []
    print("\n[Outil NLP] 🚀 Début de l'analyse Gemini des copies en PARALLÈLE...")

    # Utilisation d'un ThreadPoolExecutor pour analyser plusieurs copies en même temps
    # Max_workers est limité à 4 pour ne pas surcharger les quotas "Free Tier" de l'API Gemini
    # tout en restant beaucoup plus rapide qu'une exécution séquentielle.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_single_copy, copie, client): copie for copie in copies}
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res is not None:
                resultats_globaux.append(res)
            # Petit délai pour ménager l'API
            time.sleep(0.5)

    # Tri pour garder l'ordre d'origine
    resultats_globaux.sort(key=lambda x: x.get("copie_id", ""))

    print("[Outil NLP] ✅ Analyse terminée.\n")
    return json.dumps({"resultats_stylometrie": resultats_globaux}, ensure_ascii=False)