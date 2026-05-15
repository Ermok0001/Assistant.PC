"""
╔══════════════════════════════════════════════╗
║           ПИКА — Голосовой ассистент         ║
║           Версия 3.0 (Fixed)                 ║
╚══════════════════════════════════════════════╝
"""

import os
import uuid
import subprocess
import time
import threading
import sys
import re
import logging
import webbrowser
import tkinter as tk
import ctypes
from datetime import datetime
from pathlib import Path

import psutil
import pyautogui
import pygetwindow as gw
from PIL import Image, ImageTk
import speech_recognition as sr
import asyncio
import edge_tts
from playsound import playsound
import screen_brightness_control as sbc
from google import genai
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# ─────────────────────────────────────────────
#  КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────

# ⚠️ Лучше хранить ключ в .env:
#     pip install python-dotenv
#     Создай файл .env: GEMINI_API_KEY=твой_ключ
# from dotenv import load_dotenv; load_dotenv()
# API_KEY = os.getenv("GEMINI_API_KEY", "")

API_KEY         = "AIzaSyDn1b2QhgwOvGkZoR2m6ZJPMqsq7n0lOqo"   # <-- замени на свой ключ
WAKE_WORD       = "пика"
RELAX_VIDEO     = "https://www.youtube.com/watch?v=CFXH1FFOFVM&list=LL&index=1"
NOTES_FILE      = Path.home() / "Desktop" / "pika_notes.txt"
SCREENSHOTS_DIR = Path.home() / "Pictures"
LOG_FILE        = "pika.log"
VOICE           = "ru-RU-DmitryNeural"

# Пути к приложениям (твои пути — не трогаем)
PATHS = {
    "word_lnk"   : r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Word 2016.lnk",
    "ppt_lnk"    : r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PowerPoint 2016.lnk",
    "pub_lnk"    : r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Publisher 2016.lnk",
    "steam"      : r"C:\Users\Админ\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Steam\Steam.lnk",
    "discord"    : r"C:\Users\Админ\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk",
    "premiere"   : r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
    "lightroom"  : r"C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe",
    "afterfx"    : r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
}

# Словарь приложений { ключевое_слово: (имя, команда/путь, процесс) }
APPS = {
    "ворд"        : ("Word",            "start winword",   "WINWORD.EXE"),
    "эксель"      : ("Excel",           "start excel",     "EXCEL.EXE"),
    "телеграм"    : ("Telegram",        "start telegram",  "Telegram.exe"),
    "хром"        : ("Chrome",          "start chrome",    "chrome.exe"),
    "стим"        : ("Steam",           PATHS["steam"],    "steam.exe"),
    "дискорд"     : ("Discord",         PATHS["discord"],  "Discord.exe"),
    "блокнот"     : ("Блокнот",         "notepad",         "notepad.exe"),
    "калькулятор" : ("Калькулятор",     "calc",            "calc.exe"),
    "фотошоп"     : ("Photoshop",       "start photoshop", "Photoshop.exe"),
    "проводник"   : ("Проводник",       "explorer",        "explorer.exe"),
    "презентация" : ("PowerPoint",      "start powerpnt",  "POWERPNT.EXE"),
    "paint"       : ("Paint",           "mspaint",         "mspaint.exe"),
    "диспетчер"   : ("Диспетчер задач", "taskmgr",         "taskmgr.exe"),
}

ADOBE_APPS = {
    "видео"   : ("Premiere Pro",  PATHS["premiere"],  "Adobe Premiere Pro.exe"),
    "лайтрум" : ("Lightroom",     PATHS["lightroom"], "Lightroom.exe"),
    "эффект"  : ("After Effects", PATHS["afterfx"],   "AfterFX.exe"),
}

# ─────────────────────────────────────────────
#  ЛОГИРОВАНИЕ
# ─────────────────────────────────────────────

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

def log(msg: str, level: str = "info"):
    getattr(logging, level)(msg)

# ─────────────────────────────────────────────
#  TTS  ← ИСПРАВЛЕНО: убрано дублирование функции
# ─────────────────────────────────────────────

def speak(text: str):
    """Озвучивает текст через edge-tts и воспроизводит аудио."""
    # Если текст пустой — ничего не делаем
    if not text or not text.strip():
        return

    print(f"🤖 Пика: {text}")
    log(f"SPEAK: {text}")

    # Уникальное имя файла чтобы не было конфликтов
    unique_filename = f"pika_voice_{uuid.uuid4().hex[:8]}.mp3"

    async def _generate(text_to_say: str, filename: str):
        communicate = edge_tts.Communicate(
            text=text_to_say,
            voice=VOICE,
            rate="+5%",
            pitch="+0Hz",
        )
        await communicate.save(filename)

    try:
        asyncio.run(_generate(text, unique_filename))
        playsound(unique_filename)
    except Exception as e:
        log(f"TTS error: {e}", "error")
        print("Ошибка озвучки:", e)
    finally:
        # Удаляем временный файл
        if os.path.exists(unique_filename):
            try:
                os.remove(unique_filename)
            except Exception as e:
                log(f"Не удалось удалить {unique_filename}: {e}", "warning")

# ─────────────────────────────────────────────
#  АВАТАР (Tkinter, поверх всех окон)
# ─────────────────────────────────────────────

_root:  tk.Tk    | None = None
_label: tk.Label | None = None

STATE_COLORS = {
    "idle"      : "black",
    "listening" : "#00FF00",
    "working"   : "#8A2BE2",
    "error"     : "#FF4444",
}

def update_avatar(state: str = "idle"):
    if not _root or not _label:
        return
    color = STATE_COLORS.get(state, "black")
    _root.config(bg=color)
    _label.config(bg=color)
    _root.attributes("-transparentcolor", "black" if state == "idle" else "")
    _root.update()

def _resource(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative)

def start_avatar():
    global _root, _label
    _root = tk.Tk()
    _root.title("PikaAvatar")
    _root.overrideredirect(True)
    _root.attributes("-topmost", True)
    _root.attributes("-transparentcolor", "black")
    _root.config(bg="black")

    try:
        img   = Image.open(_resource("pike.png")).resize((150, 150))
        photo = ImageTk.PhotoImage(img)
        _label = tk.Label(_root, image=photo, bg="black", bd=0)
        _label.image = photo
    except Exception:
        _label = tk.Label(_root, text="⚡", font=("Arial", 40), bg="black", fg="yellow")

    _label.pack()
    sw, sh = _root.winfo_screenwidth(), _root.winfo_screenheight()
    _root.geometry(f"150x150+{sw - 160}+{sh - 200}")

    def keep_on_top():
        if _root:
            _root.attributes("-topmost", True)
            _root.lift()
            _root.after(2000, keep_on_top)

    keep_on_top()
    _root.mainloop()

# ─────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────

def get_system_status() -> str:
    cpu  = psutil.cpu_percent(interval=0.5)
    ram  = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    return f"Процессор: {cpu}%. Память: {ram}%. Диск: {disk}%."

def set_volume(level: int):
    """Устанавливает громкость системы (0–100)."""
    try:
        devices   = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume    = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
    except Exception as e:
        log(f"set_volume error: {e}", "error")

def launch(cmd: str):
    """Открывает приложение по команде или пути."""
    if "\\" in cmd or "/" in cmd:
        os.startfile(cmd)
    else:
        subprocess.Popen(cmd, shell=True)

def extract_number(text: str, default: int = 50) -> int:
    """
    Извлекает первое число из текста.
    Также понимает русские слова: ноль, десять, двадцать... сто.
    """
    # Сначала ищем цифры
    nums = re.findall(r"\d+", text)
    if nums:
        return int(nums[0])

    # Русские числа-слова
    word_map = {
        "ноль": 0, "нуль": 0,
        "десять": 10, "двадцать": 20, "тридцать": 30,
        "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
        "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
        "сто": 100,
    }
    for word, val in word_map.items():
        if word in text:
            return val

    return default

def save_note(text: str):
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%H:%M %d.%m.%Y}] {text}\n")

def take_screenshot() -> str:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS_DIR / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
    pyautogui.screenshot(str(path))
    return str(path)

def minimize_all_windows():
    """
    Сворачивает все пользовательские окна.
    ← ИСПРАВЛЕНО: добавлены варианты без мягкого знака и улучшена надёжность.
    """
    system_titles = {"", "taskbar", "панель задач", "program manager", "pikaavatar"}

    for win in gw.getAllWindows():
        title_lower = (win.title or "").lower()
        if not win.title:
            continue
        if any(s in title_lower for s in system_titles):
            continue
        try:
            if not win.isMinimized:
                win.minimize()
                time.sleep(0.05)  # небольшая пауза чтобы WinAPI успевал
        except Exception:
            pass

def ask_gemini(client, model_id: str, prompt: str) -> str | None:
    try:
        response = client.models.generate_content(model=model_id, contents=prompt)
        return response.text
    except Exception as e:
        log(f"Gemini error: {e}", "error")
        return None

# ─────────────────────────────────────────────
#  ОБРАБОТЧИКИ КОМАНД
#  Каждый возвращает True если команда обработана
# ─────────────────────────────────────────────

def cmd_exit(t, **_) -> bool:
    keywords = ["стоп", "выключись", "отключись", "пока пика", "до свидания пика"]
    if any(w in t for w in keywords):
        speak("Слушаюсь, сэр. Выключаюсь.")
        time.sleep(1)
        os._exit(0)
    return False


def cmd_sleep_pc(t, **_) -> bool:
    """
    ← ИСПРАВЛЕНО: добавлены все варианты распознавания слова "спать".
    """
    triggers = ["спать", "спящий режим", "ко сну", "сон", "усыпи", "спи"]
    if any(w in t for w in triggers):
        speak("Перевожу компьютер в спящий режим.")
        try:
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        except Exception:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return True
    return False


def cmd_shutdown(t, **_) -> bool:
    """
    ← ИСПРАВЛЕНО: расширены варианты триггеров выключения.
    """
    triggers = [
        "выключи компьютер", "завершить работу", "выключи пк",
        "выключай компьютер", "отключи компьютер", "выключай пк",
    ]
    if any(w in t for w in triggers):
        speak("Выключаю компьютер.")
        os.system("shutdown /s /t 5")
        return True
    return False


def cmd_restart(t, **_) -> bool:
    """
    ← ИСПРАВЛЕНО: расширены варианты триггеров перезагрузки.
    """
    triggers = [
        "перезагрузи", "перезапусти", "перезагрузка",
        "перезагрузи компьютер", "рестарт", "перезапуск",
    ]
    if any(w in t for w in triggers):
        speak("Перезагружаю компьютер.")
        os.system("shutdown /r /t 5")
        return True
    return False


def cmd_work_mode(t, **_) -> bool:
    if "режим работы" in t or "рабочий режим" in t:
        speak("Режим работы активирован. Открываю Word, PowerPoint и Publisher.")
        for lnk in ["word_lnk", "ppt_lnk", "pub_lnk"]:
            try:
                os.startfile(PATHS[lnk])
                time.sleep(1)  # небольшая задержка между запусками
            except Exception as e:
                log(f"work_mode open {lnk} error: {e}", "error")
        return True
    return False


def cmd_relax_mode(t, **_) -> bool:
    if "режим отдыха" in t or "режим релакса" in t or "отдыхай" in t:
        speak("Режим отдыха запущен. Приятного просмотра.")
        webbrowser.open(RELAX_VIDEO)
        return True
    return False


def cmd_game_mode(t, **_) -> bool:
    if "режим игры" in t or "игровой режим" in t or "режим игр" in t:
        speak("Игровой режим. Запускаю Steam и Discord.")
        try:
            os.startfile(PATHS["steam"])
        except Exception as e:
            log(f"game_mode steam error: {e}", "error")
        try:
            os.startfile(PATHS["discord"])
        except Exception as e:
            log(f"game_mode discord error: {e}", "error")
        return True
    return False


def cmd_open_app(t, **_) -> bool:
    if not any(x in t for x in ["открой", "запусти", "запустить", "включи", "открыть"]):
        return False

    for keyword, (name, cmd, _proc) in APPS.items():
        if keyword in t:
            speak(f"Открываю {name}.")
            launch(cmd)
            return True

    for keyword, (name, path, _proc) in ADOBE_APPS.items():
        if keyword in t:
            if os.path.exists(path):
                speak(f"Запускаю {name}.")
                subprocess.Popen(f'"{path}"', shell=True)
            else:
                speak(f"{name} не найден на диске.")
            return True

    return False


def cmd_close_app(t, **_) -> bool:
    if not any(x in t for x in ["закрой", "закрыть", "заверши", "убей"]):
        return False

    for keyword, (name, _cmd, proc) in APPS.items():
        if keyword in t:
            killed = False
            for p in psutil.process_iter(["name"]):
                try:
                    if p.info["name"] and p.info["name"].lower() == proc.lower():
                        p.kill()
                        killed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            speak(f"{'Закрыл' if killed else 'Не нашёл'} {name}.")
            return True
    return False


def cmd_hide_windows(t, **_) -> bool:
    """
    ← ИСПРАВЛЕНО: добавлены варианты без мягкого знака (речевой движок
    часто возвращает "все" вместо "всё").
    """
    triggers = [
        "скрой всё", "скрой все",
        "сверни всё", "сверни все",
        "покажи рабочий стол", "рабочий стол",
        "скрой окна", "убери окна",
    ]
    if any(x in t for x in triggers):
        minimize_all_windows()
        speak("Сэр, рабочий стол открыт. Я остаюсь на связи.")
        return True
    return False


def cmd_screenshot(t, **_) -> bool:
    if "скриншот" in t or "сделай снимок" in t or "снимок экрана" in t:
        path = take_screenshot()
        speak("Скриншот сохранён в папке Изображения.")
        log(f"Screenshot saved: {path}")
        return True
    return False


def cmd_note(t, **_) -> bool:
    if "запиши" in t:
        note = t
        for phrase in ["запиши заметку", "запиши заметки", "запиши"]:
            note = note.replace(phrase, "")
        note = note.strip()
        if note:
            save_note(note)
            speak("Заметка сохранена.")
        else:
            speak("Сэр, что именно записать?")
        return True
    return False


def cmd_brightness(t, **_) -> bool:
    if "яркость" in t:
        level = extract_number(t, default=50)
        try:
            sbc.set_brightness(level)
            speak(f"Яркость установлена на {level} процентов.")
        except Exception as e:
            speak("Не удалось изменить яркость.")
            log(f"brightness error: {e}", "error")
        return True
    return False


def cmd_volume(t, **_) -> bool:
    # Сначала проверяем точные команды без числа
    if "тише" in t:
        speak("Убавляю громкость.")
        pyautogui.hotkey("volumedown")
        return True
    if "громче" in t:
        speak("Прибавляю громкость.")
        pyautogui.hotkey("volumeup")
        return True
    if "без звука" in t or "выключи звук" in t or "отключи звук" in t:
        speak("Отключаю звук.")
        pyautogui.hotkey("volumemute")
        return True
    # Установка точного уровня
    if "громкость" in t:
        level = extract_number(t, default=50)
        set_volume(level)
        speak(f"Громкость установлена на {level} процентов.")
        return True
    return False


def cmd_status(t, **_) -> bool:
    triggers = ["статус", "нагрузка", "состояние системы", "как система", "загрузка"]
    if any(x in t for x in triggers):
        status = get_system_status()
        speak(status)
        return True
    return False


def cmd_time(t, **_) -> bool:
    triggers = ["который час", "время", "дата", "какое время", "сколько времени"]
    if any(x in t for x in triggers):
        now = datetime.now()
        speak(f"Сейчас {now:%H} часов {now:%M} минут, {now:%d}.{now:%m}.{now:%Y}.")
        return True
    return False


def cmd_search(t, client, model_id, **_) -> bool:
    triggers = [
        "найди информацию", "найди в гугле", "найди в интернете",
        "поищи", "найди", "загугли",
    ]
    match = next((x for x in triggers if x in t), None)
    if not match:
        return False

    query = t.replace(match, "").strip()
    if not query:
        speak("Сэр, что именно найти?")
        return True

    if client and model_id:
        answer = ask_gemini(client, model_id, f"Кратко объясни: {query}")
        if answer:
            speak(f"Вот что я нашёл: {answer[:300]}")

    webbrowser.open(f"https://www.google.com/search?q={query}")
    return True


def cmd_open_site(t, **_) -> bool:
    sites = {
        "ютуб"    : "https://youtube.com",
        "ватсап"  : "https://web.whatsapp.com",
        "гитхаб"  : "https://github.com",
        "почту"   : "https://mail.google.com",
        "гугл"    : "https://google.com",
    }
    open_triggers = ["открой", "зайди", "перейди", "открыть"]
    if not any(x in t for x in open_triggers):
        return False

    for word, url in sites.items():
        if word in t:
            speak(f"Открываю {word}.")
            webbrowser.open(url)
            return True
    return False


def cmd_gemini_chat(t, client, model_id, **_) -> bool:
    """Fallback — отправляем запрос в Gemini если ни одна команда не сработала."""
    if not client or not model_id:
        speak("Нет подключения к ИИ, сэр.")
        return True
    answer = ask_gemini(client, model_id, t)
    if answer:
        speak(answer[:400])
    else:
        speak("Сэр, не смог получить ответ.")
    return True


# ─────────────────────────────────────────────
#  СПИСОК ОБРАБОТЧИКОВ (порядок важен!)
# ─────────────────────────────────────────────

HANDLERS = [
    cmd_exit,
    cmd_sleep_pc,
    cmd_shutdown,
    cmd_restart,
    cmd_work_mode,
    cmd_relax_mode,
    cmd_game_mode,
    cmd_open_site,      # до cmd_open_app, чтобы "открой ютуб" не ушёл в APPS
    cmd_open_app,
    cmd_close_app,
    cmd_hide_windows,
    cmd_screenshot,
    cmd_note,
    cmd_brightness,
    cmd_volume,
    cmd_status,
    cmd_time,
    cmd_search,
    cmd_gemini_chat,    # всегда последний — fallback
]

# ─────────────────────────────────────────────
#  ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ КОМАНДЫ
# ─────────────────────────────────────────────

def process_task(client, model_id: str, task: str):
    if not task:
        return

    task_lower = task.lower().strip()
    log(f"COMMAND: {task_lower}")
    update_avatar("working")

    for handler in HANDLERS:
        try:
            if handler(t=task_lower, client=client, model_id=model_id):
                break
        except Exception as e:
            log(f"Handler {handler.__name__} error: {e}", "error")
            speak("Произошла ошибка при выполнении команды.")
            break

    update_avatar("idle")

# ─────────────────────────────────────────────
#  РАСПОЗНАВАНИЕ РЕЧИ
# ─────────────────────────────────────────────

_recognizer = sr.Recognizer()
_recognizer.pause_threshold        = 0.5
_recognizer.dynamic_energy_threshold = True

def listen() -> str | None:
    with sr.Microphone() as source:
        try:
            audio = _recognizer.listen(source, timeout=None, phrase_time_limit=7)
            return _recognizer.recognize_google(audio, language="ru-RU").lower()
        except sr.UnknownValueError:
            return None   # не распознал — тихо пропускаем
        except sr.RequestError as e:
            log(f"Speech recognition error: {e}", "error")
            speak("Проблема со связью при распознавании речи.")
            return None

# ─────────────────────────────────────────────
#  ТОЧКА ВХОДА
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Инициализация Gemini
    client, MODEL_ID = None, None
    try:
        client   = genai.Client(api_key=API_KEY)
        models   = list(client.models.list())
        flash    = next((m.name for m in models if "flash" in m.name), None)
        MODEL_ID = flash.split("/")[-1] if flash else None
        log(f"Gemini model: {MODEL_ID}")
        print(f"✅ Gemini подключён: {MODEL_ID}")
    except Exception as e:
        log(f"Gemini init error: {e}", "error")
        print(f"⚠️  Gemini недоступен: {e}")

    # Запуск аватара в отдельном потоке
    threading.Thread(target=start_avatar, daemon=True).start()

    speak("Yes sir. Все системы на связи. Жду вашей команды.")

    # Главный цикл
    while True:
        try:
            text = listen()
            if text:
                log(f"HEARD: {text}")
                print(f"🎤 Слышу: {text}")
                if WAKE_WORD in text:
                    update_avatar("listening")
                    command = text.replace(WAKE_WORD, "").strip()
                    if command:
                        process_task(client, MODEL_ID, command)
                    else:
                        speak("Слушаю, сэр.")
        except KeyboardInterrupt:
            speak("До свидания, сэр.")
            break
        except Exception as e:
            log(f"Main loop error: {e}", "error")

        time.sleep(0.01)