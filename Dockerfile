# 1. Adım: Python 3.11'in resmi, hafif bir versiyonunu temel al
FROM python:3.11-slim

# 2. Adım: Konteyner içinde /app adında bir çalışma dizini oluştur
WORKDIR /app

# 3. Adım: Önce sadece kütüphane listesini kopyala (önbellekleme için daha verimli)
COPY requirements.txt .

# 4. Adım: Tüm kütüphaneleri kur
RUN pip install -r requirements.txt

# 5. Adım: Proje kodunun geri kalanını /app dizinine kopyala
COPY . .

# 6. Adım: Uygulamayı başlatacak komutu tanımla
# Not: Render'ın beklediği port 10000'dir. Gunicorn uygulamayı bu portta başlatacak.
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "dersplanlama:app"]