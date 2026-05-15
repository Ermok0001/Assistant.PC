import os
import subprocess
import time
import threading
import sys
import re
import queue
import webbrowser
import tkinter as tk
import psutil
import pyautogui
import pygetwindow as gw
import ctypes
import logging
from datetime import datetime
from PIL import Image, ImageTk
from threading import Lock

try:
    import speech_recognition as sr
    import pyttsx3
    import screen_brightness_control as sbc
    from google import genai
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError as e:
    logging.error(f"Ошибка импорта: {e}")
    sys.exit(1)

# === КОНФИГУРАЦИЯ ===
try:
    from config import (
        API_KEY, WAKE_WORD, RELAX_VIDEO_URL, OFFICE_SHORTCUTS,
        STEAM_LNK, DISCORD_LNK, APPS_DATA, ADOBE_DATA, TTS_RATE, LOG_LEVEL, LOG_FILE
    )
except ImportError:
    logging.error("Не найден файл config.py!")
    sys.exit(1)

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === ИНИЦИАЛИЗАЦИЯ ===
engine = pyttsx3.init()
engine.setProperty('rate', TTS_RATE)
speech_queue = queue.Queue()
avatar_lock = Lock()
root, label = None, None

def tts_worker():
    """Рабочий поток для TTS"""
    while True:
        text = speech_queue.get()
        if text is None:
            break
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"Ошибка TTS: {e}")
        finally:
            speech_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

def speak(text):
    """Говорит текст через TTS"""
    print(f"🤖 Пика: {text}")
    logger.info(f"Речь: {text}")
    speech_queue.put(text)

def resource_path(relative_path):
    """Получает путь ресурса для PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def update_avatar_state(state):
    """Обновляет состояние аватара (idle/listening/working)"""
    global root, label
    if not root or not label:
        return
    
    with avatar_lock:
        try:
            if state == "idle":
                root.config(bg="black")
                label.config(bg="black")
                root.attributes("-transparentcolor", "black")
            elif state == "listening":
                root.config(bg="#00FF00")
                label.config(bg="#00FF00")
                root.attributes("-transparentcolor", "")
            elif state == "working":
                root.config(bg="#8A2BE2")
                label.config(bg="#8A2BE2")
                root.attributes("-transparentcolor", "")
            root.update()
        except tk.TclError as e:
            logger.warning(f"Ошибка обновления аватара: {e}")

def start_avatar():
    """Запускает окно аватара в основном потоке Tkinter"""
    global root, label
    try:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", "black")
        root.config(bg="black")
        
        try:
            img = Image.open(resource_path("pike.png")).resize((150, 150))
            photo = ImageTk.PhotoImage(img)
            label = tk.Label(root, image=photo, bg="black", bd=0)
            label.image = photo
            label.pack()
        except FileNotFoundError:
            logger.warning("Файл pike.png не найден, используется текстовый символ")
            label = tk.Label(root, text="⚡", font=("Arial", 40), bg="black", fg="yellow")
            label.pack()
        
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"150x150+{sw-160}+{sh-200}")
        root.mainloop()
    except Exception as e:
        logger.error(f"Ошибка запуска аватара: {e}")

def get_system_status():
    """Возвращает статус системы"""
    try:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return f"Процессор: {cpu}%. Память: {ram}%."
    except Exception as e:
        logger.error(f"Ошибка получения статуса системы: {e}")
        return "Ошибка получения данных системы"

def set_volume_local(level):
    """Устанавливает громкость звука"""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        logger.info(f"Громкость установлена на {level}%")
    except Exception as e:
        logger.error(f"Ошибка установки громкости: {e}")

def handle_exit(client):
    """Обработка выхода из приложения"""
    speak("Слушаюсь, сэр. Выключаюсь.")
    time.sleep(1)
    if client:
        try:
            client.close()
        except Exception:
            pass
    logger.info("Приложение завершено")
    sys.exit(0)

def handle_sleep_mode():
    """Переводит ПК в спящий режим"""
    speak("Перевожу компьютер в спящий режим.")
    try:
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
    except OSError:
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        except Exception as e:
            logger.error(f"Ошибка спящего режима: {e}")
            speak("Сэр, не смог перевести в спящий режим")

def handle_google_search(client, model_id, task):
    """Обработка поиска в Google"""
    query = task.lower()
    query = query.replace("найди информацию об этом в гугле", "").replace("найди в гугле", "").replace("найди информацию", "").strip()
    
    if not query:
        speak("Сэр, что именно мне найти?")
        return
    
    if not client or not model_id:
        speak("Сэр, нет подключения к Google Gemini")
        return
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=f"Кратко объясни что такое {query}"
        )
        speak(f"Сэр, вот что я нашел: {response.text}")
        webbrowser.open(f"https://www.google.com/search?q={query}")
    except Exception as e:
        logger.error(f"Ошибка поиска Google: {e}")
        speak("Сэр, ошибка при поиске информации")

def handle_work_mode():
    """Открывает приложения для работы"""
    speak("Режим работы активирован. Открываю Word, PowerPoint и Publisher.")
    shortcuts = [OFFICE_SHORTCUTS.get("word"), OFFICE_SHORTCUTS.get("powerpoint"), OFFICE_SHORTCUTS.get("publisher")]
    
    for shortcut in shortcuts:
        if shortcut and os.path.exists(shortcut):
            try:
                os.startfile(shortcut)
            except OSError as e:
                logger.error(f"Ошибка открытия {shortcut}: {e}")
        else:
            logger.warning(f"Ярлык не найден: {shortcut}")
    
    if not any(os.path.exists(s) for s in shortcuts if s):
        speak("Сэр, проверьте пути к Office 2016.")

def handle_relax_mode():
    """Открывает видео для отдыха"""
    speak("Режим отдыха запущен. Приятного просмотра.")
    try:
        webbrowser.open(RELAX_VIDEO_URL)
    except Exception as e:
        logger.error(f"Ошибка открытия видео: {e}")

def handle_game_mode():
    """Открывает приложения для игр"""
    speak("Игровой режим. Запускаю Стим и Дискорд.")
    try:
        if os.path.exists(STEAM_LNK):
            os.startfile(STEAM_LNK)
        if os.path.exists(DISCORD_LNK):
            os.startfile(DISCORD_LNK)
    except OSError as e:
        logger.error(f"Ошибка запуска игр: {e}")

def handle_app_launch(task):
    """Запускает приложение по названию"""
    opened = False
    
    for app_key, app_data in APPS_DATA.items():
        if app_key in task.lower():
            try:
                if "\\" in app_data[1]:
                    os.startfile(app_data[1])
                else:
                    subprocess.Popen(app_data[1], shell=True)
                speak(f"Открываю {app_data[0]} локально.")
                opened = True
                logger.info(f"Запущено приложение: {app_data[0]}")
            except OSError as e:
                logger.error(f"Ошибка запуска {app_data[0]}: {e}")
            break
    
    if not opened:
        for adobe_key, adobe_data in ADOBE_DATA.items():
            if adobe_key in task.lower():
                if os.path.exists(adobe_data[1]):
                    try:
                        subprocess.Popen(f'"{adobe_data[1]}"', shell=True)
                        speak(f"Запускаю {adobe_data[0]}.")
                        opened = True
                        logger.info(f"Запущено Adobe приложение: {adobe_data[0]}")
                    except OSError as e:
                        logger.error(f"Ошибка запуска {adobe_data[0]}: {e}")
                else:
                    logger.warning(f"Adobe приложение не найдено: {adobe_data[1]}")
                break
    
    if opened:
        return True
    return False

def handle_hide_all():
    """Скрывает все окна"""
    try:
        pyautogui.hotkey('win', 'd')
        for window in gw.getAllWindows():
            if window.title and window.visible and "PikaAvatar" not in window.title:
                try:
                    window.minimize()
                except Exception as e:
                    logger.warning(f"Ошибка минимизации окна {window.title}: {e}")
        speak("Сэр, я всё скрыл. Я остаюсь на связи.")
    except Exception as e:
        logger.error(f"Ошибка скрытия окон: {e}")

def handle_screenshot():
    """Создаёт скриншот"""
    try:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(os.path.expanduser("~"), "Pictures", f"Screenshot_{now}.png")
        pyautogui.screenshot(path)
        speak("Скриншот сохранен.")
        logger.info(f"Скриншот сохранён: {path}")
    except Exception as e:
        logger.error(f"Ошибка создания скриншота: {e}")

def handle_note(task):
    """Сохраняет заметку"""
    note = task.lower().replace("запиши заметку", "").replace("запиши", "").strip()
    if not note:
        speak("Сэр, о чём мне записать заметку?")
        return
    
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop", "pika_notes.txt")
        with open(desktop, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M')}] {note}\n")
        speak("Заметка сохранена.")
        logger.info(f"Заметка сохранена: {note}")
    except IOError as e:
        logger.error(f"Ошибка сохранения заметки: {e}")
        speak("Сэр, ошибка при сохранении заметки")

def handle_brightness(task):
    """Управляет яркостью дисплея"""
    try:
        numbers = re.findall(r'\d+', task)
        brightness = int(numbers[0]) if numbers else 50
        
        if 0 <= brightness <= 100:
            sbc.set_brightness(brightness)
            speak(f"Яркость: {brightness}%.")
            logger.info(f"Яркость установлена на {brightness}%")
        else:
            speak("Сэр, яркость должна быть от 0 до 100 процентов")
    except Exception as e:
        logger.error(f"Ошибка управления яркостью: {e}")
        speak("Сэр, ошибка при управлении яркостью")

def process_task(client, model_id, task):
    """Основной обработчик команд"""
    if not task or not isinstance(task, str):
        return
    
    task_lower = task.lower().strip()
    update_avatar_state("working")
    
    try:
        # Выход
        if any(word == task_lower or word in task_lower for word in ["стоп", "выключись", "отключись"]):
            handle_exit(client)
            return
        
        # Спящий режим
        if "спать" in task_lower:
            handle_sleep_mode()
            return
        
        # Поиск информации
        if any(x in task_lower for x in ["найди информацию", "найди в гугле"]):
            handle_google_search(client, model_id, task)
            update_avatar_state("idle")
            return
        
        # Режим работы
        if "режим работы" in task_lower:
            handle_work_mode()
            update_avatar_state("idle")
            return
        
        # Режим отдыха
        if "режим отдыха" in task_lower:
            handle_relax_mode()
            update_avatar_state("idle")
            return
        
        # Режим игры
        if "режим игры" in task_lower:
            handle_game_mode()
            update_avatar_state("idle")
            return
        
        # Открытие приложений
        if any(x in task_lower for x in ["открой", "запусти"]):
            if handle_app_launch(task):
                update_avatar_state("idle")
                return
        
        # Скрытие всех окон
        if any(x in task_lower for x in ["скрой всё", "сверни всё", "покажи рабочий стол"]):
            handle_hide_all()
            update_avatar_state("idle")
            return
        
        # Скриншот
        if "скриншот" in task_lower:
            handle_screenshot()
            update_avatar_state("idle")
            return
        
        # Сохранение заметки
        if "запиши" in task_lower:
            handle_note(task)
            update_avatar_state("idle")
            return
        
        # Управление яркостью
        if "яркость" in task_lower:
            handle_brightness(task)
            update_avatar_state("idle")
            return
        
        logger.warning(f"Неизвестная команда: {task}")
    
    except Exception as e:
        logger.error(f"Ошибка обработки команды '{task}': {e}")
        speak("Сэр, произошла ошибка при обработке команды")
    
    finally:
        update_avatar_state("idle")

def listen():
    """Слушает микрофон и возвращает распознанный текст"""
    try:
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        recognizer.pause_threshold = 0.5
        
        with mic as source:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=5)
            return recognizer.recognize_google(audio, language="ru-RU").lower()
    except sr.UnknownValueError:
        logger.debug("Речь не распознана")
        return None
    except sr.RequestError as e:
        logger.error(f"Ошибка сервиса речи: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка микрофона: {e}")
        return None

def main():
    """Главная функция"""
    client = None
    model_id = None
    
    try:
        if not API_KEY:
            raise ValueError("API_KEY не установлен!")
        
        client = genai.Client(api_key=API_KEY)
        models_list = list(client.models.list())
        model_id = next(
            (m.name.split('/')[-1] for m in models_list if "flash" in m.name),
            None
        )
        
        if not model_id:
            logger.warning("Flash модель не найдена, используется базовая модель")
    except Exception as e:
        logger.error(f"Ошибка инициализации Gemini: {e}")
        client = None
    
    # Запуск аватара в отдельном потоке
    avatar_thread = threading.Thread(target=start_avatar, daemon=True)
    avatar_thread.start()
    
    speak("Yes, sir. Все системы на связи.")
    logger.info("Приложение запущено")
    
    try:
        while True:
            voice_input = listen()
            if voice_input and WAKE_WORD in voice_input:
                update_avatar_state("listening")
                command = voice_input.replace(WAKE_WORD, "").strip()
                if command:
                    process_task(client, model_id, command)
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Прерывание пользователем")
        handle_exit(client)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        handle_exit(client)

if __name__ == "__main__":
    main()
