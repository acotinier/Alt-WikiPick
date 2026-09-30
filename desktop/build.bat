@echo off
REM Construit Alt-WikiPick Desktop (Windows) : dist\WikiPickDesktop\ puis dist\Alt-WikiPick-windows.zip.
REM Prerequis : Python 3.10+ installe (commande "py"). Se lance depuis n'importe ou.
REM Mode dossier (--onedir) : l'appli demarre tout de suite, sans se decompresser a chaque lancement comme un .exe unique.
cd /d "%~dp0.."
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onedir --windowed --name WikiPickDesktop --icon desktop\icon.ico --paths . --add-data "desktop\web;web" desktop\app.py
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "Compress-Archive -Path 'dist\WikiPickDesktop' -DestinationPath 'dist\Alt-WikiPick-windows.zip' -Force"
echo.
echo Termine :
echo   dist\WikiPickDesktop\WikiPickDesktop.exe   (garde tout le dossier ensemble)
echo   dist\Alt-WikiPick-windows.zip              (a partager)
pause
