"""
Конфиг файл для Pika Assistant
"""
import os
from dotenv import load_dotenv

# Загрузи переменные окружения
load_dotenv()

# API Configuration
API_KEY = os.getenv("GEMINI_API_KEY", "")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY не установлен в переменных окружения!")

WAKE_WORD = "пика"
RELAX_VIDEO_URL = "https://www.youtube.com/watch?v=CFXH1FFOFVM&list=LL&index=1"

# Office shortcuts
OFFICE_SHORTCUTS = {
    "word": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Word 2016.lnk",
    "powerpoint": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PowerPoint 2016.lnk",
    "publisher": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Publisher 2016.lnk",
}

STEAM_LNK = r'C:\Users\Админ\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Steam\Steam.lnk'
DISCORD_LNK = r'C:\Users\Админ\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk'

APPS_DATA = {
    "ворд": ("Word", "start winword", "WINWORD.EXE"),
    "эксель": ("Excel", "start excel", "EXCEL.EXE"),
    "телеграм": ("Telegram", "start telegram", "Telegram.exe"),
    "хром": ("Chrome", "start chrome", "chrome.exe"),
    "гугл": ("Google", "start chrome", "chrome.exe"),
    "стим": ("Steam", STEAM_LNK, "steam.exe"),
    "дискорд": ("Discord", DISCORD_LNK, "Discord.exe"),
    "блокнот": ("Блокнот", "notepad", "notepad.exe"),
    "калькулятор": ("Калькулятор", "calc", "calc.exe"),
    "фотошоп": ("Photoshop", "start photoshop", "Photoshop.exe"),
    "проводник": ("Проводник", "explorer", "explorer.exe"),
    "презентация": ("PowerPoint", "start powerpnt", "POWERPNT.EXE")
}

ADOBE_DATA = {
    "видео": ("Premiere Pro", r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe", "Adobe Premiere Pro.exe"),
    "фото": ("Lightroom", r"C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe", "Lightroom.exe"),
    "эффект": ("After Effects", r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe", "AfterFX.exe")
}

# TTS Configuration
TTS_RATE = 190

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "pika_assistant.log"
