import sys
import os
import requests
import traceback

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/upload-copies"

def run_investigation_pipeline(investigation_id, professor_email):
    """
    Triggers the n8n workflow by sending uploaded files and investigation_id.
    """
    from app import app
    from models import db, Investigation, ExamCopy
    
    with app.app_context():
        inv = Investigation.query.get(investigation_id)
        if not inv:
            return
            
        inv.status = 'processing'
        db.session.commit()
        
        try:
            print(f"[PIPELINE #{investigation_id}] Triggering n8n workflow...")
            
            # Gather files from DB
            copies = ExamCopy.query.filter_by(investigation_id=investigation_id).all()
            
            # Prepare multipart/form-data
            files_payload = []
            for copy in copies:
                if os.path.exists(copy.stored_path):
                    # Open file in binary mode
                    f = open(copy.stored_path, 'rb')
                    files_payload.append(('copies', (copy.original_filename, f)))
            
            data_payload = {
                "investigation_id": investigation_id,
                "email": professor_email
            }

            # Send POST request to n8n
            response = requests.post(
                N8N_WEBHOOK_URL, 
                files=files_payload, 
                data=data_payload,
                timeout=30 # Timeout for the initial trigger
            )
            
            # Close all file handles
            for _, file_tuple in files_payload:
                file_tuple[1].close()

            if response.status_code == 200:
                print(f"[PIPELINE #{investigation_id}] Successfully triggered n8n.")
            else:
                print(f"[PIPELINE #{investigation_id}] n8n trigger failed: {response.status_code} - {response.text}")
                inv.status = 'failed'
                db.session.commit()

        except Exception as e:
            print(f"[PIPELINE #{investigation_id}] ERROR: {str(e)}")
            traceback.print_exc()
            inv.status = 'failed'
            db.session.commit()
