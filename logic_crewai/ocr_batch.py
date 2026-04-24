"""
ocr_batch.py — Traitement OCR via API Google Gemini
Appelé par n8n : python ocr_batch.py --dossier data/uploads --sortie data/resultats_ocr.json
"""
import argparse
import json
import os
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass
import time
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import PIL.PngImagePlugin
import PIL.JpegImagePlugin
import PIL.WebPImagePlugin
import PIL.BmpImagePlugin
from dotenv import load_dotenv

load_dotenv()

# Config Gemini
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

def extraire_texte_api_gemini(chemin_image: str) -> str:
    """
    Utilise l'API Google Gemini 1.5 Flash pour extraire le texte d'une image.
    """
    chemin = Path(chemin_image)
    if not chemin.exists():
        return ""

    try:
        print(f"  [API Gemini] Traitement de {chemin.name}...")
        
        img = Image.open(chemin_image)
        
        prompt = "Extrais TOUT le texte de cette image. Ne commente pas, donne juste le texte brut."
        
        reponse = model.generate_content([prompt, img])
        
        texte = reponse.text
        print(f"  [API Gemini] Succès : {len(texte)} caractères extraits.")
        return texte

    except Exception as e:
        print(f"  [API Gemini Erreur] {e}", file=sys.stderr)
        return ""

def main():
    parser = argparse.ArgumentParser(description="OCR via Gemini sur un dossier d'images")
    parser.add_argument("--dossier", required=True, help="Dossier contenant les images")
    parser.add_argument("--sortie",  required=True, help="Fichier JSON de sortie")
    parser.add_argument("--question", required=False, default="", help="Question de l'examen")
    args = parser.parse_args()

    # MOCK MODE FOR N8N TEST
    mock_file = Path("C:/Users/HP/Downloads/prjt_fixed2/entree_detection_ia.json")
    if mock_file.exists():
        with open(mock_file, "r", encoding="utf-8") as f:
            mock_data = json.load(f)
        
        # Inject the question into the mock data if not already there, just in case
        for copie in mock_data.get('copies', []):
            if not copie.get('question'):
                copie['question'] = args.question
        
        mock_data['nb_copies'] = len(mock_data.get('copies', []))
        
        Path(args.sortie).parent.mkdir(parents=True, exist_ok=True)
        with open(args.sortie, "w", encoding="utf-8") as f:
            json.dump(mock_data, f, ensure_ascii=False, indent=2)
        print(f"[OCR API MOCK] Terminé. Copies simulées injectées.")
        sys.exit(0)


if __name__ == "__main__":
    main()
