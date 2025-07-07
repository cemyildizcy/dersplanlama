#!/bin/bash

# Hata oluşursa betiği durdur
set -e

echo "--- Veritabanı migrasyonları çalıştırılıyor ---"
# Flask uygulamasını bulmak için FLASK_APP ortam değişkenini ayarla
export FLASK_APP=dersplanlama:app
# Veritabanı migrasyonlarını çalıştır
flask db upgrade

echo "--- Uygulama başlatılıyor ---"
# CMD'den gelen komutu çalıştır (gunicorn)
exec "$@"
