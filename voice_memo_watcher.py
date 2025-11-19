#!/usr/bin/env python3
"""
Voice Memo Watcher - автоматическая транскрипция голосовых заметок из Voice Memos в Obsidian
"""

import os
import sys
import json
import time
import base64
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, List
import logging
import tempfile

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from openai import OpenAI
from dotenv import load_dotenv
from pydub import AudioSegment

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
    """Класс для транскрипции голосовых заметок через Groq (Whisper Large v3)"""

    def __init__(self, groq_api_key: str, openrouter_client: OpenAI = None,
                 transcription_model: str = "whisper-large-v3-turbo",
                 text_model: str = "openai/gpt-4o-mini",
                 language: str = "ru", improve_text: bool = True):
        # Используем Groq только для транскрипции (Whisper)
        self.transcription_client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        # OpenRouter для улучшения текста и генерации заголовков
        self.text_client = openrouter_client
        self.transcription_model = transcription_model
        self.text_model = text_model
        self.language = language
        self.improve_text = improve_text
        # Путь к пользовательскому словарю
        self.dictionary_path = "custom_dictionary.txt"
        self.custom_dictionary = self._load_dictionary()
        # Максимальный размер файла для Groq (25 MB)
        self.max_file_size_mb = 20  # Оставляем запас

    def _encode_audio_to_base64(self, audio_file_path: str) -> str:
        """Конвертировать аудио файл в base64"""
        with open(audio_file_path, 'rb') as audio_file:
            return base64.b64encode(audio_file.read()).decode('utf-8')

    def _get_mime_type(self, file_path: str) -> str:
        """Определить MIME тип аудио файла"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.m4a': 'audio/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4v': 'audio/mp4',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }
        return mime_types.get(ext, 'audio/mp4')

    def _load_dictionary(self) -> str:
        """Загрузить пользовательский словарь"""
        try:
            if os.path.exists(self.dictionary_path):
                with open(self.dictionary_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        logger.info(f"Загружен словарь из {self.dictionary_path}")
                        return content
        except Exception as e:
            logger.error(f"Ошибка загрузки словаря: {e}")
        return ""

    def _save_to_dictionary(self, words: list):
        """Добавить слова в пользовательский словарь"""
        try:
            existing = set()
            if os.path.exists(self.dictionary_path):
                with open(self.dictionary_path, 'r', encoding='utf-8') as f:
                    existing = set(line.strip() for line in f if line.strip())

            new_words = [w for w in words if w and w not in existing]

            if new_words:
                with open(self.dictionary_path, 'a', encoding='utf-8') as f:
                    for word in new_words:
                        f.write(f"{word}\n")
                logger.info(f"Добавлено {len(new_words)} слов в словарь")
                # Обновляем загруженный словарь
                self.custom_dictionary = self._load_dictionary()
        except Exception as e:
            logger.error(f"Ошибка сохранения в словарь: {e}")

    def _split_audio(self, audio_file_path: str) -> List[str]:
        """Разделить большой аудио файл на части по 20 MB

        Returns:
            List[str]: Список путей к временным файлам с частями аудио
        """
        try:
            logger.info("Загружаем аудио файл для разделения...")
            audio = AudioSegment.from_file(audio_file_path)

            # Получаем размер файла
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)

            # Вычисляем длительность одного чанка в миллисекундах
            # Предполагаем линейную зависимость размера от длительности
            total_duration_ms = len(audio)
            chunk_duration_ms = int((self.max_file_size_mb / file_size_mb) * total_duration_ms)

            logger.info(f"Разделяем файл на части по ~{chunk_duration_ms/1000/60:.1f} минут...")

            # Создаем список временных файлов
            chunk_files = []
            temp_dir = tempfile.gettempdir()

            # Разделяем аудио на части
            for i, start_ms in enumerate(range(0, total_duration_ms, chunk_duration_ms)):
                end_ms = min(start_ms + chunk_duration_ms, total_duration_ms)
                chunk = audio[start_ms:end_ms]

                # Создаем временный файл для части
                chunk_file = os.path.join(temp_dir, f"chunk_{i}_{os.path.basename(audio_file_path)}")
                chunk.export(chunk_file, format="mp4")  # Экспортируем в m4a (mp4 audio)

                chunk_size_mb = os.path.getsize(chunk_file) / (1024 * 1024)
                logger.info(f"Создана часть {i+1}: {chunk_size_mb:.2f} MB ({(end_ms-start_ms)/1000/60:.1f} минут)")

                chunk_files.append(chunk_file)

            logger.info(f"Файл разделен на {len(chunk_files)} частей")
            return chunk_files

        except Exception as e:
            logger.error(f"Ошибка разделения аудио файла: {e}")
            raise

    def _transcribe_chunk(self, chunk_file_path: str) -> str:
        """Транскрибировать одну часть аудио файла"""
        try:
            with open(chunk_file_path, 'rb') as audio_file:
                transcript = self.transcription_client.audio.transcriptions.create(
                    model=self.transcription_model,
                    file=audio_file,
                    language=self.language,
                    response_format="text"
                )
            return transcript
        except Exception as e:
            logger.error(f"Ошибка транскрипции части {chunk_file_path}: {e}")
            raise

    def _generate_title(self, transcript: str) -> str:
        """Сгенерировать осмысленный заголовок для записи"""
        try:
            logger.info("Генерируем заголовок...")

            prompt = f"""На основе текста голосовой записи создай краткий заголовок.

ТЕКСТ:
{transcript[:1000]}

ПРАВИЛА:
1. Если в тексте упоминается конкретная дата (например, "15 ноября, суббота"), используй её как заголовок
2. Если даты нет, создай краткое описание темы (2-5 слов)
3. Заголовок должен быть информативным и помогать быстро понять о чем запись
4. Используй формат: "Дата" или "Краткое описание темы"
5. Не добавляй кавычки или лишние символы

ПРИМЕРЫ:
- "15 ноября, суббота"
- "Встреча с психологом"
- "Планы на неделю"
- "Разговор с Юлей о проекте"

Верни ТОЛЬКО заголовок без комментариев."""

            response = self.text_client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=100
            )

            title = response.choices[0].message.content.strip()
            # Убираем возможные кавычки
            title = title.strip('"\'«»')
            logger.info(f"Сгенерирован заголовок: {title}")

            return title

        except Exception as e:
            logger.error(f"Ошибка генерации заголовка: {e}")
            return "Голосовая заметка"

    def _improve_transcript(self, transcript: str) -> str:
        """Улучшить транскрипцию: исправить ошибки, разбить на абзацы"""
        try:
            logger.info("Улучшаем текст транскрипции...")

            # Формируем информацию о словаре
            dictionary_info = ""
            if self.custom_dictionary:
                dictionary_info = f"""

ПОЛЬЗОВАТЕЛЬСКИЙ СЛОВАРЬ (используй эти правильные написания):
{self.custom_dictionary}
"""

            prompt = f"""Ты редактор текста. Твоя задача - улучшить транскрипцию голосовой записи.

ИСХОДНЫЙ ТЕКСТ:
{transcript}
{dictionary_info}

ЗАДАЧИ:
1. Исправь опечатки и грамматические ошибки
2. Расставь правильную пунктуацию
3. Разбей текст на смысловые абзацы (по темам/событиям)
4. Сохрани естественность и стиль устной речи (не делай текст слишком формальным)
5. Не добавляй ничего от себя, только редактируй существующий текст
6. Сохрани все имена, даты, цифры как есть

ВАЖНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:
- Используй ТОЛЬКО «ёлочки» для кавычек (« »), никогда не используй " "
- Используй длинное тире (—) для пауз и пояснений, не используй дефис (-)
- Дефис (-) используй только в сложных словах (кто-то, где-то, по-русски)
- Если в словаре указаны имена или термины, используй их точное написание

ВАЖНО:
- Верни ТОЛЬКО отредактированный текст без комментариев
- Не добавляй заголовки, вступления или заключения
- Текст должен оставаться в первом лице и сохранять интонацию автора
- Если встретишь редкие имена, фамилии, термины или названия, которых нет в словаре, в конце текста после тега [СЛОВАРЬ] перечисли их через запятую"""

            response = self.text_client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=8000
            )

            improved_text = response.choices[0].message.content.strip()

            # Проверяем, есть ли новые слова для словаря
            if "[СЛОВАРЬ]" in improved_text:
                parts = improved_text.split("[СЛОВАРЬ]")
                improved_text = parts[0].strip()
                if len(parts) > 1:
                    new_words = [w.strip() for w in parts[1].strip().split(',')]
                    self._save_to_dictionary(new_words)

            logger.info(f"Текст улучшен: {len(improved_text)} символов")

            return improved_text

        except Exception as e:
            logger.error(f"Ошибка улучшения текста: {e}")
            logger.info("Возвращаем исходную транскрипцию")
            return transcript

    def transcribe(self, audio_file_path: str) -> tuple[str, str]:
        """Транскрибировать аудио файл через Groq Whisper

        Returns:
            tuple: (transcript, title) - текст транскрипции и сгенерированный заголовок
        """
        chunk_files = []
        try:
            logger.info(f"Начинаем транскрипцию через Groq Whisper: {audio_file_path}")

            # Получаем размер файла
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            logger.info(f"Размер файла: {file_size_mb:.2f} MB")

            # Проверяем, нужно ли разделить файл
            if file_size_mb > self.max_file_size_mb:
                logger.info(f"⚠️ Файл слишком большой ({file_size_mb:.2f} MB > {self.max_file_size_mb} MB)")
                logger.info("Разделяем файл на части...")

                # Разделяем файл на части
                chunk_files = self._split_audio(audio_file_path)

                # Транскрибируем каждую часть
                transcripts = []
                for i, chunk_file in enumerate(chunk_files):
                    logger.info(f"Транскрибируем часть {i+1}/{len(chunk_files)}...")
                    chunk_transcript = self._transcribe_chunk(chunk_file)
                    transcripts.append(chunk_transcript)
                    logger.info(f"Часть {i+1} транскрибирована: {len(chunk_transcript)} символов")

                # Объединяем транскрипции
                transcript = " ".join(transcripts)
                logger.info(f"Все части объединены: {len(transcript)} символов")

            else:
                # Файл достаточно маленький, транскрибируем напрямую
                logger.info(f"Отправляем запрос к модели {self.transcription_model}...")

                with open(audio_file_path, 'rb') as audio_file:
                    transcript = self.transcription_client.audio.transcriptions.create(
                        model=self.transcription_model,
                        file=audio_file,
                        language=self.language,
                        response_format="text"
                    )

                logger.info(f"Транскрипция завершена: {len(transcript)} символов")

            logger.info(f"Первые 200 символов: {transcript[:200]}...")

            # Генерируем заголовок ДО улучшения текста (чтобы захватить упоминание даты)
            title = "Голосовая заметка"
            if self.improve_text:
                title = self._generate_title(transcript)
                transcript = self._improve_transcript(transcript)

            return transcript, title

        except Exception as e:
            logger.error(f"Ошибка транскрипции {audio_file_path}: {e}")
            raise

        finally:
            # Удаляем временные файлы
            for chunk_file in chunk_files:
                try:
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
                        logger.info(f"Удален временный файл: {chunk_file}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {chunk_file}: {e}")


class TaskExtractor:
    """Класс для извлечения задач и напоминаний из текста"""

    def __init__(self, client: OpenAI, model: str = "openai/gpt-4o-mini"):
        self.client = client
        self.model = model

    def extract_tasks(self, transcript: str, date: datetime) -> Dict[str, List[str]]:
        """Извлечь задачи и напоминания из текста

        Returns:
            Dict с ключами 'tasks' (список задач) и 'important' (важные заметки)
        """
        try:
            logger.info("Извлекаем задачи и напоминания из текста...")

            prompt = f"""Проанализируй текст голосовой заметки и извлеки из него:
1. Задачи и дела, которые нужно сделать
2. Важные напоминания и заметки на будущее

ТЕКСТ:
{transcript}

ПРАВИЛА:
- Извлекай только конкретные действия и напоминания
- Формулируй задачи кратко и понятно
- Если в тексте нет задач или напоминаний, верни пустые списки
- НЕ придумывай задачи, которых нет в тексте
- Сохраняй имена, даты и детали как есть

ФОРМАТ ОТВЕТА (строго JSON):
{{
  "tasks": [
    "Конкретная задача 1",
    "Конкретная задача 2"
  ],
  "important": [
    "Важное напоминание 1",
    "Важная заметка 2"
  ]
}}

ПРИМЕРЫ ЗАДАЧ:
- "Позвонить Оксане в пятницу"
- "Купить продукты для ужина"
- "Отправить отчет до конца недели"
- "Записаться к врачу"

ПРИМЕРЫ ВАЖНЫХ ЗАМЕТОК:
- "Встреча с психологом 15 ноября в 14:00"
- "День рождения Юли 20 числа"
- "Не забыть про презентацию в понедельник"

Верни ТОЛЬКО JSON без дополнительных комментариев."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=1000
            )

            result_text = response.choices[0].message.content.strip()

            # Убираем возможные markdown блоки кода
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            result = json.loads(result_text)

            tasks_count = len(result.get('tasks', []))
            important_count = len(result.get('important', []))
            logger.info(f"Извлечено задач: {tasks_count}, важных заметок: {important_count}")

            return result

        except Exception as e:
            logger.error(f"Ошибка извлечения задач: {e}")
            return {"tasks": [], "important": []}


class TaskManager:
    """Класс для управления единым файлом с задачами из дневника"""

    def __init__(self, tasks_file_path: str = "Задачи из дневника.md"):
        self.tasks_file_path = Path(tasks_file_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Создать файл, если его нет"""
        if not self.tasks_file_path.exists():
            with open(self.tasks_file_path, 'w', encoding='utf-8') as f:
                f.write("# Задачи и напоминания из дневника\n\n")
            logger.info(f"Создан файл задач: {self.tasks_file_path}")

    def _get_month_name(self, date: datetime) -> str:
        """Получить название месяца на русском"""
        months = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        return f"{months[date.month]} {date.year}"

    def _get_day_name(self, date: datetime) -> str:
        """Получить название дня недели на русском"""
        days = {
            0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
            4: "пятница", 5: "суббота", 6: "воскресенье"
        }
        return f"{date.day} {date.strftime('%B').lower()}, {days[date.weekday()]}"

    def add_tasks(self, date: datetime, tasks: List[str], important: List[str], note_title: str = None):
        """Добавить задачи и напоминания в файл

        Args:
            date: Дата записи
            tasks: Список задач
            important: Список важных напоминаний
            note_title: Название заметки (опционально)
        """
        # Если нет задач и важных заметок, ничего не добавляем
        if not tasks and not important:
            logger.info("Нет задач или напоминаний для добавления")
            return

        try:
            # Читаем текущее содержимое
            with open(self.tasks_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            month_header = f"## {self._get_month_name(date)}"
            day_header = f"### {date.day} {self._get_month_name(date).split()[0].lower()}, {['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'][date.weekday()]}"

            # Формируем новую секцию
            new_section = f"\n{day_header}\n\n"

            if note_title:
                new_section += f"*Из заметки: {note_title}*\n\n"

            if tasks:
                new_section += "#### Задачи\n"
                for task in tasks:
                    new_section += f"- [ ] {task}\n"
                new_section += "\n"

            if important:
                new_section += "#### Важное\n"
                for item in important:
                    new_section += f"- {item}\n"
                new_section += "\n"

            new_section += "---\n"

            # Проверяем, есть ли уже раздел для этого месяца
            if month_header in content:
                # Месяц уже есть, добавляем в конец месяца
                parts = content.split(month_header)
                before_month = parts[0] + month_header
                after_month = parts[1]

                # Ищем следующий месяц
                next_month_pos = after_month.find("\n## ")
                if next_month_pos != -1:
                    # Вставляем перед следующим месяцем
                    month_content = after_month[:next_month_pos]
                    rest = after_month[next_month_pos:]
                    new_content = before_month + month_content + new_section + rest
                else:
                    # Это последний месяц, добавляем в конец
                    new_content = content + new_section
            else:
                # Месяца нет, добавляем новый раздел
                new_content = content + f"\n{month_header}\n" + new_section

            # Записываем обновленное содержимое
            with open(self.tasks_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            logger.info(f"Задачи добавлены в {self.tasks_file_path}")

        except Exception as e:
            logger.error(f"Ошибка добавления задач в файл: {e}")


class ObsidianWriter:
    """Класс для сохранения заметок в Obsidian"""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def save_transcription(self, audio_file_path: str, transcription: str, title: str = None) -> str:
        """Сохранить транскрипцию в Obsidian"""
        # Получаем информацию о файле
        audio_path = Path(audio_file_path)
        file_stat = audio_path.stat()
        created_time = datetime.fromtimestamp(file_stat.st_ctime)

        # Используем сгенерированный заголовок или дефолтный
        if not title or title == "Голосовая заметка":
            note_name = created_time.strftime("%Y-%m-%d — Voice Memo")
        else:
            note_name = title

        note_path = self.vault_path / f"{note_name}.md"

        # Если файл уже существует, добавляем счетчик
        counter = 1
        original_note_name = note_name
        while note_path.exists():
            note_name = f"{original_note_name} {counter}"
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
                 tracker: ProcessedFilesTracker,
                 task_extractor: TaskExtractor = None,
                 task_manager: TaskManager = None):
        self.transcriber = transcriber
        self.obsidian_writer = obsidian_writer
        self.tracker = tracker
        self.task_extractor = task_extractor
        self.task_manager = task_manager
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

            # Получаем дату создания файла
            file_stat = Path(file_path).stat()
            created_time = datetime.fromtimestamp(file_stat.st_ctime)

            # Транскрибируем
            logger.info("Начинаем транскрипцию...")
            transcription, title = self.transcriber.transcribe(file_path)

            # Сохраняем в Obsidian
            logger.info("Сохраняем в Obsidian...")
            note_path = self.obsidian_writer.save_transcription(file_path, transcription, title)

            # Извлекаем задачи и напоминания (если включено)
            if self.task_extractor and self.task_manager:
                logger.info("Извлекаем задачи из записи...")
                tasks_data = self.task_extractor.extract_tasks(transcription, created_time)
                self.task_manager.add_tasks(
                    date=created_time,
                    tasks=tasks_data.get('tasks', []),
                    important=tasks_data.get('important', []),
                    note_title=title
                )

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
    groq_api_key = os.getenv('GROQ_API_KEY')
    openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
    transcription_model = os.getenv('TRANSCRIPTION_MODEL', 'whisper-large-v3-turbo')
    text_improvement_model = os.getenv('TEXT_IMPROVEMENT_MODEL', 'openai/gpt-4o-mini')
    task_extraction_model = os.getenv('TASK_EXTRACTION_MODEL', 'openai/gpt-4o-mini')
    voice_memos_path = os.getenv('VOICE_MEMOS_PATH')
    obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')
    language = os.getenv('TRANSCRIPTION_LANGUAGE', 'ru')
    improve_text = os.getenv('IMPROVE_TEXT', 'true').lower() == 'true'
    extract_tasks = os.getenv('EXTRACT_TASKS', 'true').lower() == 'true'
    tasks_file_path = os.getenv('TASKS_FILE_PATH', 'Задачи из дневника.md')

    # Проверяем наличие необходимых настроек
    if not groq_api_key:
        logger.error("❌ GROQ_API_KEY не задан в .env файле")
        sys.exit(1)

    if not openrouter_api_key:
        logger.error("❌ OPENROUTER_API_KEY не задан в .env файле")
        logger.info("💡 Получите ключ на https://openrouter.ai/keys")
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
    tasks_file_path = os.path.expanduser(tasks_file_path)

    # Проверяем существование папки Voice Memos
    if not os.path.exists(voice_memos_path):
        logger.error(f"❌ Папка Voice Memos не найдена: {voice_memos_path}")
        logger.info("💡 Проверьте путь в .env файле")
        sys.exit(1)

    logger.info("🎙️ Voice Memo Watcher запущен")
    logger.info(f"📂 Отслеживаем: {voice_memos_path}")
    logger.info(f"📝 Сохраняем в: {obsidian_vault_path}")
    logger.info(f"🎤 Модель транскрипции: {transcription_model} (Groq)")
    logger.info(f"✍️  Модель улучшения текста: {text_improvement_model} (OpenRouter)")
    logger.info(f"🌍 Язык: {language}")
    logger.info(f"✨ Улучшение текста: {'включено' if improve_text else 'выключено'}")
    logger.info(f"📋 Извлечение задач: {'включено' if extract_tasks else 'выключено'}")
    if extract_tasks:
        logger.info(f"🔍 Модель извлечения задач: {task_extraction_model} (OpenRouter)")
        logger.info(f"📄 Файл задач: {tasks_file_path}")

    # Создаем OpenRouter клиента для улучшения текста и извлечения задач
    openrouter_client = OpenAI(
        api_key=openrouter_api_key,
        base_url="https://openrouter.ai/api/v1"
    )

    # Создаем объекты
    tracker = ProcessedFilesTracker()
    transcriber = VoiceMemoTranscriber(
        groq_api_key=groq_api_key,
        openrouter_client=openrouter_client,
        transcription_model=transcription_model,
        text_model=text_improvement_model,
        language=language,
        improve_text=improve_text
    )
    obsidian_writer = ObsidianWriter(obsidian_vault_path)

    # Создаем объекты для извлечения задач (если включено)
    task_extractor = None
    task_manager = None
    if extract_tasks:
        task_extractor = TaskExtractor(openrouter_client, task_extraction_model)
        task_manager = TaskManager(tasks_file_path)

    event_handler = VoiceMemoHandler(transcriber, obsidian_writer, tracker, task_extractor, task_manager)

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
