#!/bin/bash

# Hata oluşursa betiği durdur
set -e

echo "--- Veritabanı migrasyonları çalıştırılıyor ---"
# Flask uygulamasını bulmak için FLASK_APP ortam değişkenini ayarla
export FLASK_APP=dersplanlama:app
# Veritabanı migrasyonlarını çalıştır
flask db upgrade

# YENİ EKLENEN KISIM: Admin kullanıcısını oluşturmak için özel komut
echo "--- Admin kullanıcısı kontrol ediliyor/oluşturuluyor ---"
flask create-initial-admin # python3 -m flask kullanmaya gerek yoksa

echo "--- Uygulama başlatılıyor ---"
# CMD'den gelen komutu çalıştır (gunicorn)
exec "$@"