#!/usr/bin/env python3
"""
Скрипт для ручной транскрипции одного файла
Полезно для тестирования или обработки отдельных файлов
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Импортируем классы из основного скрипта
from voice_memo_watcher import VoiceMemoTranscriber, ObsidianWriter


def main():
    if len(sys.argv) < 2:
        print("Использование: python transcribe_file.py <путь_к_аудио_файлу>")
        print("\nПример:")
        print('  python transcribe_file.py "/Users/user/recording.m4a"')
        sys.exit(1)

    audio_file = sys.argv[1]

    # Проверяем существование файла
    if not os.path.exists(audio_file):
        print(f"❌ Файл не найден: {audio_file}")
        sys.exit(1)

    # Загружаем конфигурацию
    load_dotenv()

    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('TRANSCRIPTION_MODEL', 'whisper-large-v3-turbo')
    obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')
    language = os.getenv('TRANSCRIPTION_LANGUAGE', 'ru')
    improve_text = os.getenv('IMPROVE_TEXT', 'true').lower() == 'true'

    if not api_key:
        print("❌ GROQ_API_KEY не задан в .env файле")
        sys.exit(1)

    if not obsidian_vault_path:
        print("❌ OBSIDIAN_VAULT_PATH не задан в .env файле")
        sys.exit(1)

    # Расширяем пути
    audio_file = os.path.expanduser(audio_file)
    obsidian_vault_path = os.path.expanduser(obsidian_vault_path)

    print(f"🎙️  Файл: {audio_file}")
    file_size = os.path.getsize(audio_file) / (1024 * 1024)
    print(f"📊 Размер: {file_size:.2f} MB")
    print(f"🤖 Модель: {model}")
    print(f"🌍 Язык: {language}")
    print(f"✨ Улучшение текста: {'включено' if improve_text else 'выключено'}")
    print()

    # Создаем объекты
    transcriber = VoiceMemoTranscriber(api_key, model, language, improve_text)
    obsidian_writer = ObsidianWriter(obsidian_vault_path)

    try:
        # Транскрибируем
        print("⏳ Транскрибируем...")
        transcription = transcriber.transcribe(audio_file)

        print(f"✅ Транскрипция завершена ({len(transcription)} символов)")
        print()
        print("=" * 60)
        print("ТЕКСТ:")
        print("=" * 60)
        print(transcription)
        print("=" * 60)
        print()

        # Сохраняем в Obsidian
        print("💾 Сохраняем в Obsidian...")
        note_path = obsidian_writer.save_transcription(audio_file, transcription)
        print(f"✅ Заметка сохранена: {note_path}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
