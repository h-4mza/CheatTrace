from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='prof') # 'admin', 'prof'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    modules = db.relationship('Module', backref='professor', lazy=True)

class Module(db.Model):
    __tablename__ = 'modules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    professor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    investigations = db.relationship('Investigation', backref='module', lazy=True)

class Investigation(db.Model):
    __tablename__ = 'investigations'
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # 'pending', 'processing', 'completed', 'failed'
    type_investigation = db.Column(db.String(20), default='complete') # 'singuliere', 'collaborative', 'complete'
    exam_question = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    report_path = db.Column(db.String(500))

    exam_copies = db.relationship('ExamCopy', backref='investigation', lazy=True)

class ExamCopy(db.Model):
    __tablename__ = 'exam_copies'
    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.Integer, db.ForeignKey('investigations.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    ocr_text = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
