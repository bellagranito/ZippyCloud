@echo off
chcp 65001 > nul
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python seed.py
echo.
echo Instalacao concluida.
echo Para iniciar depois, execute INICIAR_ZIPPY.bat
pause
