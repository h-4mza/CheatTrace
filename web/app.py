from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import uuid
import threading
from datetime import datetime
from dotenv import load_dotenv
from models import db, User, Module, Investigation, ExamCopy
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pipeline_runner import run_investigation_pipeline

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'forensique_web.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'data', 'uploads')

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin Required Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        modules_count = Module.query.count()
        investigations = Investigation.query.order_by(Investigation.created_at.desc()).limit(5).all()
        total_inv = Investigation.query.count()
    else:
        modules_count = Module.query.filter_by(professor_id=current_user.id).count()
        investigations = Investigation.query.join(Module).filter(Module.professor_id == current_user.id).order_by(Investigation.created_at.desc()).limit(5).all()
        total_inv = Investigation.query.join(Module).filter(Module.professor_id == current_user.id).count()
        
    pending_inv = Investigation.query.join(Module).filter(Module.professor_id == current_user.id, Investigation.status.in_(['pending', 'processing'])).count()
    
    return render_template('dashboard.html', 
                           modules_count=modules_count, 
                           investigations=investigations,
                           total_inv=total_inv,
                           pending_inv=pending_inv)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Connexion réussie !', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants invalides.', 'danger')
            
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('login'))

# --- MODULES ---

@app.route('/modules')
@login_required
def modules_list():
    if current_user.role == 'admin':
        modules = Module.query.all()
    else:
        modules = Module.query.filter_by(professor_id=current_user.id).all()
    return render_template('modules/list.html', modules=modules)

@app.route('/modules/new', methods=['GET', 'POST'])
@login_required
def modules_new():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        new_module = Module(name=name, description=description, professor_id=current_user.id)
        db.session.add(new_module)
        db.session.commit()
        flash('Module créé avec succès.', 'success')
        return redirect(url_for('modules_list'))
    return render_template('modules/new.html')

# --- INVESTIGATIONS ---

@app.route('/investigations')
@login_required
def investigations_list():
    if current_user.role == 'admin':
        investigations = Investigation.query.order_by(Investigation.created_at.desc()).all()
    else:
        investigations = Investigation.query.join(Module).filter(Module.professor_id == current_user.id).order_by(Investigation.created_at.desc()).all()
    return render_template('investigations/list.html', investigations=investigations)

@app.route('/investigations/new', methods=['GET', 'POST'])
@login_required
def investigations_new():
    module_id = request.args.get('module_id', type=int)
    
    if current_user.role == 'admin':
        modules = Module.query.all()
    else:
        modules = Module.query.filter_by(professor_id=current_user.id).all()

    if request.method == 'POST':
        selected_module_id = request.form.get('module_id')
        files = request.files.getlist('files')
        
        if not selected_module_id or not files or files[0].filename == '':
            flash('Veuillez sélectionner un module et au moins un fichier.', 'danger')
            return redirect(url_for('investigations_new', module_id=module_id))

        # Create investigation record
        inv = Investigation(module_id=selected_module_id, status='pending')
        db.session.add(inv)
        db.session.commit()

        # Save files
        inv_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'investigations', str(inv.id))
        os.makedirs(inv_dir, exist_ok=True)
        
        saved_files = []
        for file in files:
            filename = secure_filename(file.filename)
            # Add unique prefix to avoid collisions
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(inv_dir, unique_filename)
            file.save(filepath)
            
            copy = ExamCopy(
                investigation_id=inv.id,
                original_filename=filename,
                stored_path=filepath
            )
            db.session.add(copy)
            saved_files.append(filepath)
        
        db.session.commit()
        
        # Trigger pipeline asynchronously
        from pipeline_runner import run_investigation_pipeline
        threading.Thread(target=run_investigation_pipeline, args=(inv.id, current_user.email)).start()
        
        flash('Investigation lancée avec succès.', 'success')
        return redirect(url_for('investigations_detail', id=inv.id))

    return render_template('investigations/new.html', modules=modules, selected_module_id=module_id)

@app.route('/investigations/<int:id>')
@login_required
def investigations_detail(id):
    inv = Investigation.query.get_or_404(id)
    # Check ownership
    if current_user.role != 'admin' and inv.module.professor_id != current_user.id:
        abort(403)
        
    report_content = ""
    if inv.status == 'completed' and inv.report_path and os.path.exists(inv.report_path):
        import markdown
        with open(inv.report_path, 'r', encoding='utf-8') as f:
            report_content = markdown.markdown(f.read())
            
    return render_template('investigations/detail.html', investigation=inv, report_content=report_content)

@app.route('/api/investigations/<int:id>/status')
@login_required
def api_investigation_status(id):
    inv = Investigation.query.get_or_404(id)
    if current_user.role != 'admin' and inv.module.professor_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "status": inv.status,
        "completed_at": inv.completed_at.isoformat() if inv.completed_at else None
    })

@app.route('/api/investigation/callback', methods=['POST'])
def investigation_callback():
    """
    Called by n8n when the forensic analysis is completed.
    Payload: { "investigation_id": X, "status": "completed/failed", "report_content": "Markdown text" }
    """
    data = request.json
    inv_id = data.get('investigation_id')
    status = data.get('status', 'completed')
    report_content = data.get('report_content', '')

    inv = Investigation.query.get(inv_id)
    if not inv:
        return jsonify({"error": "Investigation not found"}), 404

    inv.status = status
    if status == 'completed':
        report_dir = os.path.join(os.path.dirname(app.config['UPLOAD_FOLDER']), 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"investigation_{inv_id}.md")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        inv.report_path = report_path
        inv.completed_at = datetime.utcnow()
        
    db.session.commit()
    return jsonify({"message": "Callback processed successfully"}), 200

# --- ADMIN ---

@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        "users": User.query.count(),
        "modules": Module.query.count(),
        "investigations": Investigation.query.count(),
        "pending": Investigation.query.filter(Investigation.status.in_(['pending', 'processing'])).count()
    }
    recent_investigations = Investigation.query.order_by(Investigation.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, investigations=recent_investigations)

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_users():
    if request.method == 'POST':
        # Add User Logic
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Cet utilisateur existe déjà.', 'danger')
        else:
            from werkzeug.security import generate_password_hash
            new_user = User(
                username=username, 
                email=email, 
                password_hash=generate_password_hash(password),
                role=role
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f'Utilisateur {username} créé.', 'success')
            
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/delete/<int:id>')
@login_required
@admin_required
def admin_user_delete(id):
    if id == current_user.id:
        flash('Vous ne pouvez pas vous supprimer vous-même.', 'danger')
    else:
        user = User.query.get_or_404(id)
        db.session.delete(user)
        db.session.commit()
        flash('Utilisateur supprimé.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/investigations')
@login_required
@admin_required
def admin_investigations_all():
    # Simple filtering logic
    prof_id = request.args.get('prof_id', type=int)
    status = request.args.get('status')
    
    query = Investigation.query.join(Module).join(User, Module.professor_id == User.id)
    
    if prof_id:
        query = query.filter(User.id == prof_id)
    if status:
        query = query.filter(Investigation.status == status)
        
    investigations = query.order_by(Investigation.created_at.desc()).all()
    professors = User.query.filter_by(role='prof').all()
    
    return render_template('admin/investigations.html', 
                           investigations=investigations, 
                           professors=professors,
                           current_prof_id=prof_id,
                           current_status=status)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
