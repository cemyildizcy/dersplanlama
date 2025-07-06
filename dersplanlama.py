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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'varsayilan_cok_gizli_bir_anahtar_12345')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///dersplanlama.db')
# ...
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# // --- GEÇİCİ KOD BAŞLANGICI (BURAYI EKLEYİN) --- //
with app.app_context():
    db.create_all()
# // --- GEÇİCİ KOD BİTİŞİ --- //

# --- VERİTABANI MODELLERİ (JSON yerine artık bunları kullanacağız) ---
class User(db.Model):
# ...


# --- VERİTABANI MODELLERİ (JSON yerine artık bunları kullanacağız) ---

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

# Giriş yapmayı gerektiren sayfalar için bir decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin olmayı gerektiren sayfalar için bir decorator
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
            
            if user.is_admin:
                return redirect(url_for("admin_panel"))
            else:
                return redirect(url_for("user_panel"))
        else:
            flash("Hatalı kullanıcı adı veya şifre!", "danger")
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
    # Admin paneli için gerekli tüm verileri veritabanından çek
    users = User.query.order_by(User.username).all()
    dersler = Ders.query.order_by(Ders.name).all()
    is_main_admin = session.get("username") == "admin"

    # --- POST İŞLEMLERİ (Form Gönderimleri) ---
    if request.method == "POST":
        action = request.form.get("action")

        # Yeni Kullanıcı Ekleme
        if action == "add_user" and is_main_admin:
            username = request.form.get("new_username")
            password = request.form.get("new_password")
            access_days = request.form.get("access_days", type=int)

            if User.query.filter_by(username=username).first():
                flash("Bu kullanıcı adı zaten mevcut.", "danger")
            else:
                hashed_password = generate_password_hash(password)
                expire_date = datetime.utcnow() + timedelta(days=access_days) if access_days else None
                new_user = User(username=username, password=hashed_password, is_admin=False, expire_date=expire_date)
                db.session.add(new_user)
                db.session.commit()
                flash(f"{username} kullanıcısı başarıyla eklendi.", "success")
            return redirect(url_for('admin_panel'))

        # Erişim Süresi Güncelleme
        if action == "update_user" and is_main_admin:
            user_id = request.form.get("update_user_id", type=int)
            update_days = request.form.get("update_days", type=int)
            user_to_update = User.query.get(user_id)
            if user_to_update and update_days:
                user_to_update.expire_date = datetime.utcnow() + timedelta(days=update_days)
                db.session.commit()
                flash(f"{user_to_update.username} kullanıcısının erişim süresi güncellendi.", "success")
            return redirect(url_for('admin_panel'))
            
        # Yeni Ders Ekleme
        if action == "add_ders":
            ders_name = request.form.get("yeni_ders")
            if ders_name and not Ders.query.filter_by(name=ders_name).first():
                new_ders = Ders(name=ders_name)
                db.session.add(new_ders)
                db.session.commit()
                flash("Ders başarıyla eklendi.", "success")
            else:
                flash("Ders adı boş olamaz veya bu ders zaten mevcut.", "danger")
            return redirect(url_for('admin_panel'))

        # Yeni Konu Ekleme
        if action == "add_konu":
            konu_name = request.form.get("yeni_konu")
            ders_id = request.form.get("ders_sec_konu", type=int)
            if konu_name and ders_id:
                new_konu = Konu(name=konu_name, ders_id=ders_id)
                db.session.add(new_konu)
                db.session.commit()
                flash("Konu başarıyla eklendi.", "success")
            else:
                flash("Konu adı veya ders seçimi boş olamaz.", "danger")
            return redirect(url_for('admin_panel'))

        # Yeni Alt Başlık Ekleme
        if action == "add_alt_baslik":
            alt_baslik_name = request.form.get("alt_baslik")
            konu_id = request.form.get("konu_sec_alt", type=int)
            video_link = request.form.get("video")
            notlar = request.form.get("notlar")
            if alt_baslik_name and konu_id:
                new_alt_baslik = AltBaslik(name=alt_baslik_name, konu_id=konu_id, video_link=video_link, notlar=notlar)
                db.session.add(new_alt_baslik)
                db.session.commit()
                flash("Alt başlık başarıyla eklendi.", "success")
            else:
                flash("Alt başlık veya konu seçimi boş olamaz.", "danger")
            return redirect(url_for('admin_panel'))
    
    # --- GET İŞLEMLERİ (Silme vb.) ---
    delete_type = request.args.get("delete_type")
    delete_id = request.args.get("id", type=int)
    if delete_type and delete_id:
        if delete_type == "ders":
            item_to_delete = Ders.query.get_or_404(delete_id)
        elif delete_type == "konu":
            item_to_delete = Konu.query.get_or_404(delete_id)
        elif delete_type == "alt_baslik":
            item_to_delete = AltBaslik.query.get_or_404(delete_id)
        elif delete_type == "user" and is_main_admin:
            item_to_delete = User.query.get_or_404(delete_id)
        else:
            item_to_delete = None
        
        if item_to_delete:
            db.session.delete(item_to_delete)
            db.session.commit()
            flash(f"{delete_type.capitalize()} başarıyla silindi.", "success")
        return redirect(url_for('admin_panel'))
    
    return render_template('admin.html', users=users, dersler=dersler, is_main_admin=is_main_admin)


@app.route("/panel", methods=["GET"])
@login_required
def user_panel():
    # Tüm dersleri her zaman al
    dersler = Ders.query.order_by(Ders.name).all()
    
    # URL'den gelen ID'leri al
    selected_ders_id = request.args.get('ders_id', type=int)
    selected_konu_id = request.args.get('konu_id', type=int)
    
    selected_ders = None
    selected_konu = None
    
    if selected_ders_id:
        selected_ders = Ders.query.get(selected_ders_id)
    
    if selected_konu_id:
        selected_konu = Konu.query.get(selected_konu_id)

    # Kalan gün hesabını yap
    user = User.query.get(session['user_id'])
    kalan_gun = None
    if user.expire_date:
        delta = user.expire_date.date() - datetime.utcnow().date()
        kalan_gun = max(delta.days, 0)
    
    # Session'a da kalan günü ekleyelim ki her yerde kullanabilelim
    session['kalan_gun'] = kalan_gun

    return render_template(
        'user.html',
        dersler=dersler,
        selected_ders=selected_ders,
        selected_konu=selected_konu,
        kalan_gun=kalan_gun
    )
# Bu blok sadece bilgisayarda `python app.py` komutuyla çalıştırıldığında devreye girer.
# Render bu bloğu görmez, Gunicorn'u kullanır.
# Bu blok sadece bilgisayarda `python app.py` komutuyla çalıştırıldığında devreye girer.
# Render bu bloğu görmez, Gunicorn'u kullanır.
# Bu blok sadece bilgisayarda `python app.py` komutuyla çalıştırıldığında devreye girer.
if __name__ == '__main__':
    with app.app_context():
        # Veritabanında tablolar var mı diye kontrol et, yoksa oluştur.
        db.create_all()

        # --- İLK ADMİN KULLANICISINI OLUŞTURMA KODU ---
        # Veritabanında 'admin' adında bir kullanıcı var mı diye kontrol et
        if not User.query.filter_by(username='admin').first():
            # Eğer yoksa, şifresini hash'leyerek oluştur
            hashed_password = generate_password_hash('Cemyildiz10.')
            admin_user = User(username='admin', password=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
            print("Varsayılan Admin kullanıcısı oluşturuldu.")
        # ------------------------------------------------

    app.run(debug=True)