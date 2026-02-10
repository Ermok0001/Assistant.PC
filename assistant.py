import os
import subprocess
import time
import speech_recognition as sr
import pyttsx3
from google import genai

# === ОБНОВЛЕННЫЙ КЛЮЧ ===
API_KEY = "AIzaSyDEnd0Wr-CGWNtlickQZFpEvmhrvJqeyNA"
WAKE_WORD = "альфа" 

# Настройка голоса
engine = pyttsx3.init()
def speak(text):
    print(f"🤖 Альфа: {text}")
    engine.say(text)
    engine.runAndWait()

def initialize_gemini():
    """Проверка ключа и выбор модели Gemini 3 Flash"""
    try:
        client = genai.Client(api_key=API_KEY)
        # Получаем список моделей для проверки ключа
        models_list = list(client.models.list())
        # Ищем Flash-модель
        selected = next((m.name for m in models_list if "flash" in m.name.lower()), models_list[0].name)
        model_id = selected.replace("models/", "")
        
        # Тестовый микро-запрос
        client.models.generate_content(model=model_id, contents="hi")
        print(f"✅ Ключ принят. Работаем на модели: {model_id}")
        return client, model_id
    except Exception as e:
        print(f"❌ Ошибка ключа или сети: {e}")
        return None, None

def execute_command(ai_response):
    """Безопасное выполнение через CMD"""
    try:
        cmd = ai_response.replace('```', '').replace('`', '').strip()
        if cmd.lower().startswith('cmd'): cmd = cmd[3:].strip()
        if not cmd: return

        # Защита от "серого экрана" (не даем закрыть проводник)
        critical = ["explorer.exe", "svchost.exe", "lsass.exe", "wininit.exe", "services.exe"]
        
        if "taskkill" in cmd.lower():
            if any(p in cmd.lower() for p in critical):
                speak("Это системный процесс. Я не могу его закрыть.")
                return
            
            print(f"🚀 Закрываю: {cmd}")
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                speak("Программа закрыта.")
            else:
                speak("Она уже закрыта.")
        else:
            print(f"🚀 Открываю: {cmd}")
            subprocess.Popen(cmd, shell=True)
            speak("Готово.")
            
    except Exception as e:
        print(f"❌ Ошибка исполнения: {e}")

def listen():
    """Слушаем микрофон"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(f"🎤 Жду обращения '{WAKE_WORD}'...")
        r.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = r.listen(source, timeout=10, phrase_time_limit=8)
            query = r.recognize_google(audio, language="ru-RU")
            print(f"👤 Ты: {query}")
            return query.lower()
        except:
            return None

# --- ЗАПУСК ---
client, MODEL_ID = initialize_gemini()

if __name__ == "__main__" and client:
    speak("Система Альфа активирована.")
    
    while True:
        voice_text = listen()
        
        # Реагируем только если услышали имя "Альфа"
        if voice_text and WAKE_WORD in voice_text:
            # Очищаем фразу от имени бота
            task = voice_text.replace(WAKE_WORD, "").strip()
            
            if not task:
                speak("Слушаю тебя.")
                continue
                
            if any(x in task for x in ["стоп", "выход", "выключись"]):
                speak("Завершаю работу.")
                break
            
            try:
                # Промпт для ИИ
                prompt = f"Выведи ТОЛЬКО команду CMD для Windows (без лишних слов): {task}"
                response = client.models.generate_content(model=MODEL_ID, contents=prompt)
                
                if response.text:
                    execute_command(response.text)
            except Exception as e:
                if "429" in str(e):
                    speak("Закончились лимиты. Подожди минуту.")
                else:
                    print(f"⚠️ Ошибка API: {e}")
                    
        time.sleep(0.2)
else:
    print("💥 Скрипт не запущен. Проверь API-ключ или работу GoodbyeDPI.")