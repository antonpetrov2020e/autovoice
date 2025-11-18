# 🚀 Настройка автозапуска

Инструкции по настройке автоматического запуска Voice Memo Watcher при старте macOS.

## Метод 1: launchd (Рекомендуется для macOS)

### Шаг 1: Отредактируйте plist файл

Откройте `com.voicememo.watcher.plist` и замените `ЗАМЕНИТЕ_НА_ПОЛНЫЙ_ПУТЬ` на реальный путь к папке проекта.

Например, если проект находится в `/Users/viktorivanov/autovoice`, то:

```xml
<string>/usr/bin/python3</string>
<string>/Users/viktorivanov/autovoice/voice_memo_watcher.py</string>
```

и

```xml
<key>WorkingDirectory</key>
<string>/Users/viktorivanov/autovoice</string>
```

### Шаг 2: Скопируйте plist в LaunchAgents

```bash
cp com.voicememo.watcher.plist ~/Library/LaunchAgents/
```

### Шаг 3: Загрузите сервис

```bash
launchctl load ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

### Шаг 4: Проверьте, что сервис запущен

```bash
launchctl list | grep voicememo
```

Вы должны увидеть что-то вроде:
```
12345   0   com.voicememo.watcher
```

### Управление сервисом

**Остановить:**
```bash
launchctl unload ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

**Запустить снова:**
```bash
launchctl load ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

**Удалить из автозапуска:**
```bash
launchctl unload ~/Library/LaunchAgents/com.voicememo.watcher.plist
rm ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

### Просмотр логов

Логи сохраняются в:
- Стандартный вывод: `/tmp/voicememo-watcher.log`
- Ошибки: `/tmp/voicememo-watcher.error.log`

```bash
tail -f /tmp/voicememo-watcher.log
```

---

## Метод 2: Автозапуск через Login Items (Простой способ)

### Создайте shell скрипт

Создайте файл `start_watcher.sh`:

```bash
#!/bin/bash
cd /Users/viktorivanov/autovoice
/usr/bin/python3 voice_memo_watcher.py >> /tmp/voicememo.log 2>&1
```

Замените путь на ваш.

Сделайте его исполняемым:
```bash
chmod +x start_watcher.sh
```

### Добавьте в Login Items

1. Откройте **Системные настройки** → **Основные** → **Login Items**
2. Нажмите **+**
3. Выберите `start_watcher.sh`

Теперь скрипт будет запускаться при входе в систему.

---

## Метод 3: Использование Automator

### Шаг 1: Создайте Application в Automator

1. Откройте **Automator**
2. Выберите **Application**
3. Добавьте действие **Run Shell Script**
4. Вставьте:

```bash
cd /Users/viktorivanov/autovoice
/usr/bin/python3 voice_memo_watcher.py
```

5. Сохраните как `VoiceMemoWatcher.app`

### Шаг 2: Добавьте в Login Items

1. **Системные настройки** → **Основные** → **Login Items**
2. Добавьте созданное приложение `VoiceMemoWatcher.app`

---

## Метод 4: Cron (Не рекомендуется)

Cron не очень подходит для долгоработающих процессов, но можно настроить проверку каждые N минут.

```bash
crontab -e
```

Добавьте:
```
*/5 * * * * cd /Users/viktorivanov/autovoice && /usr/bin/python3 voice_memo_watcher.py
```

Это будет запускать скрипт каждые 5 минут.

---

## Проверка работы

После настройки автозапуска:

1. Перезагрузите Mac
2. Сделайте новую запись в Voice Memos
3. Подождите несколько секунд
4. Проверьте папку Obsidian - должна появиться новая заметка

---

## Устранение проблем

### Сервис не запускается

1. Проверьте логи:
```bash
cat /tmp/voicememo-watcher.error.log
```

2. Проверьте права:
```bash
ls -l ~/Library/LaunchAgents/com.voicememo.watcher.plist
```

3. Убедитесь, что пути в plist файле правильные

### Нет доступа к файлам

macOS может блокировать доступ. Добавьте Python в:
- **Системные настройки** → **Конфиденциальность** → **Полный доступ к диску**

### Переменные окружения не загружаются

В launchd переменные из `.env` могут не загружаться автоматически. Убедитесь, что `.env` файл находится в рабочей директории проекта.

---

**Рекомендация:** Используйте **Метод 1 (launchd)** для надежной работы в фоне.
