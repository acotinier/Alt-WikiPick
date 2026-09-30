@echo off
REM Lance l'appli de bureau sans construire l'exe (pratique pour tester). Se lance depuis n'importe ou.
cd /d "%~dp0.."
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
python desktop\app.py
