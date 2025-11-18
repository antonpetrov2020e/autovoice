# 🎙️ Voice Memo Auto Transcriber

Автоматическая транскрипция голосовых заметок из приложения "Диктофон" (Voice Memos) на Mac с сохранением в Obsidian.

## 📋 Описание

Это решение автоматически:
1. **Отслеживает** появление новых записей в Voice Memos
2. **Транскрибирует** их с помощью OpenAI Whisper
3. **Сохраняет** расшифровки в вашем Obsidian хранилище

Больше не нужно вручную искать записи и отправлять на расшифровку!

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

### 2. Установите Python зависимости

```bash
pip install -r requirements.txt
```

### 3. Настройте конфигурацию

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл:

```bash
# OpenAI API ключ (получите на https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-actual-api-key-here

# Путь к папке с записями Voice Memos (обычно этот путь)
VOICE_MEMOS_PATH=/Users/viktorivanov/Library/Application Support/com.apple.voicememos/Recordings

# Путь к папке в Obsidian, куда сохранять транскрипции
OBSIDIAN_VAULT_PATH=/Users/viktorivanov/Documents/Obsidian/MyVault/Daily Diary

# Язык транскрипции (ru = русский, en = английский)
TRANSCRIPTION_LANGUAGE=ru
```

### 4. Проверьте путь к Voice Memos

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
2. Убедитесь, что у вас есть кредиты на аккаунте OpenAI
3. Проверьте на https://platform.openai.com/api-keys

### Записи не появляются в Obsidian

1. Проверьте путь `OBSIDIAN_VAULT_PATH` в `.env`
2. Убедитесь, что у скрипта есть права на запись в эту папку
3. Проверьте логи в `voice_memo_watcher.log`

## 💰 Стоимость

Использование OpenAI Whisper API:
- **$0.006 за минуту** аудио

Примеры:
- 10-минутная запись = $0.06
- 30-минутная запись = $0.18
- 1 час записи = $0.36

## 📝 Отслеживание обработанных файлов

Скрипт хранит список обработанных файлов в `processed_files.json`. Это предотвращает повторную обработку одних и тех же записей.

Чтобы обработать файл заново:
1. Удалите его путь из `processed_files.json`
2. Перезапустите скрипт

Или полностью очистите историю:
```bash
rm processed_files.json
```

## 🔧 Расширенная настройка

### Изменение формата заметок

Отредактируйте метод `ObsidianWriter.save_transcription()` в `voice_memo_watcher.py`

### Поддержка других форматов

Скрипт поддерживает: `.m4a`, `.mp3`, `.wav`, `.m4v`

Для добавления других форматов, измените список в методе `VoiceMemoHandler.on_created()`

### Другие языки

Поддерживаются все языки Whisper. Измените `TRANSCRIPTION_LANGUAGE` в `.env`:
- `ru` - Русский
- `en` - Английский
- `es` - Испанский
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
