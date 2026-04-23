import os
from crewai import Agent, LLM
from dotenv import load_dotenv

load_dotenv()

# Utilisation de Google Gemini (AI Studio)
llm_gemini = LLM(
    model="gemini/gemini-3.1-flash-lite-preview",
    api_key=os.environ.get("GEMINI_API_KEY"),
)

def creer_agents() -> dict:

    expert_nlp = Agent(
        role="Expert NLP et Stylométriste Forensique",
        goal=(
            "Analyser chaque texte extrait pour détecter les signatures "
            "d'une génération par IA (LLM). Produire un score et lister les preuves textuelles."
        ),
        backstory=(
            "Tu es un linguiste computationnel de renommée mondiale, spécialisé dans "
            "la détection de textes générés par intelligence artificielle. Tu sais "
            "faire la différence entre une rédaction humaine (imparfaite, avec une variance syntaxique) "
            "et une rédaction IA (trop lisse, parfaite, sans bruit humain). Tu ne te laisses "
            "jamais tromper par de simples fautes d'orthographe rajoutées artificiellement."
        ),
        llm=llm_gemini,
        verbose=True,
        allow_delegation=False,
    )

    analyste_fraude = Agent(
        role="Analyste en Fraude Collaborative et Plagiat",
        goal=(
            "Identifier les groupes d'étudiants ayant collaboré frauduleusement "
            "en mesurant la similarité sémantique (paraphrase) et lexicale (copier-coller)."
        ),
        backstory=(
            "Tu es un analyste forensique redoutable en milieu académique. "
            "Tu utilises des algorithmes mathématiques avancés (SBERT, MinHash) pour débusquer "
            "les étudiants qui se partagent les réponses. Tu sais que si deux étudiants ont "
            "les mêmes idées formulées différemment, c'est une fraude. Tu te bases uniquement sur les mathématiques."
        ),
        llm=llm_gemini,
        verbose=True,
        allow_delegation=False,
    )

    juge_forensique = Agent(
        role="Juge Forensique Académique Suprême",
        goal=(
            "Synthétiser les analyses de l'Expert NLP et de l'Analyste Fraude. "
            "Évaluer la convergence des preuves et générer le JSON de verdict final."
        ),
        backstory=(
            "Tu es le responsable final de cette investigation. Tu reçois les "
            "rapports des experts. Ton rôle est de croiser les preuves : si l'expert NLP "
            "dit 'IA' et l'Analyste dit 'Collusion', tu tranches. Tu es froid, impartial, "
            "et tu exiges des preuves convergentes avant d'accuser un étudiant. "
            "Tu formates toujours tes conclusions dans un JSON strict pour les systèmes informatiques."
        ),
        llm=llm_gemini,
        verbose=True,
        allow_delegation=True,
    )

    return {
        "expert_nlp":       expert_nlp,
        "analyste_fraude":  analyste_fraude,
        "juge_forensique":  juge_forensique,
    }
