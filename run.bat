@echo off
REM Lance l'appli sans construire l'exe (pratique pour tester).
cd /d "%~dp0"
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
python app.py
