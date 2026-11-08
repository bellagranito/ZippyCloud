@echo off
chcp 65001 > nul
call .venv\Scripts\activate.bat
python -m flask --app app run --host=127.0.0.1 --port=5000 --no-reload
pause
