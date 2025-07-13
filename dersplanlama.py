# Gerekli kütüphaneleri ve modülleri import ediyoruz
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import UniqueConstraint
from werkzeug.utils import secure_filename # Güvenli dosya adı için
from sqlalchemy import func # SQL fonksiyonları için (örn. count)

# --- UYGULAMA VE VERİTABANI KURULUMU ---

app = Flask(__name__)

# Güvenli konfigürasyon: Ayarları ortam değişkenlerinden alıyoruz
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'varsayilan_cok_gizli_bir_anahtar_12345')
# Yerel geliştirme için SQLite kullan, yayın ortamı için DATABASE_URL ortam değişkenini kullan
database_url = os.environ.get('DATABASE_URL', 'sqlite:///dersplanlama.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Dosya yükleme klasörü ve izin verilen uzantılar
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip', 'rar', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Eğer uploads klasörü yoksa oluştur
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Veritabanı nesnesini ve Migrate nesnesini oluşturuyoruz
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- YARDIMCI FONKSİYONLAR ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- VERITABANI MODELLERİ ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    expire_date = db.Column(db.DateTime)
    progress = db.relationship('UserProgress', backref='user', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='user_rel', lazy=True, cascade="all, delete-orphan")
    quiz_attempts = db.relationship('UserQuizAttempt', backref='user_rel', lazy=True, cascade="all, delete-orphan")

class Ders(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    konular = db.relationship('Konu', backref='ders', lazy=True, cascade="all, delete-orphan")

class Konu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ders_id = db.Column(db.Integer, db.ForeignKey('ders.id'), nullable=False)
    alt_basliklar = db.relationship('AltBaslik', backref='konu', lazy=True, cascade="all, delete-orphan")

class AltBaslik(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    video_link = db.Column(db.Text)
    notlar = db.Column(db.Text)
    konu_id = db.Column(db.Integer, db.ForeignKey('konu.id'), nullable=False)
    progress_records = db.relationship('UserProgress', backref='alt_baslik', lazy=True, cascade="all, delete-orphan")
    materials = db.relationship('Material', backref='alt_baslik', lazy=True, cascade="all, delete-orphan")
    quiz = db.relationship('Quiz', backref='alt_baslik_rel', lazy=True, uselist=False, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='alt_baslik_rel', lazy=True, cascade="all, delete-orphan")

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alt_baslik_id = db.Column(db.Integer, db.ForeignKey('alt_baslik.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('user_id', 'alt_baslik_id', name='_user_alt_baslik_uc'),)

    def __repr__(self):
        return f'<UserProgress UserID: {self.user_id}, AltBaslikID: {self.alt_baslik_id}>'

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<Announcement {self.title}>'

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alt_baslik_id = db.Column(db.Integer, db.ForeignKey('alt_baslik.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Material {self.original_filename}>'

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    alt_baslik_id = db.Column(db.Integer, db.ForeignKey('alt_baslik.id'), nullable=False)
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Quiz {self.title}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False) 
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Question {self.question_text[:50]}...>'

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=False) 
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<Answer {self.answer_text[:50]}...>'

class UserQuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    attempt_date = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('user_id', 'quiz_id', name='_user_quiz_uc'),)

    def __repr__(self):
        return f'<UserQuizAttempt UserID: {self.user_id}, QuizID: {self.quiz_id}, Score: {self.score}>'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alt_baslik_id = db.Column(db.Integer, db.ForeignKey('alt_baslik.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    replies = db.relationship('Comment', backref=db.backref('parent_comment_rel', remote_side=[id]), lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Comment by {self.user_id} on AltBaslik {self.alt_baslik_id}: {self.content[:50]}...>'


# --- YARDIMCI FONKSİYONLAR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Bu sayfaya erişim yetkiniz yok.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- ROTALAR (SAYFALAR) ---

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            # Erişim süresi kontrolü
            if user.expire_date:
                # current_app.logger.debug(f"User expire date: {user.expire_date}, UTC now: {datetime.utcnow()}")
                # datetime.utcnow() ile karşılaştırma yaparken bir günlük tolerans ekleyebiliriz
                # Böylece bitiş günü dahil erişim sağlanır
                if datetime.utcnow() >= (user.expire_date + timedelta(days=1)):
                    flash(f"Erişim süreniz {user.expire_date.strftime('%Y-%m-%d')} tarihinde dolmuştur. Lütfen yöneticinizle iletişime geçin.", "danger")
                    return redirect(url_for('login'))
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            return redirect(url_for("admin_panel" if user.is_admin else "user_panel"))
        else:
            flash("Hatalı kullanıcı adı veya şifre!", "danger")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.clear()
    flash("Başarıyla çıkış yaptınız.", "success")
    return redirect(url_for("login"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin_panel():
    is_main_admin = session.get("username") == "admin"

    if request.method == "POST":
        action = request.form.get("action")
        delete_type = request.form.get("delete_type")
        delete_id = request.form.get("id", type=int)
        
        # current_app.logger.debug(f"DEBUG: Silme isteği alındı. Tür: {delete_type}, ID: {delete_id}, Admin mi: {session.get('is_admin')}, Ana Admin mi: {is_main_admin}")

        if delete_type and delete_id:
            item_to_delete = None
            try:
                if delete_type == "ders": 
                    item_to_delete = Ders.query.get_or_404(delete_id)
                elif delete_type == "konu": 
                    item_to_delete = Konu.query.get_or_404(delete_id)
                elif delete_type == "alt_baslik": 
                    item_to_delete = AltBaslik.query.get_or_404(delete_id)
                elif delete_type == "user" and is_main_admin: 
                    item_to_delete = User.query.get_or_404(delete_id)
                elif delete_type == "announcement": 
                    item_to_delete = Announcement.query.get_or_404(delete_id)
                elif delete_type == "quiz":
                    item_to_delete = Quiz.query.get_or_404(delete_id)
                elif delete_type == "material": 
                    material_to_delete = Material.query.get_or_404(delete_id)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], material_to_delete.filename)
                    # current_app.logger.debug(f"DEBUG: Materyal dosyası silinmeye çalışılıyor: {file_path}")
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            # current_app.logger.debug(f"DEBUG: Dosya {file_path} başarıyla silindi.")
                        except OSError as e:
                            current_app.logger.error(f"HATA: Dosya silinirken hata oluştu {file_path}: {e}")
                            flash(f"Dosya silinirken bir hata oluştu: {e}", "danger")
                            db.session.rollback()
                            return redirect(url_for('admin_panel'))
                    item_to_delete = material_to_delete
                
                if item_to_delete:
                    # current_app.logger.debug(f"DEBUG: Silinecek öğe bulundu: {item_to_delete}")
                    if delete_type == 'user' and item_to_delete.username == 'admin':
                        flash("Ana admin kullanıcısı silinemez.", "danger")
                        # current_app.logger.debug("DEBUG: Ana admin kullanıcısı silinmeye çalıştı.")
                    else:
                        db.session.delete(item_to_delete)
                        db.session.commit()
                        flash(f"{delete_type.capitalize()} başarıyla silindi.", "success")
                        # current_app.logger.debug(f"DEBUG: {delete_type.capitalize()} ID {delete_id} veritabanından başarıyla silindi.")
                # else:
                    # current_app.logger.debug(f"DEBUG: Silme için öğe bulunamadı. Tür: {delete_type}, ID: {delete_id}.")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"HATA: Silme işlemi sırasında beklenmeyen bir hata oluştu ({delete_type} ID {delete_id}): {e}")
                flash(f"Silme işlemi sırasında bir hata oluştu: {e}", "danger")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_user" and is_main_admin:
            username = request.form.get("new_username", "").strip()
            password = request.form.get("new_password", "").strip()
            access_days_str = request.form.get("access_days", "").strip()

            if not username or not password:
                flash("Kullanıcı adı ve şifre boş olamaz.", "danger")
            elif User.query.filter_by(username=username).first():
                flash("Bu kullanıcı adı zaten mevcut.", "danger")
            else:
                expire_date = None
                if access_days_str.isdigit():
                    days_to_add = int(access_days_str)
                    if days_to_add > 0 and days_to_add <= 36500: # Max 100 yıl
                        expire_date = datetime.utcnow() + timedelta(days=days_to_add)
                    elif days_to_add <= 0:
                        flash("Erişim süresi pozitif bir sayı olmalıdır.", "danger")
                        return redirect(url_for('admin_panel'))
                    else:
                        flash("Erişim süresi çok büyük. Lütfen daha küçük bir değer girin.", "danger")
                        return redirect(url_for('admin_panel'))
                elif access_days_str: # Sayısal olmayan ama boş olmayan giriş
                    flash("Erişim süresi sadece sayı içermelidir.", "danger")
                    return redirect(url_for('admin_panel'))
                
                hashed_password = generate_password_hash(password)
                new_user = User(username=username, password=hashed_password, is_admin=False, expire_date=expire_date)
                db.session.add(new_user)
                db.session.commit()
                flash(f"'{username}' kullanıcısı başarıyla eklendi.", "success")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_ders":
            ders_name = request.form.get("yeni_ders", "").strip()
            if ders_name and not Ders.query.filter_by(name=ders_name).first():
                new_ders = Ders(name=ders_name)
                db.session.add(new_ders)
                db.session.commit()
                flash(f"'{ders_name}' dersi eklendi.", "success")
            else:
                flash("Ders adı boş olamaz veya bu ders zaten mevcut.", "danger")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_konu":
            konu_name = request.form.get("yeni_konu", "").strip()
            ders_id = request.form.get("ders_sec_konu", type=int)
            if konu_name and ders_id:
                new_konu = Konu(name=konu_name, ders_id=ders_id)
                db.session.add(new_konu)
                db.session.commit()
                flash(f"'{konu_name}' konusu eklendi.", "success")
            else:
                flash("Konu adı veya ders seçimi boş olamaz.", "danger")
            return redirect(url_for('admin_panel'))
            
        elif action == "add_alt_baslik":
            alt_baslik_name = request.form.get("alt_baslik", "").strip()
            konu_id = request.form.get("konu_sec_alt", type=int)
            video_link = request.form.get("video", "").strip()
            notlar = request.form.get("notlar", "").strip()
            if alt_baslik_name and konu_id:
                new_alt_baslik = AltBaslik(name=alt_baslik_name, konu_id=konu_id, video_link=video_link, notlar=notlar)
                db.session.add(new_alt_baslik)
                db.session.commit()
                flash(f"'{alt_baslik_name}' alt başlığı eklendi.", "success")
            else:
                flash("Alt başlık veya konu seçimi boş olamaz.", "danger")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_announcement":
            title = request.form.get("announcement_title", "").strip()
            content = request.form.get("announcement_content", "").strip()
            if title and content:
                new_announcement = Announcement(title=title, content=content)
                db.session.add(new_announcement)
                db.session.commit()
                flash("Duyuru başarıyla eklendi.", "success")
            else:
                flash("Duyuru başlığı ve içeriği boş olamaz.", "danger")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_material":
            alt_baslik_id = request.form.get("alt_baslik_sec_materyal", type=int)
            if 'file' not in request.files:
                flash("Dosya yüklenemedi: Dosya bulunamadı.", "danger")
                return redirect(url_for('admin_panel'))
            
            file = request.files['file']
            if file.filename == '':
                flash("Dosya yüklenemedi: Dosya seçilmedi.", "danger")
                return redirect(url_for('admin_panel'))
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

                new_material = Material(
                    alt_baslik_id=alt_baslik_id,
                    filename=unique_filename,
                    original_filename=file.filename
                )
                db.session.add(new_material)
                db.session.commit()
                flash(f"'{file.filename}' materyali başarıyla yüklendi.", "success")
            else:
                flash("Geçersiz dosya türü veya dosya yüklenemedi.", "danger")
            return redirect(url_for('admin_panel'))
        
        elif action == "add_quiz":
            alt_baslik_id = request.form.get("alt_baslik_sec_quiz", type=int)
            quiz_title = request.form.get("quiz_title", "").strip()
            
            question_texts = request.form.getlist("question_text[]")
            
            if not alt_baslik_id or not quiz_title or not question_texts:
                flash("Quiz başlığı, alt başlık seçimi veya en az bir soru boş olamaz.", "danger")
                return redirect(url_for('admin_panel'))

            existing_quiz = Quiz.query.filter_by(alt_baslik_id=alt_baslik_id).first()
            if existing_quiz:
                flash("Bu alt başlık için zaten bir quiz mevcut. Lütfen mevcut quizi silin veya düzenleyin.", "danger")
                return redirect(url_for('admin_panel'))

            new_quiz = Quiz(title=quiz_title, alt_baslik_id=alt_baslik_id)
            db.session.add(new_quiz)
            db.session.flush() # new_quiz.id'ye erişmek için flush

            for i, q_text in enumerate(question_texts):
                if not q_text.strip():
                    continue
                new_question = Question(quiz_id=new_quiz.id, question_text=q_text.strip())
                db.session.add(new_question)
                db.session.flush()

                answer_texts = request.form.getlist(f"answer_text_{i+1}[]")
                correct_answer_index_str = request.form.get(f"correct_answer_{i+1}")
                
                if not answer_texts or correct_answer_index_str is None:
                    flash(f"Soru {i+1} için cevaplar veya doğru cevap seçimi eksik.", "danger")
                    db.session.rollback()
                    return redirect(url_for('admin_panel'))
                
                try:
                    correct_answer_index = int(correct_answer_index_str)
                except ValueError:
                    flash(f"Soru {i+1} için doğru cevap seçimi geçersiz.", "danger")
                    db.session.rollback()
                    return redirect(url_for('admin_panel'))


                for j, a_text in enumerate(answer_texts):
                    if not a_text.strip():
                        continue
                    is_correct = (j == correct_answer_index)
                    new_answer = Answer(question_id=new_question.id, answer_text=a_text.strip(), is_correct=is_correct)
                    db.session.add(new_answer)
            
            db.session.commit()
            flash(f"'{quiz_title}' quizi başarıyla eklendi.", "success")
            return redirect(url_for('admin_panel'))
        
        flash("Geçersiz işlem veya eksik veri.", "danger")
        return redirect(url_for('admin_panel'))

    users = User.query.order_by(User.username).all()
    dersler = Ders.query.order_by(Ders.name).all()
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).all()


    total_users_count = User.query.count()
    active_users_count = User.query.filter(User.expire_date > datetime.utcnow()).count()

    course_completion_counts = db.session.query(
        Ders.name,
        func.count(UserProgress.id)
    ).join(Konu, Ders.id == Konu.ders_id)\
     .join(AltBaslik, Konu.id == AltBaslik.konu_id)\
     .join(UserProgress, AltBaslik.id == UserProgress.alt_baslik_id)\
     .group_by(Ders.name)\
     .order_by(func.count(UserProgress.id).desc())\
     .all()

    chart_labels = [row[0] for row in course_completion_counts]
    chart_data = [row[1] for row in course_completion_counts]
    
    return render_template('admin.html', 
                           users=users, 
                           dersler=dersler, 
                           is_main_admin=is_main_admin,
                           announcements=announcements,
                           total_users_count=total_users_count,
                           active_users_count=active_users_count,
                           chart_labels=chart_labels,
                           chart_data=chart_data)


@app.route("/panel", methods=["GET"])
@login_required
def user_panel():
    # current_app.logger.debug("--- user_panel fonksiyonu çağrıldı ---") # Yorum satırı yapıldı
    dersler = Ders.query.order_by(Ders.name).all()
    
    selected_ders_id = request.args.get('ders_id', type=int)
    selected_konu_id = request.args.get('konu_id', type=int)
    
    selected_ders = Ders.query.get(selected_ders_id) if selected_ders_id else None
    selected_konu = Konu.query.get(selected_konu_id) if selected_konu_id else None

    user = User.query.get(session['user_id'])
    kalan_gun = None
    if user.expire_date:
        remaining_time = (user.expire_date + timedelta(days=1)) - datetime.utcnow()
        kalan_gun = max(0, remaining_time.days)
        if kalan_gun == 0 and remaining_time.total_seconds() <= 0:
            kalan_gun = 0
        elif kalan_gun == 0 and remaining_time.total_seconds() > 0:
            pass

    completed_alt_baslik_ids = set()
    if user:
        progress_records = UserProgress.query.filter_by(user_id=user.id).all()
        completed_alt_baslik_ids = {p.alt_baslik_id for p in progress_records}
    # current_app.logger.debug(f"DEBUG: Kullanıcının tamamladığı alt başlık ID'leri: {completed_alt_baslik_ids}") # Yorum satırı yapıldı

    unique_recommended_alt_basliks = []

    completion_percentage = 0
    if selected_konu:
        total_alt_basliks_in_konu = len(selected_konu.alt_basliklar)
        if total_alt_basliks_in_konu > 0:
            completed_count_in_konu = 0
            for alt_baslik in selected_konu.alt_basliklar:
                if alt_baslik.id in completed_alt_baslik_ids:
                    completed_count_in_konu += 1
            completion_percentage = int((completed_count_in_konu / total_alt_basliks_in_konu) * 100)

    active_announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).all()

    from sqlalchemy.orm import joinedload
    # user_quiz_attempts = db.session.query(UserQuizAttempt).filter_by(user_id=session['user_id']).options(joinedload(UserQuizAttempt.quiz)).all() # Yorum satırı yapıldı
    # user_quiz_attempts_map = {attempt.quiz_id: attempt for attempt in user_quiz_attempts} # Yorum satırı yapıldı

    return render_template('user.html', 
                           dersler=dersler, 
                           selected_ders=selected_ders, 
                           selected_konu=selected_konu, 
                           kalan_gun=kalan_gun,
                           completed_alt_baslik_ids=completed_alt_baslik_ids,
                           completion_percentage=completion_percentage,
                           active_announcements=active_announcements,
                           recommended_alt_basliks=unique_recommended_alt_basliks,
                           UserQuizAttempt=UserQuizAttempt,
                           session=session
                           )

@app.route("/mark_completed", methods=["POST"])
@login_required
def mark_completed():
    alt_baslik_id = request.form.get("alt_baslik_id", type=int)
    user_id = session.get("user_id")

    if not alt_baslik_id or not user_id:
        flash("Geçersiz istek.", "danger")
        return redirect(url_for('user_panel'))

    alt_baslik = AltBaslik.query.get(alt_baslik_id)
    if not alt_baslik:
        flash("Alt başlık bulunamadı.", "danger")
        return redirect(url_for('user_panel'))

    existing_progress = UserProgress.query.filter_by(user_id=user_id, alt_baslik_id=alt_baslik_id).first()

    if existing_progress:
        db.session.delete(existing_progress)
        db.session.commit()
        flash(f"'{alt_baslik.name}' tamamlandı işareti kaldırıldı.", "info")
    else:
        new_progress = UserProgress(user_id=user_id, alt_baslik_id=alt_baslik_id)
        db.session.add(new_progress)
        db.session.commit()
        flash(f"'{alt_baslik.name}' başarıyla tamamlandı olarak işaretlendi.", "success")
    
    selected_ders_id = request.form.get("selected_ders_id", type=int)
    selected_konu_id = request.form.get("selected_konu_id", type=int)
    return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))

@app.route("/submit_quiz", methods=["POST"])
@login_required
def submit_quiz():
    user_id = session.get("user_id")
    quiz_id = request.form.get("quiz_id", type=int)
    alt_baslik_id = request.form.get("alt_baslik_id", type=int)
    selected_ders_id = request.form.get("selected_ders_id", type=int)
    selected_konu_id = request.form.get("selected_konu_id", type=int)

    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        flash("Quiz bulunamadı.", "danger")
        return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))

    correct_answers_count = 0
    total_questions = len(quiz.questions)

    if total_questions == 0:
        flash("Bu quizde soru bulunmamaktadır.", "warning")
        return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))

    for question in quiz.questions:
        selected_answer_id = request.form.get(f"question_{question.id}", type=int)
        if selected_answer_id:
            selected_answer = Answer.query.get(selected_answer_id)
            if selected_answer and selected_answer.is_correct:
                correct_answers_count += 1
    
    score = int((correct_answers_count / total_questions) * 100) if total_questions > 0 else 0

    user_attempt = UserQuizAttempt.query.filter_by(user_id=user_id, quiz_id=quiz_id).first()
    if user_attempt:
        user_attempt.score = score
        user_attempt.attempt_date = datetime.utcnow()
    else:
        new_attempt = UserQuizAttempt(user_id=user_id, quiz_id=quiz_id, score=score)
        db.session.add(new_attempt)
    
    db.session.commit()
    flash(f"Quizi tamamladınız! Puanınız: {score}%", "success")

    return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))

@app.route("/delete_quiz_attempt", methods=["POST"])
@login_required
def delete_quiz_attempt():
    quiz_attempt_id = request.form.get("quiz_attempt_id", type=int)
    selected_ders_id = request.form.get("selected_ders_id", type=int)
    selected_konu_id = request.form.get("selected_konu_id", type=int)

    attempt = UserQuizAttempt.query.get(quiz_attempt_id)
    if attempt and attempt.user_id == session.get('user_id'):
        db.session.delete(attempt)
        db.session.commit()
        flash("Quiz denemeniz başarıyla silindi.", "info")
    else:
        flash("Quiz denemesi bulunamadı veya silme yetkiniz yok.", "danger")

    return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))


@app.route("/add_comment", methods=["POST"])
@login_required
def add_comment():
    user_id = session.get("user_id")
    alt_baslik_id = request.form.get("alt_baslik_id", type=int)
    comment_content = request.form.get("comment_content", "").strip()
    parent_comment_id = request.form.get("parent_comment_id", type=int) or None
    
    selected_ders_id = request.form.get("selected_ders_id", type=int)
    selected_konu_id = request.form.get("selected_konu_id", type=int)

    if not comment_content:
        flash("Yorum içeriği boş olamaz.", "danger")
    elif not alt_baslik_id:
        flash("Yorum yapılacak alt başlık belirtilmemiş.", "danger")
    else:
        new_comment = Comment(
            user_id=user_id,
            alt_baslik_id=alt_baslik_id,
            content=comment_content,
            parent_comment_id=parent_comment_id
        )
        db.session.add(new_comment)
        db.session.commit()
        flash("Yorumunuz başarıyla eklendi.", "success")
    
    return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))

@app.route("/delete_comment", methods=["POST"])
@login_required
def delete_comment():
    comment_id = request.form.get("comment_id", type=int)
    selected_ders_id = request.form.get("selected_ders_id", type=int)
    selected_konu_id = request.form.get("selected_konu_id", type=int)

    comment_to_delete = Comment.query.get(comment_id)

    if not comment_to_delete:
        flash("Yorum bulunamadı.", "danger")
    elif comment_to_delete.user_id != session.get('user_id') and not session.get('is_admin'):
        flash("Bu yorumu silme yetkiniz yok.", "danger")
    else:
        db.session.delete(comment_to_delete)
        db.session.commit()
        flash("Yorum başarıyla silindi.", "success")
    
    return redirect(url_for('user_panel', ders_id=selected_ders_id, konu_id=selected_konu_id))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if not user:
        flash("Kullanıcı bulunamadı.", "danger")
        return redirect(url_for('login'))

    kalan_gun = None
    if user.expire_date:
        remaining_time = (user.expire_date + timedelta(days=1)) - datetime.utcnow()
        kalan_gun = max(0, remaining_time.days)
        if kalan_gun == 0 and remaining_time.total_seconds() <= 0:
            kalan_gun = 0
        elif kalan_gun == 0 and remaining_time.total_seconds() > 0:
            pass

    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_new_password = request.form.get("confirm_new_password")

        if not check_password_hash(user.password, old_password):
            flash("Mevcut şifreniz yanlış.", "danger")
        elif not new_password or len(new_password) < 6:
            flash("Yeni şifreniz en az 6 karakter olmalıdır.", "danger")
        elif new_password != confirm_new_password:
            flash("Yeni şifreler uyuşmuyor.", "danger")
        else:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash("Şifreniz başarıyla güncellendi.", "success")
        
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user, kalan_gun=kalan_gun)

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    user = User.query.get(session['user_id'])
    if not user or (user.expire_date and datetime.utcnow() >= (user.expire_date + timedelta(days=1))):
        flash("Dosyayı indirme yetkiniz bulunmamaktadır. Erişim süreniz dolmuş olabilir.", "danger")
        return redirect(url_for('user_panel'))
        
    material = Material.query.filter_by(filename=filename).first()
    if not material:
        flash("İndirilecek dosya bulunamadı.", "danger")
        return redirect(url_for('user_panel'))
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True, download_name=material.original_filename)

# --- DÜZENLEME ROTLARI ---

@app.route("/admin/edit_ders/<int:ders_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_ders(ders_id):
    ders = Ders.query.get_or_404(ders_id)
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        if new_name and new_name != ders.name:
            existing_ders = Ders.query.filter(Ders.name == new_name, Ders.id != ders_id).first()
            if existing_ders:
                flash("Bu ders adı zaten mevcut.", "danger")
            else:
                ders.name = new_name
                db.session.commit()
                flash(f"'{ders.name}' dersi başarıyla güncellendi.", "success")
                return redirect(url_for('admin_panel'))
        else:
            flash("Ders adı boş olamaz veya aynı isimde bir ders zaten mevcut.", "danger")
        return redirect(url_for('edit_ders', ders_id=ders.id))
    return render_template('edit_ders.html', ders=ders)

@app.route("/admin/edit_konu/<int:konu_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_konu(konu_id):
    konu = Konu.query.get_or_404(konu_id)
    dersler = Ders.query.order_by(Ders.name).all()
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_ders_id = request.form.get("ders_id", type=int)

        if not new_name or not new_ders_id:
            flash("Konu adı veya ders seçimi boş olamaz.", "danger")
        else:
            existing_konu = Konu.query.filter(
                Konu.name == new_name, 
                Konu.ders_id == new_ders_id, 
                Konu.id != konu_id
            ).first()
            if existing_konu:
                flash("Bu ders altında aynı isimde bir konu zaten mevcut.", "danger")
            else:
                konu.name = new_name
                konu.ders_id = new_ders_id
                db.session.commit()
                flash(f"'{konu.name}' konusu başarıyla güncellendi.", "success")
                return redirect(url_for('admin_panel'))
        return redirect(url_for('edit_konu', konu_id=konu.id))
    return render_template('edit_konu.html', konu=konu, dersler=dersler)


@app.route("/admin/edit_alt_baslik/<int:alt_baslik_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_alt_baslik(alt_baslik_id):
    alt_baslik = AltBaslik.query.get_or_404(alt_baslik_id)
    dersler = Ders.query.order_by(Ders.name).all()
    
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_video_link = request.form.get("video_link", "").strip()
        new_notlar = request.form.get("notlar", "").strip()
        new_konu_id = request.form.get("konu_id", type=int)

        if not new_name or not new_konu_id:
            flash("Alt başlık adı veya konu seçimi boş olamaz.", "danger")
        else:
            existing_alt_baslik = AltBaslik.query.filter(
                AltBaslik.name == new_name,
                AltBaslik.konu_id == new_konu_id,
                AltBaslik.id != alt_baslik_id
            ).first()
            if existing_alt_baslik:
                flash("Bu konu altında aynı isimde bir alt başlık zaten mevcut.", "danger")
            else:
                alt_baslik.name = new_name
                alt_baslik.video_link = new_video_link
                alt_baslik.notlar = new_notlar
                alt_baslik.konu_id = new_konu_id
                db.session.commit()
                flash(f"'{alt_baslik.name}' alt başlığı başarıyla güncellendi.", "success")
                return redirect(url_for('admin_panel'))
        return redirect(url_for('edit_alt_baslik', alt_baslik_id=alt_baslik.id))
    return render_template('edit_alt_baslik.html', alt_baslik=alt_baslik, dersler=dersler)


# dersplanlama.py dosyasının en altına, app.run() çağrısından hemen önce ekle.
# Bu kod, uygulamanın her deployunda veya yeniden başlatıldığında çalışır.
# Sadece admin kullanıcısı oluşturulduktan sonra KALDIRILMALIDIR!

with app.app_context(): # Flask uygulama bağlamına gir
    # Veritabanında hiç kullanıcı yoksa varsayılan admin kullanıcısını oluştur
    # VEYA sadece 'admin' kullanıcısı yoksa oluştur
    if User.query.filter_by(username='admin').first() is None:
        print("Admin kullanıcısı bulunamadı. Varsayılan admin kullanıcısı oluşturuluyor...")
        admin_username = 'admin'
        admin_password = 'Cemyildiz10.' # BURAYA KENDİ ÇOK GÜVENLİ ŞİFRENİ YAZ!

        hashed_password = generate_password_hash(admin_password)
        default_admin = User(username=admin_username, password=hashed_password, is_admin=True, expire_date=None) 

        db.session.add(default_admin)
        db.session.commit()
        print(f"Varsayılan admin kullanıcısı '{admin_username}' başarıyla oluşturuldu.")
    else:
        print("Admin kullanıcısı zaten mevcut. Yeni admin oluşturulmadı.")

if __name__ == '__main__':
    app.run(debug=True)
    # Flask uygulaması bağlamına girerek ilk çalıştırmada admin kullanıcısı oluştur
    with app.app_context():
        # Veritabanında hiç kullanıcı yoksa varsayılan admin kullanıcısını oluştur
        if User.query.count() == 0:
            print("Veritabanında hiç kullanıcı bulunamadı. Varsayılan admin kullanıcısı oluşturuluyor...")
            admin_username = 'admin'
            admin_password = 'Cemyildiz10.' # Lütfen BURAYA KENDİ GÜVENLİ ŞİFRENİ YAZ!

            hashed_password = generate_password_hash(admin_password)
            # expire_date=None yaparak süresiz erişim sağla
            default_admin = User(username=admin_username, password=hashed_password, is_admin=True, expire_date=None) 

            db.session.add(default_admin)
            db.session.commit()
            print(f"Varsayılan admin kullanıcısı '{admin_username}' oluşturuldu.")
        else:
            print("Veritabanında kullanıcılar zaten mevcut. Yeni admin oluşturulmadı.")

    app.run(debug=True)