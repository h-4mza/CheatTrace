import sys
import os
import requests
import traceback
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/upload-copies")

def run_investigation_pipeline(investigation_id, professor_email):
    """
    Triggers the n8n workflow. 
    """
    from app import app
    from models import db, Investigation, ExamCopy
    
    with app.app_context():
        inv = Investigation.query.get(investigation_id)
        if not inv:
            print(f"[PIPELINE] Investigation {investigation_id} not found.")
            return
            
        inv.status = 'processing'
        db.session.commit()
        
        files_to_close = []
        try:
            print(f"[PIPELINE #{investigation_id}] Preparing data for n8n...")
            
            copies = ExamCopy.query.filter_by(investigation_id=investigation_id).all()
            
            # UNIQUE KEYS for each file to prevent n8n overwriting
            files_payload = []
            for i, copy in enumerate(copies):
                if os.path.exists(copy.stored_path):
                    f = open(copy.stored_path, 'rb')
                    files_payload.append((f'copy_{i}', (copy.original_filename, f)))
                    files_to_close.append(f)
            
            data_payload = {
                "investigation_id": investigation_id,
                "email": professor_email,
                "type_investigation": inv.type_investigation,
                "exam_question": inv.exam_question or "",
                "callback_url": "http://localhost:5001/api/investigation/callback"
            }

            print(f"[PIPELINE #{investigation_id}] Sending to {N8N_WEBHOOK_URL}...")
            response = requests.post(
                N8N_WEBHOOK_URL,
                files=files_payload,
                data=data_payload,
                timeout=900
            )            

            if response.status_code in [200, 201]:
                print(f"[PIPELINE #{investigation_id}] n8n trigger SUCCESS.")
                try:
                    result = response.json()
                    status = "completed" if result.get("statut") == "termine" else "failed"
                    report_content = result.get("output", "")
                    
                    inv.status = status
                    if status == "completed":
                        report_dir = os.path.join(os.path.dirname(app.config['UPLOAD_FOLDER']), 'reports')
                        os.makedirs(report_dir, exist_ok=True)
                        report_path = os.path.join(report_dir, f"investigation_{investigation_id}.md")
                        
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(report_content)
                            
                        inv.report_path = report_path
                        inv.completed_at = datetime.utcnow()
                        
                    db.session.commit()
                except Exception as e:
                    print(f"[PIPELINE #{investigation_id}] Failed to parse n8n response: {e}")
                    inv.status = 'failed'
                    db.session.commit()
            else:
                print(f"[PIPELINE #{investigation_id}] n8n trigger FAILED: {response.status_code}")
                inv.status = 'failed'
                db.session.commit()

        except Exception as e:
            print(f"[PIPELINE #{investigation_id}] CRITICAL ERROR: {str(e)}")
            inv.status = 'failed'
            db.session.commit()
        finally:
            for f in files_to_close:
                f.close()
