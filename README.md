# 🎙️ Voice Memo Auto Transcriber

Автоматическая транскрипция голосовых заметок из приложения "Диктофон" (Voice Memos) на Mac с сохранением в Obsidian.

## 📋 Описание

Это решение автоматически:
1. **Отслеживает** появление новых записей в Voice Memos
2. **Транскрибирует** их с помощью Groq Whisper (бесплатно)
3. **Обрабатывает большие файлы**: автоматически разделяет записи > 20 MB на части
4. **Улучшает текст**: исправляет ошибки, расставляет пунктуацию, форматирует
5. **Генерирует осмысленные заголовки** на основе содержания
6. **Использует пользовательский словарь** для точной транскрипции имен и терминов
7. **Сохраняет** красиво оформленные заметки в Obsidian

Больше не нужно вручную искать записи и отправлять на расшифровку!

### ✨ Новые возможности

- **Умные заголовки**: Вместо "2025-11-19 - Voice Memo" создаются осмысленные названия типа "15 ноября, суббота" или "Встреча с психологом"
- **Правильная типографика**: Автоматические «ёлочки» для кавычек и длинное тире (—)
- **Пользовательский словарь**: Система запоминает сложные имена, термины и названия для улучшения качества

## 🔍 Где хранятся записи Voice Memos?

Voice Memos на Mac сохраняет записи в:
```
~/Library/Application Support/com.apple.voicememos/Recordings/
```

**Важно:** Путь, который вы видели (`/tmp/.com.apple.uikit.itemprovider.temporary...`) — это временная папка, используемая только при передаче данных между приложениями. Реальные записи хранятся в папке выше.

## 🚀 Установка

### 1. Клонируйте репозиторий

```bash
git clone <url-репозитория>
cd autovoice
```

### 2. Установите системные зависимости

Для обработки больших аудио файлов требуется ffmpeg:

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

### 3. Установите Python зависимости

```bash
pip install -r requirements.txt
```

### 4. Настройте конфигурацию

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл:

```bash
# OpenRouter API ключ (получите на https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-your-actual-api-key-here

# Модель для транскрипции (по умолчанию Gemini 2.5 Flash Lite)
TRANSCRIPTION_MODEL=google/gemini-2.5-flash-lite-preview-09-2025

# Путь к папке с записями Voice Memos (обычно этот путь)
VOICE_MEMOS_PATH=/Users/viktorivanov/Library/Application Support/com.apple.voicememos/Recordings

# Путь к папке в Obsidian, куда сохранять транскрипции
OBSIDIAN_VAULT_PATH=/Users/viktorivanov/Documents/Obsidian/MyVault/Daily Diary

# Язык транскрипции (ru = русский, en = английский)
TRANSCRIPTION_LANGUAGE=ru
```

### Получение OpenRouter API ключа

1. Зарегистрируйтесь на https://openrouter.ai
2. Перейдите в раздел **Keys**: https://openrouter.ai/keys
3. Создайте новый ключ
4. Скопируйте и вставьте в `.env` файл

### 5. Проверьте путь к Voice Memos

Убедитесь, что папка с записями существует:

```bash
ls -la ~/Library/Application\ Support/com.apple.voicememos/Recordings/
```

Если папка не существует:
- Запустите приложение "Диктофон" на Mac
- Сделайте тестовую запись
- Проверьте снова

## 📖 Использование

### Запуск в обычном режиме

```bash
python voice_memo_watcher.py
```

При первом запуске скрипт:
1. Обработает все существующие записи
2. Начнет отслеживать новые записи

### Что происходит при работе

1. **Обнаружение:** Скрипт обнаруживает новый `.m4a` файл в папке Voice Memos
2. **Транскрипция:** Отправляет его в OpenAI Whisper для расшифровки
3. **Сохранение:** Создает заметку в Obsidian в формате:

```markdown
# 2024-11-15 - Voice Memo

**Дата записи:** 15.11.2024 14:30
**Источник:** My Recording.m4a

---

[Текст транскрипции]

---

*Автоматически транскрибировано: 15.11.2024 14:35*
```

### Логи

Все события записываются в:
- Консоль (stdout)
- Файл `voice_memo_watcher.log`

### Остановка

Нажмите `Ctrl+C` для остановки мониторинга.

### 📦 Обработка больших файлов

Groq Whisper API имеет ограничение на размер файла в 25 MB. Скрипт автоматически:

- **Обнаруживает** файлы размером более 20 MB
- **Разделяет** их на части оптимального размера
- **Транскрибирует** каждую часть отдельно
- **Объединяет** результаты в единый текст

Это позволяет обрабатывать записи любой длительности без ограничений!

## 🔄 Автозапуск при старте системы

### Вариант 1: launchd (macOS)

Создайте файл `~/Library/LaunchAgents/com.voicememo.watcher.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicememo.watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/полный/путь/к/autovoice/voice_memo_watcher.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/полный/путь/к/autovoice</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/voicememo-watcher.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/voicememo-watcher.error.log</string>
</dict>
</plist>
```

Замените `/полный/путь/к/autovoice` на реальный путь.

Загрузите сервис:

```bash
launchctl load ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

Проверьте статус:

```bash
launchctl list | grep voicememo
```

### Вариант 2: Запуск в фоне с nohup

```bash
nohup python voice_memo_watcher.py &
```

## 🛠️ Устранение проблем

### Папка Voice Memos не найдена

Если скрипт не может найти папку с записями:

1. Проверьте, что Voice Memos установлен и работает
2. Сделайте тестовую запись
3. Поищите файлы вручную:

```bash
find ~/Library -name "*.m4a" -type f 2>/dev/null | grep -i voice
```

### Проблемы с доступом к файлам

macOS может потребовать предоставить доступ к файлам:
- Откройте **Системные настройки** → **Конфиденциальность и безопасность** → **Полный доступ к диску**
- Добавьте Terminal (или приложение, из которого запускаете скрипт)

### API ключ не работает

1. Проверьте, что ключ правильно скопирован в `.env`
2. Убедитесь, что у вас есть кредиты на аккаунте OpenRouter
3. Проверьте на https://openrouter.ai/credits
4. Убедитесь, что модель поддерживает аудио: https://openrouter.ai/models

### Записи не появляются в Obsidian

1. Проверьте путь `OBSIDIAN_VAULT_PATH` в `.env`
2. Убедитесь, что у скрипта есть права на запись в эту папку
3. Проверьте логи в `voice_memo_watcher.log`

## 💰 Стоимость

Использование через OpenRouter с моделью Gemini 2.5 Flash Lite:

**Стоимость зависит от модели:**

- **google/gemini-2.5-flash-lite-preview-09-2025**: ~$0.01-0.05 за запрос
  - Очень доступная
  - Отличное качество транскрипции

- **google/gemini-2.0-flash-thinking-exp:free**: **БЕСПЛАТНАЯ**
  - Можно использовать без затрат
  - Установите в `.env`: `TRANSCRIPTION_MODEL=google/gemini-2.0-flash-thinking-exp:free`

- **google/gemini-flash-1.5**: ~$0.02-0.10 за запрос
  - Более стабильная версия

**Преимущество OpenRouter:**
- Можно пополнить счет на $5 и этого хватит на сотни записей
- Поддержка множества моделей
- Гибкое ценообразование

Проверить актуальные цены: https://openrouter.ai/models

## 📝 Отслеживание обработанных файлов

Скрипт хранит список обработанных файлов в `processed_files.json`. Это предотвращает повторную обработку одних и тех же записей.

Чтобы обработать файл заново:
1. Удалите его путь из `processed_files.json`
2. Перезапустите скрипт

Или полностью очистите историю:
```bash
rm processed_files.json
```

## 📚 Пользовательский словарь

Для улучшения качества транскрипции создайте файл `custom_dictionary.txt`:

```bash
cp custom_dictionary.txt.example custom_dictionary.txt
open -e custom_dictionary.txt
```

Добавьте туда:
- Имена людей, которых часто упоминаете
- Названия компаний и проектов
- Специфичные термины
- Сложные слова

### Пример словаря:

```
# Имена
Оксана
Леонид
София
Виолетта

# Названия
Dom Foundation
ChatGPT
Obsidian

# Термины
контрзависимость
копинг-карточки
```

Система будет:
1. Использовать эти слова при улучшении текста
2. Автоматически добавлять новые сложные слова, которые встретит
3. Постоянно улучшать качество распознавания

## 🔧 Расширенная настройка

### Выбор модели для транскрипции

В `.env` вы можете выбрать любую модель из OpenRouter, которая поддерживает аудио:

```bash
# Бесплатная модель
TRANSCRIPTION_MODEL=google/gemini-2.0-flash-thinking-exp:free

# Быстрая и доступная (рекомендуется)
TRANSCRIPTION_MODEL=google/gemini-2.5-flash-lite-preview-09-2025

# Стабильная версия
TRANSCRIPTION_MODEL=google/gemini-flash-1.5

# Самая мощная Gemini
TRANSCRIPTION_MODEL=google/gemini-exp-1206
```

Полный список моделей: https://openrouter.ai/models

### Изменение формата заметок

Отредактируйте метод `ObsidianWriter.save_transcription()` в `voice_memo_watcher.py`

### Поддержка других форматов

Скрипт поддерживает: `.m4a`, `.mp3`, `.wav`, `.m4v`, `.aac`, `.ogg`, `.flac`

Для добавления других форматов, измените список в методе `VoiceMemoHandler.on_created()`

### Другие языки

Поддерживаются многие языки. Измените `TRANSCRIPTION_LANGUAGE` в `.env`:
- `ru` - Русский
- `en` - Английский
- `es` - Испанский
- `fr` - Французский
- `de` - Немецкий
- и т.д.

## 📄 Лицензия

MIT

## 🤝 Вклад

Pull requests приветствуются!

## ❓ Вопросы

Если возникли проблемы, проверьте:
1. Логи в `voice_memo_watcher.log`
2. Права доступа к папкам
3. Наличие API ключа и кредитов

---

**Приятного использования! 🎉**
