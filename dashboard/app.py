"""
dashboard/app.py — Interface Web Forensique
Affiche le dernier rapport + formulaire d'upload d'images
"""
import os
import markdown
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plateforme de Confiance Numérique — ENSAJ</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: #f4f7f6; color: #333; padding: 20px;
        }
        .container { max-width: 960px; margin: auto; }

        /* ── Header ── */
        .header {
            background: #2c3e50; color: white;
            padding: 20px 30px; border-radius: 10px;
            margin-bottom: 24px; display: flex;
            justify-content: space-between; align-items: center;
        }
        .header h1 { font-size: 20px; font-weight: 600; }
        .header span { font-size: 13px; opacity: 0.7; }

        /* ── Upload Card ── */
        .upload-card {
            background: white; border-radius: 10px;
            padding: 24px; margin-bottom: 24px;
            border: 2px dashed #3498db;
        }
        .upload-card h2 { color: #2980b9; font-size: 16px; margin-bottom: 16px; }
        .upload-zone {
            background: #eaf4fb; border-radius: 8px;
            padding: 20px; text-align: center;
        }
        .upload-zone input[type=file] { margin-bottom: 12px; width: 100%; }
        .upload-zone input[type=email] {
            width: 100%; padding: 8px 12px;
            border: 1px solid #ccc; border-radius: 6px;
            margin-bottom: 12px; font-size: 14px;
        }
        .btn-primary {
            background: #2980b9; color: white;
            border: none; padding: 10px 24px;
            border-radius: 6px; cursor: pointer;
            font-size: 14px; font-weight: 600;
        }
        .btn-primary:hover { background: #1a6a9a; }
        .btn-primary:disabled { background: #aaa; cursor: not-allowed; }

        /* ── Status ── */
        #status-box {
            background: #f0f8ff; border-left: 4px solid #3498db;
            padding: 12px 16px; border-radius: 0 8px 8px 0;
            margin-top: 14px; font-size: 14px; display: none;
        }
        #status-box.success { border-color: #27ae60; background: #f0fff4; }
        #status-box.error   { border-color: #e74c3c; background: #fff5f5; }

        /* ── Rapport ── */
        .rapport-card {
            background: white; border-radius: 10px;
            padding: 28px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .rappel {
            background: #e8f4f8; border-left: 4px solid #3498db;
            padding: 10px 14px; border-radius: 0 6px 6px 0;
            margin-bottom: 20px; font-size: 14px;
        }
        h1 { font-size: 24px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }
        h2 { font-size: 18px; color: #2c3e50; margin: 24px 0 12px; }
        h3 { font-size: 15px; color: #34495e; margin: 16px 0 8px; }
        ul { background: #f9f9f9; padding: 12px 12px 12px 28px; border-radius: 6px; margin-bottom: 12px; }
        li { margin-bottom: 6px; line-height: 1.6; }
        hr { border: none; border-top: 1px solid #eee; margin: 20px 0; }
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>Plateforme de Confiance Numérique — ENSAJ</h1>
        <span>Système forensique de détection de fraude académique</span>
    </div>

    <!-- FORMULAIRE UPLOAD -->
    <div class="upload-card">
        <h2>Lancer une nouvelle investigation</h2>
        <div class="upload-zone">
            <input type="file" id="files-input" multiple accept=".jpg,.jpeg,.png,.bmp,.tiff"
                   onchange="afficherNomsFichiers()">
            <div id="files-preview" style="font-size:13px;color:#666;margin-bottom:10px;"></div>
            <input type="email" id="email-input" placeholder="Email du professeur" value="professeur@ensaj.ma">
            <button class="btn-primary" id="btn-lancer" onclick="lancerInvestigation()">
                Lancer l'investigation
            </button>
            <div id="status-box">En attente...</div>
        </div>
    </div>

    <!-- RAPPORT -->
    <div class="rapport-card">
        <div class="rappel">
            <strong>Système Forensique Actif :</strong>
            Affichage du dernier rapport d'investigation généré par l'Intelligence Artificielle.
        </div>
        <div class="rapport-content">
            {{ contenu_html | safe }}
        </div>
    </div>

</div>

<script>
function afficherNomsFichiers() {
    const input = document.getElementById('files-input');
    const preview = document.getElementById('files-preview');
    const noms = Array.from(input.files).map(f => f.name).join(', ');
    preview.textContent = input.files.length > 0
        ? input.files.length + ' fichier(s) : ' + noms
        : '';
}

async function lancerInvestigation() {
    const input   = document.getElementById('files-input');
    const email   = document.getElementById('email-input').value;
    const btn     = document.getElementById('btn-lancer');
    const statBox = document.getElementById('status-box');

    if (!input.files.length) {
        alert('Veuillez sélectionner au moins un fichier image.');
        return;
    }

    btn.disabled = true;
    statBox.style.display = 'block';
    statBox.className = '';
    statBox.textContent = 'Envoi des fichiers en cours...';

    const formData = new FormData();
    for (const file of input.files) {
        formData.append('copies', file);
    }
    formData.append('email', email);

    try {
        statBox.textContent = 'OCR + analyse en cours (peut prendre 2-5 minutes)...';

        const response = await fetch('http://localhost:5678/webhook/upload-copies', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.statut === 'termine') {
            statBox.className = 'success';
            const nb = result.nb_suspects || 0;
            statBox.textContent = '✓ Investigation terminée. ' + nb + ' suspect(s) détecté(s). Rechargement...';
            setTimeout(() => window.location.reload(), 2000);
        } else {
            statBox.className = 'error';
            statBox.textContent = 'Erreur : ' + (result.message || JSON.stringify(result));
        }
    } catch (err) {
        statBox.className = 'error';
        statBox.textContent = 'Erreur réseau : ' + err.message;
    } finally {
        btn.disabled = false;
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def afficher_rapport():
    dossier = os.path.dirname(__file__)
    fichiers_md = [f for f in os.listdir(dossier) if f.endswith('.md')]

    if not fichiers_md:
        contenu = "<h2>Aucun rapport disponible</h2><p>Uploadez des copies via le formulaire ci-dessus.</p>"
        return render_template_string(TEMPLATE_HTML, contenu_html=contenu)

    fichiers_md.sort(key=lambda x: os.path.getmtime(os.path.join(dossier, x)), reverse=True)
    chemin = os.path.join(dossier, fichiers_md[0])

    with open(chemin, 'r', encoding='utf-8') as f:
        texte_md = f.read()

    html = markdown.markdown(texte_md)
    return render_template_string(TEMPLATE_HTML, contenu_html=html)

@app.route('/api/status')
def api_status():
    """Endpoint pour vérifier le statut depuis n8n ou le frontend."""
    dossier = os.path.dirname(__file__)
    fichiers = [f for f in os.listdir(dossier) if f.endswith('.md')]
    return jsonify({
        "rapports_disponibles": len(fichiers),
        "dernier": fichiers[0] if fichiers else None
    })

if __name__ == '__main__':
    print("Dashboard démarré → http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
