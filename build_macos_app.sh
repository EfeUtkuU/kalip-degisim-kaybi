#!/bin/bash
# "KalipDegisimKaybi.app" uygulamasını tek komutla üretir.
# Bir kez çalıştırman yeterli. Sonra backend/dist/"KalipDegisimKaybi.app" dosyasını
# Applications klasörüne sürükle; çift tıklayarak açılır (Terminal gerekmez).
#
# Gereksinim: Homebrew ile python3 ve node  (brew install python node)
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/5: Arayüz derleniyor =="
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

echo "== 2/5: Arayüz arka uca kopyalanıyor =="
rm -rf backend/frontend_dist
cp -R frontend/dist backend/frontend_dist

echo "== 3/5: Python ortamı hazırlanıyor =="
cd backend
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-desktop.txt

echo "== 4/5: Simge hazırlanıyor =="
python3 make_icon.py || echo "Simge üretilemedi, varsayılan simge kullanılacak."
[ -f icon.icns ] || sed -i '' 's/, icon="icon.icns"//' KalipDegisimKaybi.spec

echo "== 5/5: .app paketleniyor (birkaç dakika sürebilir) =="
rm -rf build dist
pyinstaller --noconfirm KalipDegisimKaybi.spec

APP="dist/KalipDegisimKaybi.app"
xattr -cr "$APP" || true
codesign --force --deep --sign - "$APP" || echo "Uyarı: imzalama başarısız; ilk açılışta sağ tık -> Aç ile onayla."

echo
echo "Bitti: backend/$APP"
echo "Applications klasörüne sürükle. İlk açılışta 'bilinmeyen geliştirici' uyarısı çıkarsa:"
echo "uygulamaya sağ tık -> Aç -> tekrar Aç."
