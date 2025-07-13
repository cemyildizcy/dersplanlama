#!/bin/bash

echo "--- Başlangıç öncesi komutlar çalıştırılıyor ---"

# pip'i güncelleyin (isteğe bağlı ama iyi bir pratik)
python3 -m pip install --upgrade pip

# Bağımlılıkları yükleyin
python3 -m pip install -r requirements.txt

# Flask uygulamasını bulmak için FLASK_APP ortam değişkenini ayarla
export FLASK_APP=dersplanlama:app

# Veritabanı migrasyonlarını çalıştırın
python3 -m flask db upgrade

# YENİ EKLENEN KISIM: Admin kullanıcısını oluşturmak için özel komut
echo "--- Admin kullanıcısı kontrol ediliyor/oluşturuluyor ---"
python3 -m flask create-initial-admin

echo "--- Uygulama başlatılıyor ---"
# Gunicorn sunucusunu başlatın
python3 -m gunicorn dersplanlama:app