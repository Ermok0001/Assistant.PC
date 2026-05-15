@echo off
echo [BUILDING PIKA...]
cd /d "%~dp0"
rd /s /q build
rd /s /q dist
:: Здесь мы берем любой файл, который вы положили как pike.png
python -m PyInstaller --noconsole --onefile --add-data "pike.png;." assistant.py
echo [SUCCESS! Проверьте папку dist, сэр.]
pause