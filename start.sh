#!/bin/bash

echo "--- Başlangıç öncesi komutlar çalıştırılıyor ---"

# pip'i güncelleyin (isteğe bağlı ama iyi bir pratik)
python3 -m pip install --upgrade pip

# Bağımlılıkları yükleyin
python3 -m pip install -r requirements.txt

# Veritabanı migrasyonlarını çalıştırın
python3 -m flask db upgrade

echo "--- Uygulama başlatılıyor ---"
# Gunicorn sunucusunu başlatın
python3 -m gunicorn dersplanlama:app