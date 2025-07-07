# Gerekli kütüphaneleri ve modülleri import ediyoruz
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # YENİ EKLENDİ
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps

# --- UYGULAMA VE VERİTABANI KURULUMU ---

app = Flask(__name__)

# Güvenli konfigürasyon: Ayarları ortam değişkenlerinden alıyoruz
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'varsayilan_cok_gizli_bir_anahtar_12345')
database_url = os.environ.get('DATABASE_URL', 'sqlite:///dersplanlama.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Veritabanı nesnesini ve Migrate nesnesini oluşturuyoruz
db = SQLAlchemy(app)
migrate = Migrate(app, db) # YENİ EKLENDİ

# --- VERİTABANI MODELLERİ (Aynı kalıyor) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    expire_date = db.Column(db.DateTime)

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


# --- YARDIMCI FONKSİYONLAR (Aynı kalıyor) ---
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


# --- ROTALAR (SAYFALAR) (Aynı kalıyor) ---
# (Tüm @app.route fonksiyonların burada...)
@app.route("/", methods=["GET", "POST"])
def login():
    # ... (içeriği aynı)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if user.expire_date and user.expire_date.date() < datetime.utcnow().date():
                flash("Erişim süreniz dolmuştur.", "danger")
                return redirect(url_for('login'))
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            
            return redirect(url_for("admin_panel" if user.is_admin else "user_panel"))
        else:
            flash("Hatalı kullanıcı adı veya şifre!", "danger")
            return redirect(url_for('login'))
            
    return render_template('login.html')

# ... (Diğer tüm @app.route fonksiyonları aynı kalacak şekilde buraya gelecek)
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
        if action == "add_user" and is_main_admin:
            #... (Tüm POST mantığı aynı)
            username = request.form.get("new_username", "").strip()
            password = request.form.get("new_password", "").strip()
            access_days_str = request.form.get("access_days", "").strip()

            if not username or not password:
                flash("Kullanıcı adı ve şifre boş olamaz.", "danger")
            elif User.query.filter_by(username=username).first():
                flash("Bu kullanıcı adı zaten mevcut.", "danger")
            else:
                hashed_password = generate_password_hash(password)
                expire_date = None
                if access_days_str.isdigit():
                    expire_date = datetime.utcnow() + timedelta(days=int(access_days_str))
                
                new_user = User(username=username, password=hashed_password, is_admin=False, expire_date=expire_date)
                db.session.add(new_user)
                db.session.commit()
                flash(f"'{username}' kullanıcısı başarıyla eklendi.", "success")
            return redirect(url_for('admin_panel'))
        #... Diğer action'lar
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
    
    delete_type = request.args.get("delete_type")
    delete_id = request.args.get("id", type=int)
    if delete_type and delete_id:
        item_to_delete = None
        if delete_type == "ders": item_to_delete = Ders.query.get_or_404(delete_id)
        elif delete_type == "konu": item_to_delete = Konu.query.get_or_404(delete_id)
        elif delete_type == "alt_baslik": item_to_delete = AltBaslik.query.get_or_404(delete_id)
        elif delete_type == "user" and is_main_admin: item_to_delete = User.query.get_or_404(delete_id)
        
        if item_to_delete:
            if delete_type == 'user' and item_to_delete.username == 'admin':
                flash("Ana admin kullanıcısı silinemez.", "danger")
            else:
                db.session.delete(item_to_delete)
                db.session.commit()
                flash(f"{delete_type.capitalize()} başarıyla silindi.", "success")
        return redirect(url_for('admin_panel'))

    users = User.query.order_by(User.username).all()
    dersler = Ders.query.order_by(Ders.name).all()
    
    return render_template('admin.html', users=users, dersler=dersler, is_main_admin=is_main_admin)


@app.route("/panel", methods=["GET"])
@login_required
def user_panel():
    dersler = Ders.query.order_by(Ders.name).all()
    
    selected_ders_id = request.args.get('ders_id', type=int)
    selected_konu_id = request.args.get('konu_id', type=int)
    
    selected_ders = Ders.query.get(selected_ders_id) if selected_ders_id else None
    selected_konu = Konu.query.get(selected_konu_id) if selected_konu_id else None

    user = User.query.get(session['user_id'])
    kalan_gun = None
    if user.expire_date:
        delta = user.expire_date.date() - datetime.utcnow().date()
        kalan_gun = max(delta.days, 0)
    
    return render_template('user.html', dersler=dersler, selected_ders=selected_ders, selected_konu=selected_konu, kalan_gun=kalan_gun)



# Lokalde çalıştırmak için `if __name__` bloğu aynı kalıyor
if __name__ == '__main__':
    app.run(debug=True)