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
    args = parser.parse_args()

    dossier = Path(args.dossier)
    if not dossier.exists():
        print(f"[ERREUR] Dossier introuvable : {dossier}", file=sys.stderr)
        sys.exit(1)

    EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    images = sorted([f for f in dossier.iterdir() if f.suffix.lower() in EXTENSIONS])

    if not images:
        print(f"[ERREUR] Aucune image trouvée dans {dossier}", file=sys.stderr)
        sortie = {"nb_copies": 0, "copies": []}
        with open(args.sortie, "w", encoding="utf-8") as f:
            json.dump(sortie, f, ensure_ascii=False, indent=2)
        sys.exit(0)

    print(f"[OCR API] {len(images)} image(s) trouvée(s). Envoi vers Gemini...")

    copies = []
    for i, image in enumerate(images, 1):
        copie_id = f"C{i:02d}"
        print(f"[{i}/{len(images)}] Appel API pour {image.name}...")
        debut = time.time()

        texte = extraire_texte_api_gemini(str(image))
        duree = round(time.time() - debut, 2)

        copies.append({
            "copie_id":      copie_id,
            "fichier":       image.name,
            "texte_complet": texte.strip(),
            "nb_chars":      len(texte.strip()),
            "duree_sec":     duree,
        })

    sortie = {
        "nb_copies": len(copies),
        "copies":    copies,
    }

    Path(args.sortie).parent.mkdir(parents=True, exist_ok=True)
    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    print(f"\n[OCR API] Terminé. {len(copies)} copies traitées via l'API.")


if __name__ == "__main__":
    main()
