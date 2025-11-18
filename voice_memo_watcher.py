#!/usr/bin/env python3
"""
Voice Memo Watcher - автоматическая транскрипция голосовых заметок из Voice Memos в Obsidian
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Set, Dict
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from openai import OpenAI
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_memo_watcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProcessedFilesTracker:
    """Отслеживание обработанных файлов"""

    def __init__(self, tracker_file: str = "processed_files.json"):
        self.tracker_file = tracker_file
        self.processed_files: Set[str] = self._load()

    def _load(self) -> Set[str]:
        """Загрузить список обработанных файлов"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('files', []))
            except Exception as e:
                logger.error(f"Ошибка загрузки {self.tracker_file}: {e}")
        return set()

    def _save(self):
        """Сохранить список обработанных файлов"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump({'files': list(self.processed_files)}, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения {self.tracker_file}: {e}")

    def is_processed(self, file_path: str) -> bool:
        """Проверить, был ли файл обработан"""
        return file_path in self.processed_files

    def mark_processed(self, file_path: str):
        """Отметить файл как обработанный"""
        self.processed_files.add(file_path)
        self._save()


class VoiceMemoTranscriber:
    """Класс для транскрипции голосовых заметок"""

    def __init__(self, api_key: str, language: str = "ru"):
        self.client = OpenAI(api_key=api_key)
        self.language = language

    def transcribe(self, audio_file_path: str) -> str:
        """Транскрибировать аудио файл"""
        try:
            logger.info(f"Начинаем транскрипцию: {audio_file_path}")

            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=self.language,
                    response_format="text"
                )

            logger.info(f"Транскрипция завершена: {len(transcript)} символов")
            return transcript

        except Exception as e:
            logger.error(f"Ошибка транскрипции {audio_file_path}: {e}")
            raise


class ObsidianWriter:
    """Класс для сохранения заметок в Obsidian"""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def save_transcription(self, audio_file_path: str, transcription: str) -> str:
        """Сохранить транскрипцию в Obsidian"""
        # Получаем информацию о файле
        audio_path = Path(audio_file_path)
        file_stat = audio_path.stat()
        created_time = datetime.fromtimestamp(file_stat.st_ctime)

        # Формируем имя файла в формате: YYYY-MM-DD - Voice Memo.md
        note_name = created_time.strftime("%Y-%m-%d - Voice Memo")
        note_path = self.vault_path / f"{note_name}.md"

        # Если файл уже существует, добавляем счетчик
        counter = 1
        while note_path.exists():
            note_name = created_time.strftime(f"%Y-%m-%d - Voice Memo {counter}")
            note_path = self.vault_path / f"{note_name}.md"
            counter += 1

        # Формируем содержимое заметки
        content = f"""# {note_name}

**Дата записи:** {created_time.strftime("%d.%m.%Y %H:%M")}
**Источник:** {audio_path.name}

---

{transcription}

---

*Автоматически транскрибировано: {datetime.now().strftime("%d.%m.%Y %H:%M")}*
"""

        # Сохраняем файл
        try:
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Заметка сохранена: {note_path}")
            return str(note_path)
        except Exception as e:
            logger.error(f"Ошибка сохранения в Obsidian: {e}")
            raise


class VoiceMemoHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы"""

    def __init__(self, transcriber: VoiceMemoTranscriber,
                 obsidian_writer: ObsidianWriter,
                 tracker: ProcessedFilesTracker):
        self.transcriber = transcriber
        self.obsidian_writer = obsidian_writer
        self.tracker = tracker
        self.processing = set()

    def on_created(self, event):
        """Обработка создания нового файла"""
        if event.is_directory:
            return

        file_path = event.src_path

        # Проверяем расширение файла (Voice Memos сохраняет в .m4a)
        if not file_path.lower().endswith(('.m4a', '.mp3', '.wav', '.m4v')):
            return

        # Проверяем, не обрабатывается ли уже файл
        if file_path in self.processing:
            return

        # Проверяем, не был ли файл уже обработан
        if self.tracker.is_processed(file_path):
            logger.info(f"Файл уже был обработан: {file_path}")
            return

        self.process_file(file_path)

    def process_file(self, file_path: str):
        """Обработать аудио файл"""
        self.processing.add(file_path)

        try:
            # Ждем, пока файл полностью запишется
            logger.info(f"Обнаружен новый файл: {file_path}")
            time.sleep(2)

            # Проверяем, что файл существует и доступен
            if not os.path.exists(file_path):
                logger.warning(f"Файл не найден: {file_path}")
                return

            # Транскрибируем
            logger.info("Начинаем транскрипцию...")
            transcription = self.transcriber.transcribe(file_path)

            # Сохраняем в Obsidian
            logger.info("Сохраняем в Obsidian...")
            note_path = self.obsidian_writer.save_transcription(file_path, transcription)

            # Отмечаем как обработанный
            self.tracker.mark_processed(file_path)

            logger.info(f"✅ Успешно обработано: {file_path}")
            logger.info(f"📝 Заметка создана: {note_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки {file_path}: {e}")

        finally:
            self.processing.discard(file_path)


def process_existing_files(voice_memos_path: str, handler: VoiceMemoHandler):
    """Обработать существующие файлы при запуске"""
    logger.info("Проверяем существующие файлы...")

    try:
        path = Path(voice_memos_path)
        if not path.exists():
            logger.warning(f"Папка не найдена: {voice_memos_path}")
            return

        # Ищем все аудио файлы
        audio_extensions = {'.m4a', '.mp3', '.wav', '.m4v'}
        audio_files = []

        for ext in audio_extensions:
            audio_files.extend(path.glob(f"*{ext}"))

        # Сортируем по времени создания
        audio_files.sort(key=lambda x: x.stat().st_ctime)

        logger.info(f"Найдено файлов: {len(audio_files)}")

        # Обрабатываем только необработанные файлы
        for audio_file in audio_files:
            if not handler.tracker.is_processed(str(audio_file)):
                logger.info(f"Обрабатываем существующий файл: {audio_file.name}")
                handler.process_file(str(audio_file))

    except Exception as e:
        logger.error(f"Ошибка при обработке существующих файлов: {e}")


def main():
    """Основная функция"""
    # Загружаем переменные окружения
    load_dotenv()

    # Получаем настройки
    api_key = os.getenv('OPENAI_API_KEY')
    voice_memos_path = os.getenv('VOICE_MEMOS_PATH')
    obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')
    language = os.getenv('TRANSCRIPTION_LANGUAGE', 'ru')

    # Проверяем наличие необходимых настроек
    if not api_key:
        logger.error("❌ OPENAI_API_KEY не задан в .env файле")
        sys.exit(1)

    if not voice_memos_path:
        logger.error("❌ VOICE_MEMOS_PATH не задан в .env файле")
        sys.exit(1)

    if not obsidian_vault_path:
        logger.error("❌ OBSIDIAN_VAULT_PATH не задан в .env файле")
        sys.exit(1)

    # Расширяем путь (для поддержки ~)
    voice_memos_path = os.path.expanduser(voice_memos_path)
    obsidian_vault_path = os.path.expanduser(obsidian_vault_path)

    # Проверяем существование папки Voice Memos
    if not os.path.exists(voice_memos_path):
        logger.error(f"❌ Папка Voice Memos не найдена: {voice_memos_path}")
        logger.info("💡 Проверьте путь в .env файле")
        sys.exit(1)

    logger.info("🎙️ Voice Memo Watcher запущен")
    logger.info(f"📂 Отслеживаем: {voice_memos_path}")
    logger.info(f"📝 Сохраняем в: {obsidian_vault_path}")
    logger.info(f"🌍 Язык: {language}")

    # Создаем объекты
    tracker = ProcessedFilesTracker()
    transcriber = VoiceMemoTranscriber(api_key, language)
    obsidian_writer = ObsidianWriter(obsidian_vault_path)
    event_handler = VoiceMemoHandler(transcriber, obsidian_writer, tracker)

    # Обрабатываем существующие файлы
    process_existing_files(voice_memos_path, event_handler)

    # Запускаем мониторинг
    observer = Observer()
    observer.schedule(event_handler, voice_memos_path, recursive=False)
    observer.start()

    logger.info("👀 Мониторинг активен. Нажмите Ctrl+C для остановки.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка мониторинга...")
        observer.stop()

    observer.join()
    logger.info("✅ Завершено")


if __name__ == "__main__":
    main()
