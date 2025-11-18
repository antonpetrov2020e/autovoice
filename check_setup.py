#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации Voice Memo Watcher
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def check_env_file():
    """Проверка наличия .env файла"""
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден")
        print("💡 Создайте его на основе .env.example:")
        print("   cp .env.example .env")
        return False
    print("✅ Файл .env найден")
    return True

def check_api_key():
    """Проверка API ключа Groq"""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("❌ GROQ_API_KEY не задан")
        print("💡 Добавьте ваш API ключ в .env файл")
        print("   Получить ключ БЕСПЛАТНО: https://console.groq.com/keys")
        return False

    if api_key == "your_api_key_here":
        print("❌ GROQ_API_KEY не настроен (используется значение по умолчанию)")
        print("💡 Замените 'your_api_key_here' на реальный API ключ")
        return False

    print(f"✅ GROQ_API_KEY задан ({api_key[:10]}...)")
    return True

def check_voice_memos_path():
    """Проверка папки Voice Memos"""
    path = os.getenv('VOICE_MEMOS_PATH')
    if not path:
        print("❌ VOICE_MEMOS_PATH не задан")
        return False

    expanded_path = os.path.expanduser(path)
    print(f"📂 VOICE_MEMOS_PATH: {expanded_path}")

    if not os.path.exists(expanded_path):
        print("❌ Папка не найдена")
        print("💡 Проверьте путь в .env файле")
        print("💡 Стандартный путь: ~/Library/Application Support/com.apple.voicememos/Recordings")

        # Попытка найти записи
        print("\n🔍 Поиск возможных локаций Voice Memos...")
        possible_paths = [
            "~/Library/Application Support/com.apple.voicememos/Recordings",
            "~/Library/Application Support/com.apple.VoiceMemos/Recordings",
            "~/Library/Group Containers/group.com.apple.VoiceMemos/Recordings"
        ]

        for possible_path in possible_paths:
            exp_path = os.path.expanduser(possible_path)
            if os.path.exists(exp_path):
                print(f"✅ Найдено: {exp_path}")

                # Проверяем наличие файлов
                audio_files = list(Path(exp_path).glob("*.m4a"))
                if audio_files:
                    print(f"   📁 Файлов: {len(audio_files)}")
                    print(f"💡 Используйте этот путь в .env файле")

        return False

    # Проверяем содержимое папки
    path_obj = Path(expanded_path)
    audio_files = list(path_obj.glob("*.m4a"))

    print(f"✅ Папка найдена")
    print(f"📁 Найдено аудио файлов: {len(audio_files)}")

    if audio_files:
        # Показываем последние 3 файла
        sorted_files = sorted(audio_files, key=lambda x: x.stat().st_ctime, reverse=True)
        print("\n📝 Последние записи:")
        for i, file in enumerate(sorted_files[:3], 1):
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"   {i}. {file.name} ({size_mb:.2f} MB)")

    return True

def check_obsidian_path():
    """Проверка папки Obsidian"""
    path = os.getenv('OBSIDIAN_VAULT_PATH')
    if not path:
        print("❌ OBSIDIAN_VAULT_PATH не задан")
        return False

    expanded_path = os.path.expanduser(path)
    print(f"📓 OBSIDIAN_VAULT_PATH: {expanded_path}")

    if not os.path.exists(expanded_path):
        print("⚠️  Папка не существует (будет создана автоматически)")

        # Проверяем, можем ли мы создать
        parent = Path(expanded_path).parent
        if not parent.exists():
            print(f"❌ Родительская папка не существует: {parent}")
            return False

        print("✅ Родительская папка существует, новая папка будет создана")
    else:
        print("✅ Папка найдена")

        # Проверяем права на запись
        if not os.access(expanded_path, os.W_OK):
            print("❌ Нет прав на запись в эту папку")
            return False
        print("✅ Права на запись есть")

    return True

def check_dependencies():
    """Проверка установленных зависимостей"""
    print("\n📦 Проверка зависимостей...")

    required_modules = {
        'openai': 'openai',
        'watchdog': 'watchdog',
        'dotenv': 'python-dotenv'
    }

    all_ok = True
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} не установлен")
            all_ok = False

    if not all_ok:
        print("\n💡 Установите зависимости:")
        print("   pip install -r requirements.txt")

    return all_ok

def main():
    print("=" * 60)
    print("🔍 Проверка конфигурации Voice Memo Watcher")
    print("=" * 60)
    print()

    # Проверяем .env
    if not check_env_file():
        sys.exit(1)

    # Загружаем переменные
    load_dotenv()

    print("\n" + "=" * 60)
    print("🔑 Проверка API ключа")
    print("=" * 60)
    api_ok = check_api_key()

    print("\n" + "=" * 60)
    print("📂 Проверка папки Voice Memos")
    print("=" * 60)
    voice_ok = check_voice_memos_path()

    print("\n" + "=" * 60)
    print("📓 Проверка папки Obsidian")
    print("=" * 60)
    obsidian_ok = check_obsidian_path()

    print("\n" + "=" * 60)
    deps_ok = check_dependencies()

    print("\n" + "=" * 60)
    print("📊 Итого")
    print("=" * 60)

    checks = {
        'API ключ': api_ok,
        'Папка Voice Memos': voice_ok,
        'Папка Obsidian': obsidian_ok,
        'Зависимости': deps_ok
    }

    for name, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {name}")

    all_ok = all(checks.values())

    print("\n" + "=" * 60)
    if all_ok:
        print("🎉 Все проверки пройдены!")
        print("💡 Запустите скрипт:")
        print("   python voice_memo_watcher.py")
    else:
        print("⚠️  Некоторые проверки не прошли")
        print("💡 Исправьте ошибки выше и запустите снова:")
        print("   python check_setup.py")
    print("=" * 60)

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
