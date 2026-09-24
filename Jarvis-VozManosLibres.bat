@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m src.main_voz_wakeword
pause
