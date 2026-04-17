"""
ocr_batch.py — Traitement OCR via API Mistral
Appelé par n8n : python ocr_batch.py --dossier data/uploads --sortie data/resultats_ocr.json
"""
import argparse
import json
import os
import sys
import time
import base64
from pathlib import Path
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

# Config Mistral
api_key = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=api_key)

def encoder_image(chemin_image: str) -> str:
    """Encode l'image en base64 pour l'envoi à l'API."""
    with open(chemin_image, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extraire_texte_api_mistral(chemin_image: str) -> str:
    """
    Utilise l'API Mistral OCR (Pixtral or dedicated OCR) to extract text.
    """
    chemin = Path(chemin_image)
    if not chemin.exists():
        return ""

    try:
        print(f"  [API Mistral] Traitement de {chemin.name}...")
        
        # Detect mime type
        ext = chemin.suffix.lower()
        if ext in ['.jpg', '.jpeg']: mime = "image/jpeg"
        elif ext == '.png': mime = "image/png"
        elif ext == '.webp': mime = "image/webp"
        else: mime = "image/jpeg"

        base64_image = encoder_image(chemin_image)
        
        reponse = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extrais TOUT le texte de cette image. Ne commente pas, donne juste le texte brut."},
                        {
                            "type": "image_url",
                            "image_url": f"data:{mime};base64,{base64_image}"
                        }
                    ]
                }
            ]
        )
        
        texte = reponse.choices[0].message.content
        print(f"  [API Mistral] Succès : {len(texte)} caractères extraits.")
        return texte

    except Exception as e:
        print(f"  [API Mistral Erreur] {e}", file=sys.stderr)
        # Fallback local ultra-basique si l'API échoue (optionnel)
        return ""

def main():
    parser = argparse.ArgumentParser(description="OCR via API externe sur un dossier d'images")
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

    print(f"[OCR API] {len(images)} image(s) trouvée(s). Envoi vers Mistral...")

    copies = []
    for i, image in enumerate(images, 1):
        copie_id = f"C{i:02d}"
        print(f"[{i}/{len(images)}] Appel API pour {image.name}...")
        debut = time.time()

        texte = extraire_texte_api_mistral(str(image))
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
