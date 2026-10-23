@echo off
REM "KalipDegisimKaybi" Windows uygulamasini tek komutla uretir.
REM Gereksinim: Python 3.10+ ve Node.js (python.org ve nodejs.org). Cift tiklayarak calistirabilirsin.
setlocal
cd /d "%~dp0"

echo == 1/4: Arayuz derleniyor ==
cd frontend
call npm install --no-audit --no-fund || goto :hata
call npm run build || goto :hata
cd ..

echo == 2/4: Arayuz arka uca kopyalaniyor ==
if exist backend\frontend_dist rmdir /s /q backend\frontend_dist
xcopy /e /i /q frontend\dist backend\frontend_dist >nul || goto :hata

echo == 3/4: Python ortami hazirlaniyor ==
cd backend
if not exist .venv python -m venv .venv || goto :hata
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-desktop.txt || goto :hata
python make_icon.py

echo == 4/4: Uygulama paketleniyor (birkac dakika surebilir) ==
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm KalipDegisimKaybi.spec || goto :hata

echo.
echo Bitti: backend\dist\KalipDegisimKaybi\KalipDegisimKaybi.exe
echo Klasorun tamamini istedigin yere kopyala; exe dosyasina cift tikla.
pause
exit /b 0

:hata
echo.
echo Bir adim basarisiz oldu. Yukaridaki hata mesajina bak.
pause
exit /b 1
