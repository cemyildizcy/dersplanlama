# Gerekli kütüphaneleri ve modülleri import ediyoruz
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps

# --- UYGULAMA VE VERİTABANI KURULUMU ---

app = Flask(__name__)

# Güvenli konfigürasyon: Ayarları ortam değişkenlerinden alıyoruz
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bu-sadece-lokalde-calisirken-kullanilacak-gecici-anahtar')
# Render'daki DATABASE_URL'yi kullan, yoksa lokaldeki sqlite dosyasını kullan
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///dersplanlama.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Veritabanı nesnesini oluşturuyoruz
db = SQLAlchemy(app)


# ==============================================================================

# --- VERİTABANI MODELLERİ ---

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

@app.route("/logout")
def logout():
    session.clear()
    flash("Başarıyla çıkış yaptınız.", "success")
    return redirect(url_for("login"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin_panel():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == "add_ders":
            ders_name = request.form.get("yeni_ders", "").strip()
            if ders_name and not Ders.query.filter_by(name=ders_name).first():
                db.session.add(Ders(name=ders_name))
                db.session.commit()
                flash(f"'{ders_name}' dersi eklendi.", "success")
            else:
                flash("Ders adı boş olamaz veya bu ders zaten mevcut.", "danger")

        # Diğer tüm admin işlemleri buraya eklenecek...
        
        return redirect(url_for('admin_panel'))

    # Sayfa yüklendiğinde tüm verileri veritabanından çek
    dersler = Ders.query.order_by(Ders.name).all()
    users = User.query.order_by(User.username).all()
    is_main_admin = session.get("username") == "admin"
    
    return render_template('admin.html', dersler=dersler, users=users, is_main_admin=is_main_admin)


@app.route("/panel", methods=["GET"])
@login_required
def user_panel():
    dersler = Ders.query.order_by(Ders.name).all()
    
    selected_ders_id = request.args.get('ders_id', type=int)
    selected_konu_id = request.args.get('konu_id', type=int)
    
    selected_ders = Ders.query.get(selected_ders_id) if selected_ders_id else None
    selected_konu = Konu.query.get(selected_konu_id) if selected_konu_id else None

    # Kullanıcının kalan gününü hesapla
    user = User.query.get(session['user_id'])
    kalan_gun = None
    if user.expire_date:
        delta = user.expire_date.date() - datetime.utcnow().date()
        kalan_gun = max(delta.days, 0)
    
    return render_template('user.html', dersler=dersler, selected_ders=selected_ders, selected_konu=selected_konu, kalan_gun=kalan_gun)


# Bu blok sadece bilgisayarda `python app.py` komutuyla çalıştırıldığında devreye girer.
# Render bu bloğu görmez.
if __name__ == '__main__':
    with app.app_context():
        # Veritabanı tablolarını kontrol et, yoksa oluştur
        db.create_all()

        # 'admin' kullanıcısı yoksa oluştur (artık 'User' tanımını biliyor)
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('Cemyildiz10.')
            admin_user = User(username='admin', password=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
            print("--- Varsayılan 'admin' kullanıcısı oluşturuldu. ---")
            
    app.run(debug=True)